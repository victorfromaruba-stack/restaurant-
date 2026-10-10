#!/usr/bin/env python3
"""Apply PIDI_SETUP.sql twice on a throwaway Postgres and run the order flow as anon.

The database is local. Nothing here contacts Supabase.
"""

import json
import re
import sys
import threading
from pathlib import Path

import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "PIDI_SETUP.sql"
DSN_ADMIN = "dbname=postgres host=/var/run/postgresql"
DSN = "dbname=pidi_v2_test host=/var/run/postgresql"

passed = 0
failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("pass ", name)
    else:
        failed += 1
        print("FAIL ", name, detail)


def q(conn, sql, args=None):
    cur = conn.cursor()
    cur.execute(sql, args)
    if cur.description:
        return cur.fetchall()
    return []


def scalar(conn, sql, args=None):
    rows = q(conn, sql, args)
    return rows[0][0] if rows else None


def explodes(conn, sql, args, needle):
    q(conn, "SAVEPOINT pidi_try")
    try:
        q(conn, sql, args)
    except psycopg2.Error as err:
        q(conn, "ROLLBACK TO SAVEPOINT pidi_try")
        message = err.diag.message_primary or str(err)
        return needle.lower() in message.lower(), message
    q(conn, "RELEASE SAVEPOINT pidi_try")
    return False, "no error"


def snapshot(conn):
    relations = q(conn, """
        select n.nspname, c.relname, c.relkind
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname in ('public', 'auth', 'storage', 'realtime', 'extensions')
          and c.relkind in ('r', 'v', 'm', 'S', 'i', 'f')
        order by 1, 2, 3
    """)
    routines = q(conn, """
        select n.nspname, p.proname, md5(p.prosrc)
        from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname in ('public', 'auth', 'storage', 'realtime', 'extensions')
          and p.proname not like 'pidi\\_%' escape '\\'
        order by 1, 2, 3
    """)
    types = q(conn, """
        select n.nspname, t.typname
        from pg_type t
        join pg_namespace n on n.oid = t.typnamespace
        where n.nspname = 'public' and t.typtype in ('e', 'c')
          and t.typname not like '\\_pidi\\_%' escape '\\'
          and t.typname not like 'pidi\\_%' escape '\\'
        order by 1, 2
    """)
    policies = q(conn, """
        select n.nspname, c.relname, pol.polname, pol.polcmd::text,
               coalesce(pg_get_expr(pol.polqual, pol.polrelid), ''),
               coalesce(pg_get_expr(pol.polwithcheck, pol.polrelid), '')
        from pg_policy pol
        join pg_class c on c.oid = pol.polrelid
        join pg_namespace n on n.oid = c.relnamespace
        where c.relname not like 'pidi\\_%' escape '\\'
        order by 1, 2, 3
    """)
    schemas = q(conn, "select nspname from pg_namespace order by 1")
    roles = q(conn, "select rolname from pg_roles order by 1")
    extensions = q(conn, "select extname, n.nspname from pg_extension e join pg_namespace n on n.oid = e.extnamespace order by 1")
    grants = q(conn, """
        select grantee, table_schema, table_name, privilege_type
        from information_schema.role_table_grants
        where table_schema in ('public', 'auth', 'storage', 'realtime')
          and table_name not like 'pidi\\_%' escape '\\'
        order by 1, 2, 3, 4
    """)
    dummy = q(conn, """
        select column_name, data_type
        from information_schema.columns
        where table_schema = 'public' and table_name = 'bookkeeping_dummy'
        order by ordinal_position
    """)
    row = q(conn, "select id, note from public.bookkeeping_dummy order by id")
    auth_row = q(conn, "select id::text, email from auth.users order by email")
    bucket = q(conn, "select id from storage.buckets order by id")
    return {
        "relations": relations,
        "routines": routines,
        "types": types,
        "policies": policies,
        "schemas": schemas,
        "roles": roles,
        "extensions": extensions,
        "grants": grants,
        "dummy": dummy,
        "row": row,
        "auth_row": auth_row,
        "bucket": bucket,
    }


def new_public_names(before, after):
    old = {(schema, name) for schema, name, _kind in before["relations"]}
    fresh = []
    for schema, name, kind in after["relations"]:
        if (schema, name) not in old:
            fresh.append((schema, name, kind))
    return fresh


def supabase_defaults(conn):
    """Hosted Supabase grants anon and authenticated execute on new functions and all on new tables."""
    q(conn, """
        do $role$ begin
          if not exists (select 1 from pg_roles where rolname = 'authenticated') then
            create role authenticated nologin noinherit;
          end if;
        end $role$
    """)
    q(conn, "alter default privileges in schema public grant execute on functions to anon, authenticated")
    q(conn, "alter default privileges in schema public grant all on tables to anon, authenticated")


ALLOWED = [
    "pidi_ping()",
    "pidi_place_order(jsonb)",
    "pidi_order_status(text)",
    "pidi_find_order(text)",
    "pidi_public_state()",
    "pidi_kitchen_set_busy(text,integer)",
    "pidi_kitchen_login(text)",
    "pidi_kitchen_feed(text)",
    "pidi_kitchen_accept(text,uuid)",
    "pidi_kitchen_set_status(text,uuid,text)",
    "pidi_kitchen_mark_ready(text,uuid,text)",
    "pidi_kitchen_cancel(text,uuid)",
    "pidi_kitchen_transfer_paid(text,uuid)",
    "pidi_driver_login(text,text)",
    "pidi_driver_set_online(text,boolean)",
    "pidi_driver_offers(text)",
    "pidi_driver_accept(text,uuid)",
    "pidi_driver_decline(text,uuid)",
    "pidi_driver_run(text)",
    "pidi_driver_picked_up(text,uuid)",
    "pidi_driver_delivered(text,uuid)",
    "pidi_driver_location(text,numeric,numeric)",
    "pidi_admin_add_driver(text,text,text,text)",
    "pidi_admin_set_kitchen_pin(text,text)",
    "pidi_admin_list_drivers(text)",
    "pidi_admin_remove_driver(text,uuid)",
]


