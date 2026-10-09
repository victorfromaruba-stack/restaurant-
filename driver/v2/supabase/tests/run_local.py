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
    check("no admin PIN stored by the paste", scalar(conn, "select value from public.pidi_settings where key = 'admin_pin_hash'") is None)

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
    conn.commit()

    q(conn, "set role anon")
    ok, detail = explodes(conn, "select public.pidi_dispatch()", None, "permission denied")
    check("anon cannot call dispatch directly", ok, detail)
    ok, detail = explodes(
        conn,
        "select public.pidi_place_order(%s::jsonb)",
        ['{"restaurant":"dushi-wok","name":"A","phone":"2975550001","area":"Noord","address":"1","pay":"cash","pays_with_cents":5000,"items":[{"name":"Fries","qty":1,"price_cents":100}]}'],
        "minimum",
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
    status = scalar(conn, "select public.pidi_order_status(%s)", [first["public_token"]])
    check("new order reads Received", status["label"] == "Received" and status["restaurant"] == "Dushi Wok")
    ok, detail = explodes(conn, "select public.pidi_order_status(%s)", ["nope"], "can't find")
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

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
