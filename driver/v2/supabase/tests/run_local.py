#!/usr/bin/env python3
"""Apply PIDI_SETUP.sql twice on a throwaway Postgres and run the order flow as anon.

The database is local. Nothing here contacts Supabase. Also: prices from the database (pidi_menu, filled
with the repo's own menu.json files), and the paste files for the live database (PIN_FIX, SETTINGS,
MENU_PRICES): the live database's setup plus those pastes ends up the same as a fresh install of
PIDI_SETUP.sql, and in any other project each paste stops at its first check and changes nothing.

Local Postgres (lessons.md): a cluster under /var/lib/postgresql/<name>, socket /var/run/postgresql. Point
PGPORT and PGUSER at it (for example PGPORT=5499 PGUSER=postgres).
"""

import json
import os
import re
import subprocess
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
    "pidi_kitchen_sync_menu(text,text,text,jsonb,boolean)",
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


REPO = ROOT.parents[2]
PASTES = ["PIN_FIX_2026-10-16.sql", "SETTINGS_2026-10-16.sql", "MENU_PRICES_2026-10-16.sql"]
# The database as it is live (before 16 Oct 2026): PIDI_SETUP.sql at this commit. The upgrade test needs it.
LIVE_SETUP_COMMIT = "76cdd53"


def menu_rows(menu):
    """What the kitchen app sends pidi_kitchen_sync_menu: menu.json's items, only the fields pricing needs."""
    rows = []
    for i in menu["items"]:
        rows.append({
            "id": i["id"], "name": i["name"], "price": i["price"], "soldOut": bool(i.get("soldOut")),
            "includes": i.get("includes") or [],
            "options": [{"id": g["id"], "label": g.get("label", ""), "type": g["type"], "default": g.get("default"),
                         "choices": [{"id": c["id"], "label": c["label"], "price": c.get("price") or 0} for c in g["choices"]]}
                        for g in i.get("options") or []],
        })
    return rows


def describe(item, chosen):
    """The website's words for chosen options (order-app.js describe()): the ticket line is the dish name and these, joined by ' · '."""
    out = []
    for g in item.get("options") or []:
        v = chosen.get(g["id"])
        if g["type"] == "one":
            if v and v != g.get("default"):
                c = next((x for x in g["choices"] if x["id"] == v), None)
                if c:
                    out.append(g["label"] + ": " + c["label"])
        elif isinstance(v, list) and v:
            labels = [c["label"] for c in g["choices"] if c["id"] in v]
            if g["id"] == "leave":
                out += labels
            else:
                out.append(g["label"] + ": " + ", ".join(labels))
    return out


def variants(item):
    """Every way the website can send a dish: as it comes, each other choice of a one-choice option, each
    choice of a many-choice option on its own, and all of them at once. (chosen options, extra cents)"""
    out = [({}, 0)]
    for g in item.get("options") or []:
        if g["type"] == "one":
            for c in g["choices"]:
                if c["id"] != g.get("default"):
                    out.append(({g["id"]: c["id"]}, c.get("price") or 0))
        else:
            for c in g["choices"]:
                out.append(({g["id"]: [c["id"]]}, c.get("price") or 0))
            if len(g["choices"]) > 1:
                out.append(({g["id"]: [c["id"] for c in g["choices"]]}, sum(c.get("price") or 0 for c in g["choices"])))
    return out