def privileges(conn):
    rows = q(conn, """
        select replace(p.oid::regprocedure::text, 'public.', ''),
               has_function_privilege('anon', p.oid, 'execute'),
               has_function_privilege('authenticated', p.oid, 'execute')
        from pg_proc p join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public' and p.proname like 'pidi\\_%' escape '\\'
    """)
    allowed = {sig.replace(" ", "") for sig in ALLOWED}
    leaks = [(sig, anon, auth) for sig, anon, auth in rows
             if auth or (anon and sig.replace(" ", "") not in allowed)]
    missing = sorted(allowed - {sig.replace(" ", "") for sig, anon, _auth in rows if anon})
    tables = q(conn, """
        select c.relname, r.rolname
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        cross join (values ('anon'), ('authenticated')) r(rolname)
        where n.nspname = 'public' and c.relkind = 'r' and c.relname like 'pidi\\_%' escape '\\'
          and (has_table_privilege(r.rolname, c.oid, 'select') or has_table_privilege(r.rolname, c.oid, 'insert')
               or has_table_privilege(r.rolname, c.oid, 'update') or has_table_privilege(r.rolname, c.oid, 'delete'))
    """)
    return leaks, missing, tables


def static_sql():
    text = SQL_PATH.read_text(encoding="utf-8")
    banned = [
        (r"\bcreate\s+extension\b", "create extension"),
        (r"\bcreate\s+schema\b", "create schema"),
        (r"\bcreate\s+role\b", "create role"),
        (r"\balter\s+role\b", "alter role"),
        (r"\bdrop\s+schema\b", "drop schema"),
        (r"\bdrop\s+table\b", "drop table"),
        (r"\bdrop\s+function\b", "drop function"),
        (r"\balter\s+default\s+privileges\b", "default privileges"),
        (r"\bauth\.", "auth."),
        (r"\bstorage\.", "storage."),
    ]
    bad = [label for pattern, label in banned if re.search(pattern, text, re.I)]
    check("SQL file does not enable extensions, schemas, or roles", not bad, " ".join(bad))
    alters = re.findall(r"\balter\s+table\s+(?:only\s+)?(?:public\.)?(\w+)", text, re.I)
    check("ALTER TABLE names are pidi_", all(name.startswith("pidi_") for name in alters), str(alters))
    drops = re.findall(r"\bdrop\s+policy\s+if\s+exists\s+(\w+)", text, re.I)
    check("dropped policies are pidi_", all(name.startswith("pidi_") for name in drops), str(drops))
    pubs = re.findall(r"\balter\s+publication\s+(\w+)\s+add\s+table\s+public\.(\w+)", text, re.I)
    # The publication name is a format string in PL/pgSQL, so also accept the guarded DO block.
    guarded = "alter publication supabase_realtime add table public.%I" in text
    check("publication change is only pidi_ tables", guarded and "supabase_realtime" in text)
    check(
        "placeholder appears once, on the pin assignment",
        text.count("PUT_8_DIGIT_ADMIN_PIN") == 1 and "pin text := 'PUT_8_DIGIT_ADMIN_PIN';" in text,
        str(text.count("PUT_8_DIGIT_ADMIN_PIN")),
    )


def seed_when_placeholder_replaced():
    pin = "13572468"
    admin = psycopg2.connect(DSN_ADMIN)
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    admin.cursor().execute("drop database if exists pidi_v2_seed")
    admin.cursor().execute("create database pidi_v2_seed")
    admin.close()
    conn = psycopg2.connect("dbname=pidi_v2_seed host=/var/run/postgresql")
    conn.autocommit = True
    q(conn, "create schema if not exists extensions")
    q(conn, "create extension if not exists pgcrypto with schema extensions")
    q(conn, """
        do $role$ begin
          if not exists (select 1 from pg_roles where rolname = 'anon') then
            create role anon nologin noinherit;
          end if;
        end $role$
    """)
    supabase_defaults(conn)
    replaced = SQL_PATH.read_text(encoding="utf-8").replace("PUT_8_DIGIT_ADMIN_PIN", pin)
    cur = conn.cursor()
    cur.execute(replaced)
    conn.commit()
    stored = scalar(conn, "select value from public.pidi_settings where key = 'admin_pin_hash'")
    matches = False
    if stored:
        matches = scalar(conn, "select extensions.crypt(%s, %s) = %s", [pin, stored, stored])
    check(
        "replacing the placeholder with 8 digits seeds the admin PIN",
        bool(stored) and matches is True,
        "no hash" if not stored else "hash does not match",
    )
    conn.close()
    admin = psycopg2.connect(DSN_ADMIN)
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    admin.cursor().execute("drop database if exists pidi_v2_seed")
    admin.close()


def apply_sql(conn):
    statement = SQL_PATH.read_text(encoding="utf-8")
    cur = conn.cursor()
    cur.execute(statement)
    conn.commit()