def menu_prices(conn, token):
    """Prices come from the database: pidi_menu, filled by the kitchen app (pidi_kitchen_sync_menu)."""
    phone = [7700000]

    def next_phone():
        phone[0] += 1
        return "29" + str(phone[0])

    def order(items, pay="transfer", pays=None, **more):
        body = {"name": "Menu TEST", "phone": next_phone(), "area": "Noord", "address": "TEST", "pay": pay,
                "items": items, "test": True}
        if pays is not None:
            body["pays_with_cents"] = pays
        body.update(more)
        return body

    def place(body):
        return scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])

    def attempt(body):
        q(conn, "SAVEPOINT pidi_menu_try")
        try:
            row = scalar(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])
        except psycopg2.Error as err:
            q(conn, "ROLLBACK TO SAVEPOINT pidi_menu_try")
            return None, err.diag.message_primary
        q(conn, "RELEASE SAVEPOINT pidi_menu_try")
        return row, None

    def code(body):
        q(conn, "SAVEPOINT pidi_menu_code")
        try:
            q(conn, "select public.pidi_place_order(%s::jsonb)", [json.dumps(body)])
        except psycopg2.Error as err:
            q(conn, "ROLLBACK TO SAVEPOINT pidi_menu_code")
            return err.diag.message_primary
        q(conn, "RELEASE SAVEPOINT pidi_menu_code")
        return "no error"

    def sync(slug, status, items, from_save=False, session=None):
        row = scalar(conn, "select public.pidi_kitchen_sync_menu(%s, %s, %s, %s::jsonb, %s)",
                     [session or token, slug, status, None if items is None else json.dumps(items), from_save])
        conn.commit()
        return row

    def owner(sql, args=None):
        q(conn, "reset role")
        rows = q(conn, sql, args)
        conn.commit()
        q(conn, "set role anon")
        return rows

    site = json.loads((REPO / "shared" / "site.json").read_text(encoding="utf-8"))
    menus = {b["id"]: json.loads((REPO / b["id"] / "menu.json").read_text(encoding="utf-8")) for b in site["brands"]}
    check("the repo's menus are here for the menu tests", set(menus) >= {"taco-brava", "oranje-snack", "smash-shack"}, str(list(menus)))

    # --- who may send a menu, and what it must look like
    ok, detail = explodes(conn, "select public.pidi_kitchen_sync_menu(%s, %s, %s, %s::jsonb, %s)",
                          ["x" * 64, "taco-brava", "open", json.dumps(menu_rows(menus["taco-brava"])), False], "sign in again")
    check("sending a menu needs a kitchen session", ok, detail)
    conn.commit()
    nowhere = sync("nowhere", "open", menu_rows(menus["taco-brava"]))
    check("a restaurant the database doesn't know is answered, not raised", nowhere.get("ok") is False, str(nowhere))
    tb_rows = menu_rows(menus["taco-brava"])
    for label, items, needle in [
        ("a price like 12.95", [dict(tb_rows[0], price=12.95)], "can't be read"),
        ("the same dish twice", [tb_rows[0], tb_rows[0]], "can't be read"),
        ("no dishes", [], "no dishes"),
        ("an option price like 1.50", [dict(tb_rows[0], options=[{"id": "x", "label": "Add", "type": "many",
                                                                    "choices": [{"id": "y", "label": "Cheese", "price": 1.5}]}])], "can't be read"),
        ("an option without choices", [dict(tb_rows[0], options=[{"id": "x", "label": "Add", "type": "many"}])], "can't be read"),
    ]:
        ok, detail = explodes(conn, "select public.pidi_kitchen_sync_menu(%s, %s, %s, %s::jsonb, %s)",
                              [token, "taco-brava", "open", json.dumps(items), False], needle)
        check("a menu with %s is refused" % label, ok, detail)
        conn.commit()
    ok, detail = explodes(conn, "select public.pidi_kitchen_sync_menu(%s, %s, %s, %s::jsonb, %s)",
                          [token, "taco-brava", "closed", json.dumps(tb_rows), False], "open, soon or hidden")
    check("a status other than open, soon or hidden is refused", ok, detail)
    conn.commit()
    ok, detail = explodes(conn, "select count(*) from public.pidi_menu", None, "permission denied")
    check("anon select on the menu is denied", ok, detail)
    conn.commit()

    # --- a restaurant with no menu rows yet keeps the phone's price (today's rule)
    before = place(order([{"restaurant": "taco-brava", "name": "Birria tacos (3) with consommé", "qty": 1, "price_cents": 100}]))
    conn.commit()
    check("no menu rows yet: the phone's price is kept, as before", before["food_cents"] == 100 and before.get("repriced") is False, str(before)[:200])

    # --- every restaurant's real menu, open
    for slug, menu in menus.items():
        got = sync(slug, "open", menu_rows(menu))
        check("%s's menu is taken (%s dishes)" % (slug, len(menu["items"])), got.get("ok") is True and got.get("items") == len(menu["items"]), str(got))
    stored = owner("select count(*) from public.pidi_menu")[0][0]
    check("one row per dish", stored == sum(len(m["items"]) for m in menus.values()), str(stored))

    # --- a client that sends a wrong price gets the menu's price
    bt = next(i for i in menus["taco-brava"]["items"] if i["id"] == "bt")
    wrong = place(order([{"restaurant": "taco-brava", "name": bt["name"] + " · No onion", "qty": 2, "price_cents": 100}]))
    conn.commit()
    check("a wrong price from the phone is replaced by the menu's",
          wrong["food_cents"] == 2 * bt["price"] and wrong["total_cents"] == 2 * bt["price"] + 500 and wrong.get("repriced") is True,
          str(wrong)[:300])
    check("the order's line carries the menu's price and words",
          wrong["items"] == [{"restaurant": "taco-brava", "name": bt["name"] + " · No onion", "qty": 2, "price_cents": bt["price"]}],
          str(wrong["items"]))
    right = place(order([{"restaurant": "taco-brava", "name": bt["name"], "qty": 1, "price_cents": bt["price"]}]))
    conn.commit()
    check("the right price is not flagged as changed", right["food_cents"] == bt["price"] and right.get("repriced") is False, str(right)[:200])
    no_price = place(order([{"restaurant": "taco-brava", "name": bt["name"], "qty": 1}]))
    conn.commit()
    check("a line with no price is priced from the menu", no_price["food_cents"] == bt["price"] and no_price.get("repriced") is False, str(no_price)[:200])
    feed = scalar(conn, "select public.pidi_kitchen_feed(%s)", [token])
    conn.commit()
    k = next((o for o in feed["orders"] if str(o["id"]) == str(wrong["order_id"])), {})
    k_items = [i for g in (k.get("restaurants") or []) for i in g["items"]]
    check("the kitchen sees the menu's price, not the phone's", k_items and all(i["price_cents"] == bt["price"] for i in k_items), str(k_items))
    # cash: what the customer hands over is judged against the menu's total
    check("cash that covers only the phone's wrong total is CASH_SHORT",
          code(order([{"restaurant": "taco-brava", "name": bt["name"], "qty": 1, "price_cents": 100}], pay="cash", pays=600)) == "CASH_SHORT")
    conn.commit()
    cash = place(order([{"restaurant": "taco-brava", "name": bt["name"], "qty": 1, "price_cents": 100}], pay="cash", pays=5000))
    conn.commit()
    check("change is worked out from the menu's total", cash["change_due_cents"] == 5000 - bt["price"] - 500, str(cash)[:200])

    # --- by menu id; the words in any case; the menu's own name is stored
    by_id = place(order([{"restaurant": "taco-brava", "id": "bt", "name": "Old name of the dish · No cilantro", "qty": 1, "price_cents": 1}]))
    conn.commit()
    check("a line with the menu id is priced from that dish, under the menu's name",
          by_id["items"][0]["name"] == bt["name"] + " · No cilantro" and by_id["food_cents"] == bt["price"], str(by_id["items"]))
    loose = place(order([{"restaurant": "taco-brava", "name": "  BIRRIA tacos (3)   with consommé · no ONION ", "qty": 1}]))
    conn.commit()
    check("capitals and extra spaces don't matter; the menu's spelling is stored",
          loose["items"][0]["name"] == bt["name"] + " · no ONION" and loose["food_cents"] == bt["price"], str(loose["items"]))

    # --- refusals, with the short codes the website turns into sentences
    good_line = {"restaurant": "taco-brava", "name": bt["name"], "qty": 1, "price_cents": bt["price"]}
    for want, line in [
        ("BAD_ITEM:1", {"restaurant": "taco-brava", "name": "Lobster tacos", "qty": 1, "price_cents": 100}),
        ("BAD_ITEM:1", {"restaurant": "taco-brava", "id": "zz", "name": bt["name"], "qty": 1}),
        ("BAD_ITEM:1", {"restaurant": "taco-brava", "name": bt["name"] + " · Extra steak", "qty": 1}),
        ("BAD_ITEM:1", {"restaurant": "taco-brava", "name": "Ground beef street tacos (3) · Salsa: On top, On the side", "qty": 1}),
        ("BAD_ITEM:1", {"restaurant": "taco-brava", "name": "Ground beef street tacos (3) · Salsa: Extra hot", "qty": 1}),
        ("BAD_ITEM:1", {"restaurant": "taco-brava", "name": bt["name"] + " ·  · No onion", "qty": 1}),
    ]:
        got = code(order([good_line, line]))
        check("refused %s: %s" % (want, line["name"][:50]), got == want, got)
    conn.commit()

    # --- sold out: the dish, and a bundle holding it
    lb = next(i for i in menus["taco-brava"]["items"] if i["id"] == "lb")
    rows = [dict(r, soldOut=True) if r["id"] == "lb" else r for r in tb_rows]
    sync("taco-brava", "open", rows, from_save=True)
    check("a sold-out dish is refused with SOLD_OUT",
          code(order([good_line, {"restaurant": "taco-brava", "name": lb["name"], "qty": 1, "price_cents": lb["price"]}])) == "SOLD_OUT:1")
    conn.commit()
    sync("taco-brava", "open", tb_rows, from_save=True)
    back = place(order([{"restaurant": "taco-brava", "name": lb["name"], "qty": 1}]))
    conn.commit()
    check("back on: it can be ordered again", back["food_cents"] == lb["price"], str(back)[:120])
    dw = menus["dushi-wok"]
    ft = next((i for i in dw["items"] if i.get("includes")), None)
    if ft:
        part = ft["includes"][0]
        dw_rows = [dict(r, soldOut=True) if r["id"] == part else r for r in menu_rows(dw)]
        sync("dushi-wok", "open", dw_rows, from_save=True)
        check("a bundle holding a sold-out dish is SOLD_OUT (like the website)",
              code(order([{"restaurant": "dushi-wok", "name": ft["name"], "qty": 1}])) == "SOLD_OUT:0")
        conn.commit()
        sync("dushi-wok", "open", menu_rows(dw), from_save=True)

    # --- the restaurant's own status from site.json
    sync("dushi-wok", "soon", None, from_save=True)
    fr = dw["items"][1]
    check("a restaurant set to Opening soon takes no orders (REST_CLOSED)",
          code(order([{"restaurant": "dushi-wok", "name": fr["name"], "qty": 1}])) == "REST_CLOSED:dushi-wok")
    conn.commit()
    kept = owner("select count(*) from public.pidi_menu m join public.pidi_restaurants r on r.id = m.restaurant_id where r.slug = 'dushi-wok' and m.listed")[0][0]
    check("a status-only update keeps the dishes", kept == len(dw["items"]), str(kept))
    sync("dushi-wok", "open", None, from_save=True)
    check("open again: it takes orders", place(order([{"restaurant": "dushi-wok", "name": fr["name"], "qty": 1}]))["food_cents"] == fr["price"])
    conn.commit()

    # --- an older copy from the website never undoes a Menu-tile save made in the last 15 minutes
    up = [dict(r, price=r["price"] + 100) if r["id"] == "bt" else r for r in tb_rows]
    sync("taco-brava", "open", up, from_save=True)
    stale = sync("taco-brava", "open", tb_rows, from_save=False)
    price_now = place(order([{"restaurant": "taco-brava", "name": bt["name"], "qty": 1}]))["food_cents"]
    conn.commit()
    check("a website copy right after a save is skipped; the saved price holds",
          stale.get("skipped") is True and price_now == bt["price"] + 100, "%s %s" % (stale, price_now))
    owner("update public.pidi_restaurants set menu_saved_at = now() - interval '16 minutes' where slug = 'taco-brava'")
    later = sync("taco-brava", "open", tb_rows, from_save=False)
    price_now = place(order([{"restaurant": "taco-brava", "name": bt["name"], "qty": 1}]))["food_cents"]
    conn.commit()
    check("after 15 minutes the website's copy is taken", later.get("skipped") is False and price_now == bt["price"], "%s %s" % (later, price_now))

    # --- a dish taken off the menu: refused, its row kept (nothing is removed)
    sync("taco-brava", "open", [r for r in tb_rows if r["id"] != "st"], from_save=True)
    st = next(i for i in menus["taco-brava"]["items"] if i["id"] == "st")
    check("a dish taken off the menu is refused", code(order([{"restaurant": "taco-brava", "name": st["name"], "qty": 1}])) == "BAD_ITEM:0")
    conn.commit()
    row = owner("select listed from public.pidi_menu m join public.pidi_restaurants r on r.id = m.restaurant_id where r.slug = 'taco-brava' and m.item_id = 'st'")
    check("its row is kept, marked not listed", row == [(False,)], str(row))
    sync("taco-brava", "open", tb_rows, from_save=True)
    check("put back, it can be ordered again", place(order([{"restaurant": "taco-brava", "name": st["name"], "qty": 1}]))["food_cents"] == st["price"])
    conn.commit()

    # --- options with an extra price (the website supports them: order-app.js unitPrice)
    test_menu = [
        {"id": "pz", "name": "Test pizza", "price": 1500, "soldOut": False, "includes": [], "options": [
            {"id": "size", "label": "Size", "type": "one", "default": "big", "choices": [
                {"id": "small", "label": "Small", "price": 0}, {"id": "big", "label": "Big", "price": 300}]},
            {"id": "extra", "label": "Add", "type": "many", "choices": [
                {"id": "cheese", "label": "Extra cheese", "price": 150}, {"id": "olives", "label": "Olives", "price": 100}]},
            {"id": "leave", "label": "Leave out", "type": "many", "choices": [{"id": "onion", "label": "No onion", "price": 0}]}]},
    ]
    sync("partner-test", "open", test_menu, from_save=True)
    for words, cents in [
        ("Test pizza", 1800),                                          # the default size (Big) carries 300
        ("Test pizza · Size: Small", 1500),
        ("Test pizza · Add: Extra cheese", 1950),
        ("Test pizza · Add: Extra cheese, Olives · No onion", 2050),
        ("Test pizza · Size: Small · Add: Olives · Add: Olives", 1600),   # a choice named twice counts once
        ("Test pizza · Extra cheese, Olives", 2050),
    ]:
        got = place(order([{"restaurant": "partner-test", "name": words, "qty": 2, "price_cents": 1}]))
        conn.commit()
        check("option prices: %s = %s" % (words, cents), got["food_cents"] == 2 * cents and got["items"][0]["price_cents"] == cents,
              str(got["items"]))
    check("two sizes at once is refused", code(order([{"restaurant": "partner-test", "name": "Test pizza · Size: Small, Big", "qty": 1}])) == "BAD_ITEM:0")
    conn.commit()

    # --- every dish of every real menu, with every choice, as the website writes the ticket line
    for slug, menu in menus.items():
        lines, want = [], []
        for item in menu["items"]:
            out = item.get("soldOut") or any(x.get("soldOut") for x in menu["items"] if x["id"] in (item.get("includes") or []))
            if out:
                continue
            for chosen, extra in variants(item):
                lines.append({"restaurant": slug, "name": " · ".join([item["name"]] + describe(item, chosen)), "qty": 1,
                              "price_cents": item["price"] + extra})
                want.append(item["price"] + extra)
        bad = []
        for start in range(0, len(lines), 50):
            placed, got = attempt(order(lines[start:start + 50]))
            conn.commit()
            if got:
                bad.append(got)
            elif placed.get("repriced") or placed["food_cents"] != sum(want[start:start + 50]):
                bad.append("priced %s, menu %s" % (placed["food_cents"], sum(want[start:start + 50])))
        check("%s: every dish and every choice, written as the website writes it, is priced as the menu (%s lines)" % (slug, len(lines)),
              not bad and lines, str(bad)[:300])

    # --- the menus go back to the website's own copy for whatever runs next
    for slug, menu in menus.items():
        sync(slug, "open", menu_rows(menu), from_save=True)


def fresh_db(name):
    admin = psycopg2.connect(DSN_ADMIN)
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    admin.cursor().execute("drop database if exists " + name)
    admin.cursor().execute("create database " + name)
    admin.close()
    conn = psycopg2.connect("dbname=%s host=/var/run/postgresql" % name)
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
    return conn


def gone_db(conn, name):
    conn.close()
    admin = psycopg2.connect(DSN_ADMIN)
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    admin.cursor().execute("drop database if exists " + name)
    admin.close()


def shape(conn):
    """Everything a pidi_ paste can change, to compare an upgraded database with a fresh one."""
    return {
        "functions": q(conn, """
            select p.oid::regprocedure::text, md5(p.prosrc), p.prosecdef, p.provolatile::text,
                   coalesce(array_to_string(p.proconfig, ','), ''), pg_get_function_result(p.oid),
                   has_function_privilege('anon', p.oid, 'execute'), has_function_privilege('authenticated', p.oid, 'execute')
            from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.proname like 'pidi\\_%' escape '\\' order by 1"""),
        "columns": q(conn, """
            select table_name, column_name, data_type, is_nullable, coalesce(column_default, '')
            from information_schema.columns where table_schema = 'public' and table_name like 'pidi\\_%' escape '\\'
            order by 1, 2"""),
        "constraints": q(conn, """
            select c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid)
            from pg_constraint c join pg_namespace n on n.oid = c.connamespace
            where n.nspname = 'public' and c.conname like 'pidi\\_%' escape '\\' order by 1, 2"""),
        "policies": q(conn, """
            select tablename, policyname, cmd, roles::text, coalesce(qual, ''), coalesce(with_check, '')
            from pg_policies where schemaname = 'public' and tablename like 'pidi\\_%' escape '\\' order by 1, 2"""),
        "rls": q(conn, """
            select c.relname, c.relrowsecurity from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind = 'r' and c.relname like 'pidi\\_%' escape '\\' order by 1"""),
        "table_rights": q(conn, """
            select grantee, table_name, privilege_type from information_schema.role_table_grants
            where table_schema = 'public' and table_name like 'pidi\\_%' escape '\\' and grantee in ('anon', 'authenticated', 'PUBLIC')
            order by 1, 2, 3"""),
        "settings": q(conn, """
            select key, value from public.pidi_settings
            where key not in ('kitchen_topic', 'admin_pin_hash') order by 1"""),
    }