def main():
    static_sql()
    admin = psycopg2.connect(DSN_ADMIN)
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    admin.cursor().execute("drop database if exists pidi_v2_test")
    admin.cursor().execute("create database pidi_v2_test")
    admin.close()

    psycopg2.extras.register_default_jsonb(globally=True)
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    q(conn, "create schema if not exists extensions")
    q(conn, "create extension if not exists pgcrypto with schema extensions")
    q(conn, """
        do $role$ begin
          if not exists (select 1 from pg_roles where rolname = 'anon') then
            create role anon nologin noinherit;
          end if;
        end $role$
    """)
    supabase_defaults(conn)
    q(conn, """
        create schema if not exists auth;
        create table auth.users (id uuid primary key, email text);
        insert into auth.users values ('11111111-1111-1111-1111-111111111111', 'bookkeeper@example.com');
        create schema if not exists storage;
        create table storage.buckets (id text primary key);
        insert into storage.buckets values ('receipts');
        create schema if not exists realtime;
        create table realtime.messages (id integer primary key, topic text);
        insert into realtime.messages values (1, 'bookkeeping');
        create table public.bookkeeping_dummy (id integer primary key, note text);
        insert into public.bookkeeping_dummy values (1, 'do not touch');
        alter table public.bookkeeping_dummy enable row level security;
        create policy bookkeeping_dummy_keep on public.bookkeeping_dummy
          for select using (note = 'do not touch');
    """)
    before = snapshot(conn)
    apply_sql(conn)
    apply_sql(conn)
    after = snapshot(conn)

    check("second apply leaves the bookkeeping row", after["row"] == [(1, "do not touch")])
    check("dummy columns unchanged", before["dummy"] == after["dummy"])
    check("dummy policies unchanged", before["policies"] == after["policies"])
    check("non-pidi routines unchanged", before["routines"] == after["routines"])
    check("non-pidi types unchanged", before["types"] == after["types"])
    check("schemas unchanged", before["schemas"] == after["schemas"])
    check("roles unchanged", before["roles"] == after["roles"])
    check("extensions unchanged", before["extensions"] == after["extensions"])
    check("grants on non-pidi tables unchanged", before["grants"] == after["grants"])
    check("auth.users row unchanged", after["auth_row"] == [("11111111-1111-1111-1111-111111111111", "bookkeeper@example.com")])
    check("storage bucket unchanged", after["bucket"] == [("receipts",)])
    check("realtime.messages row unchanged", scalar(conn, "select topic from realtime.messages") == "bookkeeping")
    fresh = new_public_names(before, after)
    bad_names = [item for item in fresh if item[0] != "public" or not item[1].startswith("pidi_")]
    check("new relations are public.pidi_ only", not bad_names, str(bad_names))
    check("five restaurants", scalar(conn, "select count(*) from public.pidi_restaurants") == 5)
    leaks, missing, tables = privileges(conn)
    check("anon runs only the app's functions, authenticated none", not leaks, str(leaks))
    check("anon runs every app function", not missing, str(missing))
    check("anon and authenticated have no rights on pidi_ tables", not tables, str(tables))
    check("no admin PIN stored by the paste", scalar(conn, "select value from public.pidi_settings where key = 'admin_pin_hash'") is None)
    check("unset admin PIN raises a notice", any("Admin PIN was not set" in note for note in conn.notices), " ".join(conn.notices)[-400:])

    # Broadcast stub. Created after the safety diff so the diff stays about the paste.
    q(conn, """
        create table public.bookkeeping_realtime_log (
          id integer generated always as identity primary key,
          payload jsonb, event text, topic text, private boolean
        );
        create or replace function realtime.send(payload jsonb, event text, topic text, private boolean)
        returns void language plpgsql as $fn$
        begin
          insert into public.bookkeeping_realtime_log (payload, event, topic, private)
          values (payload, event, topic, private);
        end
        $fn$;
    """)

    conn.autocommit = False
    q(conn, """
        insert into public.pidi_settings (key, value)
        values ('admin_pin_hash', extensions.crypt('42424242', extensions.gen_salt('bf', 8)))
    """)
    q(conn, "update public.pidi_settings set value = 'flag' where key = 'hours_mode'")
    q(conn, """
        insert into public.pidi_restaurants (slug, name, partner)
        values ('partner-test', 'Partner Test', true)
    """)
    conn.commit()
    check(
        "fee amounts are stored",
        scalar(conn, "select value from public.pidi_settings where key = 'fee_own'") == "500"
        and scalar(conn, "select value from public.pidi_settings where key = 'fee_partner'") == "1000",
    )

    q(conn, "set role anon")
    ok, detail = explodes(conn, "select public.pidi_dispatch()", None, "permission denied")
    check("anon cannot call dispatch directly", ok, detail)
    ok, detail = explodes(
        conn,
        "select public.pidi_place_order(%s::jsonb)",
        ['{"restaurant":"dushi-wok","name":"A","phone":"2975550001","area":"Noord","address":"1","pay":"cash","pays_with_cents":5000,"items":[{"name":"Fries","qty":1,"price_cents":100}]}'],
        "MIN_FOOD",
    )
    check("minimum ƒ24 rejected", ok, detail)
    ok, detail = explodes(conn, "select count(*) from public.pidi_orders", None, "permission denied")
    check("anon select on orders is denied", ok, detail)
    ok, detail = explodes(conn, "select count(*) from public.pidi_drivers", None, "permission denied")
    check("anon select on drivers is denied", ok, detail)
    ok, detail = explodes(conn, "select count(*) from public.pidi_kitchen_sessions", None, "permission denied")
    check("anon select on kitchen sessions is denied", ok, detail)

    def place(name, phone, area, address, lat, lng, pay, pays, restaurant, dish, price):
        body = {
            "restaurant": restaurant,
            "name": name,
            "phone": phone,
            "area": area,
            "address": address,
            "lat": lat,
            "lng": lng,
            "pay": pay,
            "items": [{"name": dish, "qty": 1, "price_cents": price}],
            "test": True,
        }
        if pay == "cash":
            body["pays_with_cents"] = pays
        row = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])
        return row

    first = place("Maria TEST", "2975990001", "Noord", "TEST, Weg 12", "12.5190", "-70.0370", "cash", 5000, "dushi-wok", "Chicken fried rice", 2895)
    second = place("Carlos TEST", "2975990002", "Oranjestad", "TEST, Wilhelminastraat 8", "12.5300", "-70.0370", "transfer", None, "taco-brava", "Birria tacos", 2700)
    conn.commit()
    check("cash total is ƒ33.95", first["total_cents"] == 3395 and first["fee_cents"] == 500)
    check("change due is ƒ16.05", first["change_due_cents"] == 1605)
    check("transfer has no change", second["change_due_cents"] is None and second["fee_cents"] == 500)

    def place_items(items, pay="cash", pays=8000, name="Mix TEST", phone="2975990099"):
        body = {
            "name": name,
            "phone": phone,
            "area": "Noord",
            "address": "TEST, Mixweg 1",
            "lat": "12.6000",
            "lng": "-70.0500",
            "pay": pay,
            "items": items,
            "test": True,
        }
        if pay == "cash":
            body["pays_with_cents"] = pays
        return scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])

    ok, detail = explodes(
        conn,
        "select public.pidi_place_order(%s::jsonb)",
        [json.dumps({
            "name": "Low TEST",
            "phone": "2975990098",
            "area": "Noord",
            "address": "TEST",
            "pay": "cash",
            "pays_with_cents": 5000,
            "items": [
                {"restaurant": "dushi-wok", "name": "Rice", "qty": 1, "price_cents": 1500},
                {"restaurant": "taco-brava", "name": "Taco", "qty": 1, "price_cents": 800},
            ],
        })],
        "MIN_FOOD",
    )
    check("mixed cart of ƒ15 + ƒ8 is refused", ok, detail)
    own_mix = place_items([
        {"restaurant": "dushi-wok", "name": "Rice", "qty": 1, "price_cents": 1500},
        {"restaurant": "taco-brava", "name": "Tacos", "qty": 1, "price_cents": 1200},
    ])
    own_subs = {row["slug"]: row["food_cents"] for row in own_mix["restaurants"]}
    check(
        "own-only mixed cart pays ƒ5",
        own_mix["food_cents"] == 2700 and own_mix["fee_cents"] == 500 and own_mix["total_cents"] == 3200,
        str(own_mix),
    )
    check(
        "per-restaurant subtotals are right",
        own_subs.get("dushi-wok") == 1500 and own_subs.get("taco-brava") == 1200,
        str(own_subs),
    )
    both = place_items([
        {"restaurant": "dushi-wok", "name": "Rice", "qty": 1, "price_cents": 1500},
        {"restaurant": "partner-test", "name": "Grill", "qty": 1, "price_cents": 1200},
    ], phone="2975990097")
    both_subs = {row["slug"]: row["food_cents"] for row in both["restaurants"]}
    check(
        "own plus partner pays ƒ10",
        both["fee_cents"] == 1000 and both["food_cents"] == 2700 and both_subs.get("partner-test") == 1200,
        str(both),
    )
    partner_only = place_items([
        {"restaurant": "partner-test", "name": "Grill", "qty": 1, "price_cents": 2500},
    ], phone="2975990096")
    check("partner-only pays ƒ10", partner_only["fee_cents"] == 1000 and partner_only["food_cents"] == 2500, str(partner_only))
    status = scalar(conn, "select public.pidi_order_status(%s)", [first["public_token"]])
    check("new order reads Received", status["label"] == "Received" and status["restaurant"] == "Dushi Wok")
    ok, detail = explodes(conn, "select public.pidi_order_status(%s)", ["nope"], "NOT_FOUND")
    check("wrong token is refused", ok, detail)

    refused = scalar(conn, "select public.pidi_admin_add_driver(%s, %s, %s, %s)", ["0000", "Ari", "2975550001", "2468"])
    check("wrong admin PIN is refused", refused.get("ok") is False and "does not match" in refused.get("error", "").lower(), str(refused))
    q(conn, "select public.pidi_admin_set_kitchen_pin(%s, %s)", ["42424242", "9999"])
    refused_kitchen = scalar(conn, "select public.pidi_kitchen_login(%s)", ["0000"])
    check(
        "wrong kitchen PIN is refused",
        refused_kitchen.get("ok") is False and "does not match" in refused_kitchen.get("error", "").lower(),
        str(refused_kitchen),
    )
    ari = scalar(conn, "select public.pidi_admin_add_driver(%s, %s, %s, %s)", ["42424242", "Ari", "2975550001", "2468"])
    bea = scalar(conn, "select public.pidi_admin_add_driver(%s, %s, %s, %s)", ["42424242", "Bea", "2975550002", "1357"])
    conn.commit()
    kitchen = scalar(conn, "select public.pidi_kitchen_login(%s)", ["9999"])
    check("kitchen login returns a token and a topic", bool(kitchen["token"]) and kitchen["topic"].startswith("pidi:k:"))
    q(conn, "reset role")
    q(conn, "update public.pidi_kitchen_sessions set expires_at = now() - interval '1 minute'")
    conn.commit()
    q(conn, "set role anon")
    ok, detail = explodes(conn, "select public.pidi_kitchen_feed(%s)", [kitchen["token"]], "sign in again")
    check("expired kitchen session is refused", ok, detail)
    kitchen = scalar(conn, "select public.pidi_kitchen_login(%s)", ["9999"])
    conn.commit()
    q(conn, "select public.pidi_kitchen_accept(%s, %s)", [kitchen["token"], first["order_id"]])
    q(conn, "select public.pidi_kitchen_set_status(%s, %s, 'cooking')", [kitchen["token"], first["order_id"]])
    cooking = scalar(conn, "select public.pidi_order_status(%s)", [first["public_token"]])
    check("cooking reads Cooking", cooking["label"] == "Cooking")
    ok, detail = explodes(
        conn,
        "select public.pidi_kitchen_set_status(%s, %s, 'delivered')",
        [kitchen["token"], first["order_id"]],
        "kitchen stops at Ready",
    )
    check("kitchen cannot mark delivered", ok, detail)
    q(conn, "select public.pidi_kitchen_set_status(%s, %s, 'ready')", [kitchen["token"], first["order_id"]])
    conn.commit()
    q(conn, "reset role")
    offered = scalar(conn, "select count(*) from public.pidi_runs where status = 'offered'")
    check("first ready order opens one run", offered == 1)
    q(conn, "set role anon")
    q(conn, "select public.pidi_kitchen_accept(%s, %s)", [kitchen["token"], second["order_id"]])
    q(conn, "select public.pidi_kitchen_set_status(%s, %s, 'cooking')", [kitchen["token"], second["order_id"]])
    q(conn, "select public.pidi_kitchen_set_status(%s, %s, 'ready')", [kitchen["token"], second["order_id"]])
    conn.commit()
    q(conn, "reset role")
    stops = scalar(conn, "select count(*) from public.pidi_run_orders")
    runs = scalar(conn, "select count(*) from public.pidi_runs")
    check("second nearby order pairs into the same run", stops == 2 and runs == 1)
    q(conn, "set role anon")
    login_ari = scalar(conn, "select public.pidi_driver_login(%s, %s)", ["Ari", "2468"])
    login_bea = scalar(conn, "select public.pidi_driver_login(%s, %s)", ["Bea", "1357"])
    q(conn, "select public.pidi_driver_set_online(%s, true)", [login_ari["token"]])
    q(conn, "select public.pidi_driver_set_online(%s, true)", [login_bea["token"]])
    offers_ari = scalar(conn, "select public.pidi_driver_offers(%s)", [login_ari["token"]])
    offers_bea = scalar(conn, "select public.pidi_driver_offers(%s)", [login_bea["token"]])
    conn.commit()
    check("both online drivers are offered the run", len(offers_ari) == 1 and len(offers_bea) == 1)
    old_ari = offers_ari[0]["offer_id"]
    old_bea = offers_bea[0]["offer_id"]
    q(conn, "reset role")
    q(conn, "update public.pidi_offers set expires_at = now() - interval '1 minute' where status = 'pending'")
    conn.commit()
    q(conn, "set role anon")
    ok, detail = explodes(conn, "select public.pidi_driver_accept(%s, %s)", [login_ari["token"], old_ari], "expired")
    check("a stale offer cannot be accepted", ok, detail)
    offers_ari = scalar(conn, "select public.pidi_driver_offers(%s)", [login_ari["token"]])
    offers_bea = scalar(conn, "select public.pidi_driver_offers(%s)", [login_bea["token"]])
    conn.commit()
    check("a stale offer is re-offered", len(offers_ari) == 1 and offers_ari[0]["offer_id"] != old_ari and len(offers_bea) == 1 and offers_bea[0]["offer_id"] != old_bea)
    check("an offer's stops carry the due time and order time",
          all(s.get("due_at") and s.get("created_at") for s in offers_ari[0]["stops"]), str(offers_ari)[:300])

    results = []

    def race(token, offer_id):
        other = psycopg2.connect(DSN)
        other.autocommit = True
        cur = other.cursor()
        try:
            cur.execute("set role anon")
            cur.execute("select public.pidi_driver_accept(%s, %s)", [token, offer_id])
            results.append(("ok", cur.fetchone()[0]))
        except psycopg2.Error as err:
            results.append(("err", err.diag.message_primary or str(err)))
        finally:
            other.close()

    threads = [
        threading.Thread(target=race, args=(login_ari["token"], offers_ari[0]["offer_id"])),
        threading.Thread(target=race, args=(login_bea["token"], offers_bea[0]["offer_id"])),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wins = [item for item in results if item[0] == "ok"]
    losses = [item for item in results if item[0] == "err"]
    check("one driver wins the race", len(wins) == 1 and len(losses) == 1, str(results))
    check("the other driver is told the run is taken", len(losses) == 1 and "took this run" in losses[0][1].lower(), str(results))
    q(conn, "reset role")
    winner_count = scalar(conn, "select count(distinct driver_id) from public.pidi_runs where status = 'active'")
    assigned = scalar(conn, "select count(*) from public.pidi_orders where status = 'assigned'")
    check("one driver owns the run and both orders are assigned", winner_count == 1 and assigned == 2)
    q(conn, "set role anon")
    run_ari = scalar(conn, "select public.pidi_driver_run(%s)", [login_ari["token"]])
    run_bea = scalar(conn, "select public.pidi_driver_run(%s)", [login_bea["token"]])
    winner = login_ari if run_ari else login_bea
    loser = login_bea if run_ari else login_ari
    won = run_ari or run_bea
    check("the other driver cannot read the run", (run_ari is None) != (run_bea is None))
    check("the run has two stops", won is not None and len(won["stops"]) == 2)
    check("each stop carries its night number, due time and order time",
          won is not None and all(s.get("night_no") and s.get("due_at") and s.get("created_at") for s in won["stops"]),
          str(won)[:300])
    check(
        "pickup lists a bag per restaurant",
        all(len(stop.get("bags") or []) == 1 and stop.get("fee_cents") == 500 for stop in won["stops"]),
        str(won["stops"]),
    )
    q(conn, "select public.pidi_driver_picked_up(%s, %s)", [winner["token"], won["run_id"]])
    for stop in won["stops"]:
        q(conn, "select public.pidi_driver_delivered(%s, %s)", [winner["token"], stop["order_id"]])
    conn.commit()
    ok, detail = explodes(
        conn,
        "select public.pidi_driver_delivered(%s, %s)",
        [loser["token"], won["stops"][0]["order_id"]],
        "not yours",
    )
    check("the other driver cannot mark delivered", ok, detail)
    done = scalar(conn, "select public.pidi_order_status(%s)", [first["public_token"]])
    done2 = scalar(conn, "select public.pidi_order_status(%s)", [second["public_token"]])
    check("status page reads Delivered", done["label"] == "Delivered" and done2["label"] == "Delivered")
    check("status page uses the computed fee", done["fee_cents"] == 500 and done2["fee_cents"] == 500)
    q(conn, "reset role")
    picked = scalar(conn, "select count(*) from public.pidi_order_events where status = 'picked_up'")
    check("picked up was logged", picked == 2)
    pins = scalar(conn, "select count(*) from public.pidi_drivers where pin_hash ~ '^[0-9]+$'")
    check("only PIN hashes are stored", pins == 0)
    logs = q(conn, "select payload::text, event, topic, private from public.bookkeeping_realtime_log")
    pii = [row for row in logs if "Maria" in row[0] or "5990001" in row[0] or "Weg" in row[0]]
    check("broadcast payload is only a ping", logs and not pii and all(row[1] == "changed" and row[3] is False and row[0] == '{"ping": "changed"}' for row in logs), str(logs[:3]))
    check("broadcast topics are pidi topics", all(row[2].startswith("pidi:") for row in logs))
    check("bookkeeping row still untouched", scalar(conn, "select note from public.bookkeeping_dummy") == "do not touch")
    check("bookkeeping policy still the only one", scalar(conn, "select polname from pg_policy p join pg_class c on c.oid = p.polrelid where c.relname = 'bookkeeping_dummy'") == "bookkeeping_dummy_keep")

    q(conn, "set role anon")
    bag = place_items([
        {"restaurant": "smash-shack", "name": "Burger", "qty": 1, "price_cents": 1600},
        {"restaurant": "oranje-snack", "name": "Bitterballen", "qty": 1, "price_cents": 1100},
    ], phone="2975990095", name="Bags TEST")
    q(conn, "select public.pidi_kitchen_accept(%s, %s)", [kitchen["token"], bag["order_id"]])
    q(conn, "select public.pidi_kitchen_set_status(%s, %s, 'cooking')", [kitchen["token"], bag["order_id"]])
    one_bag = scalar(conn, "select public.pidi_kitchen_mark_ready(%s, %s, %s)", [kitchen["token"], bag["order_id"], "smash-shack"])
    conn.commit()
    q(conn, "reset role")
    still = scalar(conn, "select status::text from public.pidi_orders where id = %s", [bag["order_id"]])
    bag_runs = scalar(conn, "select count(*) from public.pidi_run_orders where order_id = %s", [bag["order_id"]])
    check(
        "one bag ready does not dispatch",
        one_bag.get("status") == "cooking" and still == "cooking" and bag_runs == 0,
        str(one_bag) + " " + str(still),
    )
    q(conn, "set role anon")
    both_bags = scalar(conn, "select public.pidi_kitchen_mark_ready(%s, %s, %s)", [kitchen["token"], bag["order_id"], "oranje-snack"])
    conn.commit()
    q(conn, "reset role")
    ready_now = scalar(conn, "select status::text from public.pidi_orders where id = %s", [bag["order_id"]])
    bag_runs = scalar(conn, "select count(*) from public.pidi_run_orders where order_id = %s", [bag["order_id"]])
    check(
        "all bags ready sends the order",
        both_bags.get("status") == "ready" and ready_now == "ready" and bag_runs == 1,
        str(both_bags),
    )
    q(conn, "set role anon")
    feed = scalar(conn, "select public.pidi_kitchen_feed(%s)", [kitchen["token"]])
    grouped = next((order for order in feed["orders"] if str(order["id"]) == str(bag["order_id"])), None)
    names = sorted(group["restaurant"] for group in (grouped or {}).get("restaurants") or [])
    check("kitchen feed groups by restaurant", names == ["Oranje Snack", "Smash Shack"], str(names))
    check("kitchen feed says when the order is due", bool((grouped or {}).get("due_at")), str(grouped)[:200])

    same_a = place_items([{"restaurant": "dushi-wok", "name": "Rice", "qty": 2, "price_cents": 1500}],
                         phone="2975990094", name="Twice TEST")
    body = {"name": "Twice TEST", "phone": "2975990093", "area": "Noord", "address": "TEST", "pay": "transfer",
            "client_token": "test-client-token-1", "test": True,
            "items": [{"restaurant": "dushi-wok", "name": "Rice", "qty": 2, "price_cents": 1500}]}
    once = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])
    again = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])
    conn.commit()
    check("same client token returns the same order", once["order_id"] == again["order_id"] and same_a["order_id"] != once["order_id"])
    check("status tells the customer how they pay", once.get("pay") == "transfer" and once.get("transfer_status") == "awaiting", str(once))

    q(conn, "reset role")
    q(conn, "update public.pidi_settings set value = 'reject' where key = 'hours_mode'")
    tonight = scalar(conn, """
        select ((date_trunc('day', now() at time zone 'America/Aruba')
                 + case when (now() at time zone 'America/Aruba')::time < time '22:00'
                        then interval '23 hours' else interval '25 hours' end)
                at time zone 'America/Aruba')::text
    """)
    afternoon = scalar(conn, """
        select ((date_trunc('day', now() at time zone 'America/Aruba')
                 + case when (now() at time zone 'America/Aruba')::time < time '15:00'
                        then interval '15 hours' else interval '39 hours' end)
                at time zone 'America/Aruba')::text
    """)
    conn.commit()
    q(conn, "set role anon")
    pre = dict(body, client_token=None, due_at=tonight, phone="2975990092")
    pre_row = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(pre)])
    conn.commit()
    check("a pre-order for later tonight is taken in any hour", bool(pre_row.get("order_id")), str(pre_row))
    ok, detail = explodes(conn, "select public.pidi_place_order(%s::jsonb)",
                          [json.dumps(dict(pre, due_at=afternoon))], "BAD_TIME")
    check("a delivery time in the afternoon is refused", ok, detail)
    conn.commit()
    q(conn, "reset role")
    q(conn, "update public.pidi_settings set value = 'flag' where key = 'hours_mode'")
    conn.commit()
    q(conn, "set role anon")

    near = place_items([{"restaurant": "nonnas-night-in", "name": "Penne", "qty": 2, "price_cents": 1400}],
                       phone="2975990091", name="Near TEST")
    for step in ("accepted", "cooking", "ready"):
        if step == "accepted":
            q(conn, "select public.pidi_kitchen_accept(%s, %s)", [kitchen["token"], near["order_id"]])
        else:
            q(conn, "select public.pidi_kitchen_set_status(%s, %s, %s)", [kitchen["token"], near["order_id"], step])
    conn.commit()
    q(conn, "reset role")
    shared = scalar(conn, """
        select count(*) from public.pidi_run_orders a join public.pidi_run_orders b on a.run_id = b.run_id
        where a.order_id = %s and b.order_id = %s
    """, [bag["order_id"], near["order_id"]])
    conn.commit()
    check("a nearby ready order joins the offered run", shared == 1)
    q(conn, "set role anon")
    gone_bag = scalar(conn, "select public.pidi_kitchen_cancel(%s, %s)", [kitchen["token"], bag["order_id"]])
    conn.commit()
    q(conn, "reset role")
    near_runs = q(conn, """
        select r.status::text, (select count(*) from public.pidi_run_orders x where x.run_id = r.id)
        from public.pidi_run_orders ro join public.pidi_runs r on r.id = ro.run_id where ro.order_id = %s
    """, [near["order_id"]])
    bag_left = q(conn, """
        select r.status::text from public.pidi_run_orders ro join public.pidi_runs r on r.id = ro.run_id
        where ro.order_id = %s
    """, [bag["order_id"]])
    conn.commit()
    check("cancel takes the order off its run", gone_bag.get("status") == "cancelled" and bag_left == [("cancelled",)], str(gone_bag) + str(bag_left))
    check("the other order is offered again on its own", near_runs == [("offered", 1)], str(near_runs))
    q(conn, "set role anon")
    told = scalar(conn, "select public.pidi_order_status(%s)", [bag["public_token"]])
    check("the customer sees Cancelled", told["label"] == "Cancelled", str(told.get("label")))
    ok, detail = explodes(conn, "select public.pidi_kitchen_cancel(%s, %s)", [kitchen["token"], first["order_id"]], "driver has this order")
    check("a delivered order cannot be cancelled", ok, detail)
    ok, detail = explodes(conn, "select public.pidi_kitchen_cancel(%s, %s)", ["x" * 64, near["order_id"]], "sign in again")
    check("cancel needs a kitchen session", ok, detail)
    paid = scalar(conn, "select public.pidi_kitchen_transfer_paid(%s, %s)", [kitchen["token"], once["order_id"]])
    conn.commit()
    check("transfer can be marked received", paid.get("transfer_status") == "paid")
    ok, detail = explodes(conn, "select public.pidi_kitchen_transfer_paid(%s, %s)", [kitchen["token"], first["order_id"]], "not a bank transfer")
    check("a cash order is not a transfer", ok, detail)
    conn.commit()

    # --- what the status page gets, and nothing private
    st = scalar(conn, "select public.pidi_order_status(%s)", [once["public_token"]])
    blob = json.dumps(st)
    check("status carries items, events, first name, area and the window",
          len(st.get("items") or []) == 1 and len(st.get("events") or []) >= 1 and st.get("first_name") == "Twice"
          and st.get("area") == "Noord" and st.get("eta_min") and st.get("eta_max") and st.get("night_no"), blob[:300])
    check("status never carries the phone, address or note",
          "5990093" not in blob and "TEST" not in json.dumps({k: v for k, v in st.items() if k not in ("first_name", "items", "restaurant", "restaurants")})
          and "address" not in st and "phone" not in st and "note" not in st, blob[:300])
    check("transfer received is timed", bool(st.get("transfer_paid_at")) and st.get("transfer_status") == "paid", blob[:200])
    found = scalar(conn, "select public.pidi_find_order(%s)", ["test-client-token-1"])
    nothing = scalar(conn, "select public.pidi_find_order(%s)", ["never-used-token"])
    check("find_order answers by token and never inserts", found and found["order_id"] == once["order_id"] and nothing is None, str(found)[:120])

    # --- error codes, never English text
    def code_of(body):
        q(conn, "SAVEPOINT pidi_code")
        try:
            q(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])
        except psycopg2.Error as err:
            q(conn, "ROLLBACK TO SAVEPOINT pidi_code")
            return err.diag.message_primary
        q(conn, "RELEASE SAVEPOINT pidi_code")
        return "no error"
    good = {"name": "Code TEST", "phone": "2975990080", "area": "Noord", "address": "TEST", "pay": "cash", "pays_with_cents": 5000,
            "items": [{"restaurant": "dushi-wok", "name": "Rice", "qty": 2, "price_cents": 1500}]}
    cases = [
        ("BAD_PAYLOAD", None),
        ("MISSING", dict(good, name="")),
        ("BAD_PHONE", dict(good, phone="12")),
        ("NO_ITEMS", dict(good, items=[])),
        ("BAD_ITEM:1", dict(good, items=good["items"] + [{"restaurant": "dushi-wok", "name": "Rice", "qty": "two", "price_cents": 100}])),
        ("REST_CLOSED:nowhere", dict(good, items=[{"restaurant": "nowhere", "name": "Rice", "qty": 2, "price_cents": 1500}])),
        ("CASH_SHORT", dict(good, pays_with_cents=1000)),
        ("CASH_SHORT", dict(good, pays_with_cents="lots")),
        ("BAD_PAY", dict(good, pay="card")),
        ("BAD_PIN", dict(good, lat="north", lng="-70")),
        ("BAD_TIME", dict(good, due_at="tonight")),
        ("DELIVERY_ONLY", dict(good, pickup=True)),
    ]
    for want, body in cases:
        got = code_of(body) if body is not None else None
        if body is None:
            q(conn, "SAVEPOINT pidi_code")
            try:
                q(conn, "select public.pidi_place_order('[]'::jsonb)")
                got = "no error"
            except psycopg2.Error as err:
                q(conn, "ROLLBACK TO SAVEPOINT pidi_code")
                got = err.diag.message_primary
        check("error code " + want, got == want, str(got))
    conn.commit()

    # --- the same token after a rule change still returns the order (no refusal)
    q(conn, "reset role")
    q(conn, "update public.pidi_settings set value = '99999' where key = 'min_food_cents'")
    conn.commit()
    q(conn, "set role anon")
    after = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body_retry := dict(body, client_token="test-client-token-1"))])
    conn.commit()
    check("a retry with the same token returns the order after a rule change", after["order_id"] == once["order_id"])
    q(conn, "reset role")
    q(conn, "update public.pidi_settings set value = '2400' where key = 'min_food_cents'")
    conn.commit()
    q(conn, "set role anon")

    # --- US dollars, night numbers, busy minutes
    usd = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(dict(good, phone="2975990081", pays_in_usd=True, pays_with_cents=None))])
    conn.commit()
    check("US dollars: stored, no change line", usd.get("pays_in_usd") is True and usd.get("change_due_cents") == 0, str(usd)[:200])
    busy = scalar(conn, "select public.pidi_kitchen_set_busy(%s, 15)", [kitchen["token"]])
    state = scalar(conn, "select public.pidi_public_state()")
    slow = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(dict(good, phone="2975990082"))])
    scalar(conn, "select public.pidi_kitchen_set_busy(%s, 0)", [kitchen["token"]])
    conn.commit()
    check("busy adds 15 minutes to the promise", busy.get("busy_min") == 15 and state.get("busy_min") == 15
          and slow["eta_min"] == usd["eta_min"] + 15 and slow["eta_max"] == usd["eta_max"] + 15, str(state))
    check("night numbers count up", slow["night_no"] == usd["night_no"] + 1, f'{usd["night_no"]} {slow["night_no"]}')
    # A pre-order placed before noon (yesterday's service night) for tonight joins tonight's numbers.
    q(conn, "reset role")
    q(conn, "update public.pidi_orders set created_at = now() - interval '20 hours', night_no = 50 where id = %s", [slow["order_id"]])
    conn.commit()
    q(conn, "set role anon")
    joined = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(dict(good, phone="2975990085"))])
    conn.commit()
    check("night number follows the delivery night, not the order time", joined["night_no"] == 51, str(joined.get("night_no")))
    ok, detail = explodes(conn, "select public.pidi_kitchen_set_busy(%s, 7)", [kitchen["token"]], "0, 15 or 30")
    check("busy only takes 0, 15 or 30", ok, detail)
    ok, detail = explodes(conn, "select public.pidi_kitchen_set_busy(%s, 15)", ["x" * 64], "sign in again")
    check("busy needs a kitchen session", ok, detail)
    feed2 = scalar(conn, "select public.pidi_kitchen_feed(%s)", [kitchen["token"]])
    kusd = next((o for o in feed2["orders"] if str(o["id"]) == str(usd["order_id"])), {})
    check("kitchen sees USD and the night number", kusd.get("pays_in_usd") is True and kusd.get("night_no") == usd["night_no"], str(kusd)[:200])

    # --- one phone can't flood the kitchen
    flood = dict(good, phone="297 599 0083")
    scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(flood)])
    scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(dict(flood, phone="5990083"))])
    conn.commit()
    check("a third waiting order from one phone is refused", code_of(dict(flood, phone="+297-599-0083")) == "RATE_LIMIT")
    conn.commit()
    listed = scalar(conn, "select public.pidi_admin_list_drivers(%s)", ["42424242"])
    blob = json.dumps(listed)
    check("driver list has no PIN hash", listed.get("ok") is True and "pin_hash" not in blob and "$2" not in blob, blob[:240])
    check("driver list names Ari and Bea", {row["name"] for row in listed["drivers"]} >= {"Ari", "Bea"}, blob)
    cara = scalar(conn, "select public.pidi_admin_add_driver(%s, %s, %s, %s)", ["42424242", "Cara", "2975550003", "1212"])
    conn.commit()
    q(conn, "reset role")
    q(conn, "insert into public.pidi_runs (status, driver_id) values ('active', %s)", [cara["driver_id"]])
    conn.commit()
    q(conn, "set role anon")
    blocked = scalar(conn, "select public.pidi_admin_remove_driver(%s, %s)", ["42424242", cara["driver_id"]])
    check("a driver on a run is not removed", blocked.get("ok") is False and "on a run" in blocked.get("error", "").lower(), str(blocked))
    q(conn, "reset role")
    q(conn, "update public.pidi_runs set status = 'done' where driver_id = %s and status = 'active'", [cara["driver_id"]])
    conn.commit()
    q(conn, "set role anon")
    gone = scalar(conn, "select public.pidi_admin_remove_driver(%s, %s)", ["42424242", cara["driver_id"]])
    conn.commit()
    q(conn, "reset role")
    still_active = scalar(conn, "select active from public.pidi_drivers where id = %s", [cara["driver_id"]])
    sessions = scalar(conn, "select count(*) from public.pidi_driver_sessions where driver_id = %s and expires_at > now()", [cara["driver_id"]])
    check("removed driver is deactivated", gone.get("ok") is True and still_active is False and sessions == 0, str(gone))
    q(conn, "set role anon")
    listed = scalar(conn, "select public.pidi_admin_list_drivers(%s)", ["42424242"])
    listed_names = {row["name"] for row in listed["drivers"]}
    check("removed driver is off the list", "Cara" not in listed_names and "Ari" in listed_names, str(listed_names))

    q(conn, "reset role")
    q(conn, "set role anon")
    conn.commit()
    sixth = ""
    for n in range(1, 7):
        row = scalar(
            conn,
            "select public.pidi_admin_add_driver(%s, %s, %s, %s)",
            ["00000000", "Nope", "2975550099", "2468"],
        )
        conn.commit()
        detail = (row or {}).get("error", "")
        if n < 6:
            check("wrong admin PIN %s" % n, row.get("ok") is False and "does not match" in detail.lower(), detail)
        else:
            check("six wrong admin PINs lock it", row.get("ok") is False and "too many tries" in detail.lower(), detail)
        sixth = detail
    row = scalar(
        conn,
        "select public.pidi_admin_add_driver(%s, %s, %s, %s)",
        ["42424242", "Nope", "2975550099", "2468"],
    )
    conn.commit()
    detail = (row or {}).get("error", "")
    check("right admin PIN refused during lockout", row.get("ok") is False and "too many tries" in detail.lower(), detail)
    listed_locked = scalar(conn, "select public.pidi_admin_list_drivers(%s)", ["42424242"])
    conn.commit()
    check(
        "admin list is refused during lockout",
        listed_locked.get("ok") is False and "too many tries" in listed_locked.get("error", "").lower(),
        str(listed_locked),
    )
    check("lockout message is the five minute wait", "wait 5 minutes" in sixth.lower() and "wait 5 minutes" in detail.lower(), sixth + " / " + detail)

    def pin_lock(label, sql, wrong, right):
        sixth_msg = ""
        for n in range(1, 7):
            row = scalar(conn, sql, wrong)
            conn.commit()
            detail = (row or {}).get("error", "")
            if n < 6:
                check("wrong %s PIN %s" % (label, n), row.get("ok") is False and "does not match" in detail.lower(), detail)
            else:
                check("six wrong %s PINs lock it" % label, row.get("ok") is False and "too many tries" in detail.lower(), detail)
            sixth_msg = detail
        row = scalar(conn, sql, right)
        conn.commit()
        detail = (row or {}).get("error", "")
        check("right %s PIN refused during lockout" % label, row.get("ok") is False and "too many tries" in detail.lower(), detail)
        check("%s lockout message is the five minute wait" % label, "wait 5 minutes" in sixth_msg.lower() and "wait 5 minutes" in detail.lower(), sixth_msg + " / " + detail)

    pin_lock("kitchen", "select public.pidi_kitchen_login(%s)", ["0000"], ["9999"])
    pin_lock("driver", "select public.pidi_driver_login(%s, %s)", ["Ari", "0000"], ["Ari", "2468"])
    bea_still = scalar(conn, "select public.pidi_driver_login(%s, %s)", ["Bea", "1357"])
    conn.commit()
    check(
        "a different driver is not locked",
        bool(bea_still.get("token")) and bea_still.get("ok") is True,
        str(bea_still),
    )

    seed_when_placeholder_replaced()

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