def upgrade_matches_fresh():
    """The live database (PIDI_SETUP.sql as it was live) + the paste files == a fresh install of today's file."""
    old_path = os.environ.get("PIDI_OLD_SETUP")
    old = Path(old_path).read_text(encoding="utf-8") if old_path else None
    if old is None:
        try:
            old = subprocess.run(["git", "show", LIVE_SETUP_COMMIT + ":driver/v2/supabase/PIDI_SETUP.sql"], cwd=REPO,
                                 capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            print("skip  the upgrade test: PIDI_SETUP.sql at %s is not in this checkout (set PIDI_OLD_SETUP)" % LIVE_SETUP_COMMIT)
            return
    up = fresh_db("pidi_v2_upgrade")
    q(up, old)
    # an order placed before the pastes, by the old rules (the phone's price, a ƒ24 minimum)
    q(up, "update public.pidi_settings set value = 'flag' where key = 'hours_mode'")
    q(up, "set role anon")
    before = scalar(up, "select public.pidi_place_order(%s::jsonb)", [json.dumps({
        "name": "Old TEST", "phone": "2977100001", "area": "Noord", "address": "TEST", "pay": "transfer", "test": True,
        "items": [{"restaurant": "taco-brava", "name": "Birria tacos (3) with consommé", "qty": 1, "price_cents": 2700}]})])
    q(up, "reset role")
    q(up, "update public.pidi_settings set value = 'reject' where key = 'hours_mode'")
    for name in PASTES + PASTES:   # twice: safe to run twice
        q(up, (ROOT / name).read_text(encoding="utf-8"))
    fresh = fresh_db("pidi_v2_fresh")
    q(fresh, SQL_PATH.read_text(encoding="utf-8"))
    a, b = shape(up), shape(fresh)
    for part in a:
        check("upgrade = fresh install: %s" % part, a[part] == b[part],
              str([x for x in a[part] if x not in b[part]][:3]) + " / " + str([x for x in b[part] if x not in a[part]][:3]))
    kept = scalar(up, "select count(*) from public.pidi_orders where id = %s", [before["order_id"]])
    check("the order placed before the pastes is still there", kept == 1)
    gone_db(up, "pidi_v2_upgrade")
    gone_db(fresh, "pidi_v2_fresh")


def paste_guards():
    """In another project (no pidi_ tables) each paste stops at its first check and changes nothing."""
    conn = fresh_db("pidi_v2_other")
    q(conn, "create table public.bookkeeping_dummy (id integer primary key, note text)")
    q(conn, "insert into public.bookkeeping_dummy values (1, 'do not touch')")
    for name in PASTES:
        ok, detail = False, "no error"
        try:
            q(conn, (ROOT / name).read_text(encoding="utf-8"))
        except psycopg2.Error as err:
            detail = err.diag.message_primary or str(err)
            ok = "not the Pidi database" in detail
            q(conn, "rollback")   # the paste's own begin left an aborted transaction open
        made = scalar(conn, "select count(*) from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relname like 'pidi\\_%' escape '\\'")
        funcs = scalar(conn, "select count(*) from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname like 'pidi\\_%' escape '\\'")
        check("%s in another project stops and changes nothing" % name, ok and made == 0 and funcs == 0, "%s; tables %s, functions %s" % (detail, made, funcs))
    check("the other project's own row is untouched", scalar(conn, "select note from public.bookkeeping_dummy") == "do not touch")
    gone_db(conn, "pidi_v2_other")


def static_pastes():
    for name in PASTES:
        text = (ROOT / name).read_text(encoding="utf-8")
        code_only = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("--"))
        check("%s has no drop, delete or truncate (the SQL editor would ask, and nothing is removed)" % name,
              not re.search(r"\b(drop|delete|truncate)\b", text, re.I))
        body = code_only.strip()
        check("%s is one transaction that starts with the Pidi check" % name,
              re.match(r"begin;\s*do \$guard\$ begin\s*if to_regclass\('public\.pidi_orders'\) is null", body) is not None
              and "\ncommit;" in body, body[:120])


def main():
    static_sql()
    static_pastes()
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
    settings = dict(q(conn, "select key, value from public.pidi_settings where key in ('min_food_cents', 'eta_min', 'eta_max')"))
    check("no minimum and 35 to 50 minutes are the defaults (Victor, 16 Oct 2026)",
          settings == {"min_food_cents": "0", "eta_min": "35", "eta_max": "50"}, str(settings))
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
    # No minimum order (Victor, 16 Oct 2026): a ƒ1 order goes in.
    small = scalar(
        conn,
        "select public.pidi_place_order(%s::jsonb)",
        ['{"restaurant":"dushi-wok","name":"A","phone":"2975550001","area":"Noord","address":"1","pay":"cash","pays_with_cents":5000,"items":[{"name":"Fries","qty":1,"price_cents":100}],"test":true}'],
    )
    conn.commit()
    check("no minimum: a ƒ1 order goes in", small and small["food_cents"] == 100 and small["total_cents"] == 600, str(small)[:200])
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

    low = place_items([
        {"restaurant": "dushi-wok", "name": "Rice", "qty": 1, "price_cents": 1500},
        {"restaurant": "taco-brava", "name": "Taco", "qty": 1, "price_cents": 800},
    ], pays=5000, name="Low TEST", phone="2975990098")
    conn.commit()
    check("a mixed cart of ƒ15 + ƒ8 goes in (no minimum)", low["food_cents"] == 2300 and low["fee_cents"] == 500, str(low)[:200])
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
    # The live kitchen PIN was set when 4 digits were allowed. Store one like that,
    # as the owner, so the steps below prove it still signs in. New PINs are 6 to 8
    # digits; that is tested at the end.
    q(conn, "reset role")
    q(conn, """
        insert into public.pidi_settings (key, value)
        values ('kitchen_pin_hash', extensions.crypt('9999', extensions.gen_salt('bf', 8)))
        on conflict (key) do update set value = excluded.value
    """)
    q(conn, "set role anon")
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
    check("a 4-digit kitchen PIN set before the 6-digit rule still signs in", kitchen.get("ok") is True, str(kitchen)[:120])
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
    # A minimum set again later still works: ƒ15 of food under a ƒ24 minimum is refused.
    check("a minimum set again later refuses a smaller order",
          code_of(dict(good, phone="2975990079", items=[{"restaurant": "dushi-wok", "name": "Rice", "qty": 1, "price_cents": 1500}])) == "MIN_FOOD")
    conn.commit()
    q(conn, "reset role")
    q(conn, "update public.pidi_settings set value = '0' where key = 'min_food_cents'")
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

    # --- prices from the database's copy of the menus
    menu_prices(conn, kitchen["token"])
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

    # --- many wrong PINs at once, each on its own connection, still count one by one
    def owner(sql, args=None):
        q(conn, "reset role")
        q(conn, sql, args)
        conn.commit()
        q(conn, "set role anon")
        conn.commit()

    def burst(sql, args, n=20):
        gate = threading.Barrier(n)
        answers = []

        def one():
            other = psycopg2.connect(DSN)
            other.autocommit = True
            cur = other.cursor()
            try:
                cur.execute("set role anon")
                gate.wait(timeout=30)
                cur.execute(sql, args)
                row = cur.fetchone()[0]
                answers.append((row.get("error") or "ok") if isinstance(row, dict) else str(row))
            except (psycopg2.Error, threading.BrokenBarrierError) as err:
                answers.append("raised: " + str(err).strip())
            finally:
                other.close()

        threads = [threading.Thread(target=one) for _ in range(n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        misses = sum("does not match" in a.lower() for a in answers)
        waits = sum("too many tries" in a.lower() for a in answers)
        return misses, waits, answers

    def burst_check(label, misses, waits, answers, n=20):
        check(
            "%s %s wrong tries at once: at most 5 misses, the rest told to wait" % (n, label),
            misses <= 5 and misses + waits == n,
            "misses=%s waits=%s other=%s" % (misses, waits, [a for a in answers if "does not match" not in a.lower() and "too many tries" not in a.lower()][:3]),
        )
        check("%s wrong tries at once are all counted (exactly 5 misses)" % label, misses == 5, "misses=%s" % misses)

    owner("""
        update public.pidi_settings set value = case key when 'kitchen_pin_failures' then '0' else '' end
        where key in ('kitchen_pin_failures', 'kitchen_pin_locked_until')
    """)
    misses, waits, answers = burst("select public.pidi_kitchen_login(%s)", ["0000"])
    burst_check("kitchen", misses, waits, answers)
    q(conn, "reset role")
    k_failures = scalar(conn, "select value from public.pidi_settings where key = 'kitchen_pin_failures'")
    k_locked = scalar(conn, "select nullif(value, '')::timestamptz > now() from public.pidi_settings where key = 'kitchen_pin_locked_until'")
    conn.commit()
    q(conn, "set role anon")
    check("kitchen burst sets the lock and counts 5", k_locked is True and k_failures == "5", "%s %s" % (k_failures, k_locked))
    row = scalar(conn, "select public.pidi_kitchen_login(%s)", ["9999"])
    conn.commit()
    check("right kitchen PIN refused after the burst", row.get("ok") is False and "too many tries" in row.get("error", "").lower(), str(row))

    owner("update public.pidi_drivers set pin_failures = 0, pin_locked_until = null where name = 'Ari'")
    misses, waits, answers = burst("select public.pidi_driver_login(%s, %s)", ["Ari", "0000"])
    burst_check("driver", misses, waits, answers)
    q(conn, "reset role")
    d_row = q(conn, "select pin_failures, pin_locked_until > now() from public.pidi_drivers where name = 'Ari'")
    conn.commit()
    q(conn, "set role anon")
    check("driver burst sets the lock and counts 5", d_row == [(5, True)], str(d_row))
    row = scalar(conn, "select public.pidi_driver_login(%s, %s)", ["Ari", "2468"])
    conn.commit()
    check("right driver PIN refused after the burst", row.get("ok") is False and "too many tries" in row.get("error", "").lower(), str(row))
    row = scalar(conn, "select public.pidi_driver_login(%s, %s)", ["Bea", "1357"])
    conn.commit()
    check("the burst on one driver leaves another signing in", row.get("ok") is True, str(row))

    owner("""
        update public.pidi_settings set value = case key when 'admin_pin_failures' then '0' else '' end
        where key in ('admin_pin_failures', 'admin_pin_locked_until')
    """)
    misses, waits, answers = burst("select public.pidi_admin_list_drivers(%s)", ["00000000"])
    burst_check("admin", misses, waits, answers)
    q(conn, "reset role")
    a_failures = scalar(conn, "select value from public.pidi_settings where key = 'admin_pin_failures'")
    a_locked = scalar(conn, "select nullif(value, '')::timestamptz > now() from public.pidi_settings where key = 'admin_pin_locked_until'")
    conn.commit()
    q(conn, "set role anon")
    check("admin burst sets the lock and counts 5", a_locked is True and a_failures == "5", "%s %s" % (a_failures, a_locked))
    row = scalar(conn, "select public.pidi_admin_list_drivers(%s)", ["42424242"])
    conn.commit()
    check("right admin PIN refused after the burst", row.get("ok") is False and "too many tries" in row.get("error", "").lower(), str(row))

    # --- a new kitchen PIN is 6 to 8 digits
    owner("""
        update public.pidi_settings set value = case when key in ('admin_pin_failures', 'kitchen_pin_failures') then '0' else '' end
        where key in ('admin_pin_failures', 'admin_pin_locked_until', 'kitchen_pin_failures', 'kitchen_pin_locked_until')
    """)
    for short in ("1234", "12345"):
        ok, detail = explodes(conn, "select public.pidi_admin_set_kitchen_pin(%s, %s)", ["42424242", short], "6 to 8 digits")
        conn.commit()
        check("a %s-digit kitchen PIN is refused" % len(short), ok, detail)
    old = scalar(conn, "select public.pidi_kitchen_login(%s)", ["9999"])
    conn.commit()
    check("a refused new PIN leaves the old 4-digit PIN working", old.get("ok") is True, str(old)[:120])
    for good_pin in ("246810", "86420246"):
        saved = scalar(conn, "select public.pidi_admin_set_kitchen_pin(%s, %s)", ["42424242", good_pin])
        conn.commit()
        signed = scalar(conn, "select public.pidi_kitchen_login(%s)", [good_pin])
        conn.commit()
        check("a %s-digit kitchen PIN is saved and signs in" % len(good_pin),
              saved.get("ok") is True and signed.get("ok") is True, str(saved) + " " + str(signed)[:80])
    stale = scalar(conn, "select public.pidi_kitchen_login(%s)", ["9999"])
    conn.commit()
    check("the old 4-digit PIN stops working once a new one is set",
          stale.get("ok") is False and "does not match" in stale.get("error", "").lower(), str(stale))

    seed_when_placeholder_replaced()
    upgrade_matches_fresh()
    paste_guards()

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
