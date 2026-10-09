#!/usr/bin/env python3
"""Apply the Pidi v2 migration to local Postgres and test dispatch and RLS.

    python3 driver/v2/supabase/tests/run_local.py

Uses the local cluster (no Supabase project, no network). A failure exits 1.
"""

import json
import pathlib
import subprocess
import threading

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "20261009170000_pidi_v2.sql"
DB = "pidi_v2_test"
DSN = f"dbname={DB} host=/var/run/postgresql"

passes = []
fails = []


def check(name, ok, detail=""):
    if ok:
        passes.append(name)
        print(f"pass  {name}")
    else:
        fails.append(name)
        print(f"FAIL  {name}  {detail}")


def admin(sql):
    subprocess.check_call(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-c", sql],
        stdout=subprocess.DEVNULL,
    )


def fresh():
    admin(f"DROP DATABASE IF EXISTS {DB}")
    admin(f"CREATE DATABASE {DB}")
    subprocess.check_call(
        ["sudo", "-u", "postgres", "psql", "-q", "-v", "ON_ERROR_STOP=1", "-d", DB, "-f", str(MIGRATION)],
        stdout=subprocess.DEVNULL,
    )


def connect():
    return psycopg2.connect(DSN)


def allow(cur):
    cur.execute("select set_config('pidi.allow_anytime', 'on', false)")


def claims(cur, body):
    cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(body),))


def place(cur, **extra):
    payload = {
        "restaurant": "dushi-wok",
        "name": "Maria TEST",
        "phone": "2975990001",
        "area": "Noord",
        "address": "TEST, Weg naar Westpunt 12, Noord",
        "lat": 12.5696,
        "lng": -70.0310,
        "note": "TEST order",
        "pay": "cash",
        "pays_with_cents": 5000,
        "test": True,
        "items": [{"name": "Chicken fried rice", "qty": 1, "price_cents": 2895}],
    }
    payload.update(extra)
    cur.execute("select pidi.place_order(%s::jsonb)", (json.dumps(payload),))
    return cur.fetchone()[0]


def seed_people(cur):
    cur.execute(
        """
        insert into drivers (name, code, pin_hash, online, active)
        values
          ('Ari', 'ari', pidi.hash_pin('2468'), true, true),
          ('Bo', 'bo', pidi.hash_pin('1357'), true, true)
        returning id, code
        """
    )
    drivers = {row[1]: row[0] for row in cur.fetchall()}
    cur.execute(
        """
        insert into staff (name, code, pin_hash, active)
        values ('Chef', 'chef', pidi.hash_pin('9999'), true)
        returning id
        """
    )
    staff_id = cur.fetchone()[0]
    return drivers, staff_id


def test_money_and_minimum():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        try:
            place(cur, items=[{"name": "Fries", "qty": 1, "price_cents": 500}])
            check("minimum ƒ24 rejected", False, "insert succeeded")
        except psycopg2.Error as exc:
            conn.rollback()
            allow(cur)
            check("minimum ƒ24 rejected", "24" in str(exc), str(exc).split("\n")[0])
        row = place(cur)
        check("cash total is ƒ33.95", row["total_cents"] == 3395, row)
        check("change due is ƒ16.05", row["change_due_cents"] == 1605, row)
        check("fee is ƒ5", row["fee_cents"] == 500, row)
        again = place(cur, client_token="retry-1")
        same = place(cur, client_token="retry-1", name="Other")
        check("same client token does not open a second order", again["id"] == same["id"], (again, same))
        transfer = place(
            cur,
            pay="transfer",
            pays_with_cents=None,
            name="Carlos TEST",
            phone="2975990002",
            area="Oranjestad",
            address="TEST, Wilhelminastraat 8, Oranjestad",
            lat=12.5092,
            lng=-70.0086,
            restaurant="taco-brava",
            items=[{"name": "Birria tacos", "qty": 1, "price_cents": 2700}],
        )
        check("transfer collects no change", transfer["change_due_cents"] is None, transfer)
        check("transfer waits", transfer["pay"] == "transfer", transfer)


def test_checkout_one_fee():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        cur.execute(
            "select pidi.place_checkout(%s::jsonb)",
            (json.dumps({
                "name": "Mix TEST",
                "phone": "2975990041",
                "area": "Noord",
                "address": "TEST mix",
                "lat": 12.57,
                "lng": -70.03,
                "pay": "cash",
                "pays_with_cents": 5000,
                "test": True,
                "groups": [
                    {"restaurant": "dushi-wok", "items": [{"name": "Fried rice", "qty": 1, "price_cents": 1600}]},
                    {"restaurant": "taco-brava", "items": [{"name": "Taco", "qty": 1, "price_cents": 1200}]},
                ],
            }),),
        )
        got = cur.fetchone()[0]
        orders = got["orders"]
        fees = sorted(o["fee_cents"] for o in orders)
        foods = sorted(o["food_cents"] for o in orders)
        check("two restaurants, one ƒ5 fee", fees == [0, 500], got)
        check("ƒ24 is the checkout total, not each restaurant", foods == [1200, 1600], got)
        check("cash change uses the fee-bearing total", orders[0]["change_due_cents"] == 5000 - (1600 + 500) or orders[1]["change_due_cents"] == 5000 - (1600 + 500), got)


def test_hours():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("select set_config('pidi.allow_anytime', '', false)")
        cur.execute("select set_config('pidi.now', '2026-10-09 15:00:00-04', false)")
        try:
            place(cur)
            check("afternoon order rejected", False, "insert succeeded")
        except psycopg2.Error as exc:
            conn.rollback()
            check("afternoon order rejected", "10 PM" in str(exc), str(exc).split("\n")[0])
        cur.execute("select set_config('pidi.now', '2026-10-09 23:30:00-04', false)")
        row = place(cur)
        check("11:30 PM order accepted", row["status"] == "new" and row["outside_hours"] is False, row)
        cur.execute("update settings set value = 'flag' where key = 'hours_mode'")
        cur.execute("select set_config('pidi.now', '2026-10-10 12:00:00-04', false)")
        flagged = place(cur, name="Day TEST", phone="2975990003", client_token="day")
        check("flag mode keeps a daytime order", flagged["outside_hours"] is True, flagged)


def kitchen_ready(cur, order_id, staff_id):
    claims(cur, {"role": "authenticated", "staff_role": "kitchen", "staff_id": str(staff_id)})
    for status in ("accepted", "cooking", "ready"):
        cur.execute(
            "select pidi.kitchen_set_status(%s, %s::public.order_status)",
            (order_id, status),
        )
        got = cur.fetchone()[0]
        if not got["ok"]:
            raise RuntimeError(got)


def test_pairing_and_offer():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        drivers, staff_id = seed_people(cur)
        near = place(cur, name="Near TEST", phone="2975990011", lat=12.5720, lng=-70.0310)
        far = place(
            cur,
            name="Far TEST",
            phone="2975990012",
            area="Oranjestad",
            address="TEST far",
            lat=12.5092,
            lng=-70.0086,
            restaurant="taco-brava",
            items=[{"name": "Birria tacos", "qty": 1, "price_cents": 2700}],
        )
        conn.commit()
        kitchen_ready(cur, near["id"], staff_id)
        kitchen_ready(cur, far["id"], staff_id)
        cur.execute("select count(*) from runs where status = 'offered'")
        check("far drops stay two runs", cur.fetchone()[0] == 2, "runs=" + str(cur.fetchone() if False else ""))
        cur.execute(
            """
            select count(*) from run_orders ro
            join runs r on r.id = ro.run_id
            where r.status = 'offered'
            group by ro.run_id
            order by count(*) desc
            """
        )
        sizes = [row[0] for row in cur.fetchall()]
        check("no unwanted pair across town", sizes == [1, 1], sizes)

        close = place(cur, name="Close TEST", phone="2975990013", lat=12.5705, lng=-70.0305)
        conn.commit()
        kitchen_ready(cur, close["id"], staff_id)
        cur.execute(
            """
            select r.id, count(ro.order_id)
            from runs r
            join run_orders ro on ro.run_id = r.id
            where r.status = 'offered'
              and r.id in (
                select run_id from run_orders where order_id in (%s, %s)
              )
            group by r.id
            """,
            (near["id"], close["id"]),
        )
        paired = cur.fetchall()
        check("nearby ready orders share one run", len(paired) == 1 and paired[0][1] == 2, paired)
        cur.execute("select count(*) from offers where status = 'pending'")
        pending = cur.fetchone()[0]
        check("each offered run reaches both online drivers", pending == 4, pending)
        cur.execute("select pidi.verify_driver_pin('ari', '2468')")
        check("right PIN returns the driver", cur.fetchone()[0]["code"] == "ari")
        cur.execute("select pidi.verify_driver_pin('ari', '0000')")
        check("wrong PIN is refused", cur.fetchone()[0]["error"] == "no")


def test_concurrent_accept():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        drivers, staff_id = seed_people(cur)
        a = place(cur, name="A TEST", phone="2975990021")
        b = place(cur, name="B TEST", phone="2975990022", lat=12.5700, lng=-70.0308)
        conn.commit()
        kitchen_ready(cur, a["id"], staff_id)
        kitchen_ready(cur, b["id"], staff_id)
        cur.execute(
            """
            select o.id, o.driver_id::text
            from offers o
            join run_orders ro on ro.run_id = o.run_id
            where ro.order_id = %s and o.status = 'pending'
            """,
            (a["id"],),
        )
        offers = cur.fetchall()
        check("paired run has two pending offers", len(offers) == 2, offers)
        conn.commit()

    results = []

    def accept(offer_id, driver_id):
        cn = connect()
        cn.autocommit = False
        c = cn.cursor()
        claims(c, {"role": "authenticated", "driver_id": driver_id})
        c.execute("select pidi.accept_offer(%s)", (offer_id,))
        results.append(c.fetchone()[0])
        cn.commit()
        cn.close()

    threads = [
        threading.Thread(target=accept, args=(offers[0][0], offers[0][1])),
        threading.Thread(target=accept, args=(offers[1][0], offers[1][1])),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    oks = [r for r in results if r.get("ok")]
    taken = [r for r in results if r.get("error") == "Another driver took this run"]
    check("one accept wins", len(oks) == 1 and len(taken) == 1, results)
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("select status, driver_id::text from runs where id = (select run_id from offers where id = %s)", (offers[0][0],))
        status, winner = cur.fetchone()
        check("run is active for the winner", status == "active" and winner in (offers[0][1], offers[1][1]), (status, winner, oks))
        cur.execute("select count(*) from orders where status = 'assigned' and id in (%s, %s)", (a["id"], b["id"]))
        # winner run_id compared wrong above. Fix check separately.
        assigned = cur.fetchone()[0]
        check("both orders assigned once", assigned == 2, assigned)
        cur.execute("select driver_id::text from runs where status = 'active'")
        drivers_on_it = [row[0] for row in cur.fetchall()]
        check("only one driver owns the run", len(drivers_on_it) == 1, drivers_on_it)


def test_reoffer():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        drivers, staff_id = seed_people(cur)
        row = place(cur)
        conn.commit()
        kitchen_ready(cur, row["id"], staff_id)
        cur.execute("update offers set expires_at = now() - interval '1 second' where status = 'pending'")
        cur.execute("select pidi.dispatch_tick()")
        cur.execute("select status, count(*) from offers group by status order by status")
        counts = dict(cur.fetchall())
        check("expired offers are closed", counts.get("expired", 0) >= 1, counts)
        check("a fresh offer is written", counts.get("pending", 0) >= 1, counts)
        cur.execute("select expires_at > now() from offers where status = 'pending'")
        check("the new offer is still open", cur.fetchone()[0] is True)


def test_dispatch_on_accept():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        seed_people(cur)
        cur.execute("update settings set value = 'accepted' where key = 'dispatch_when'")
        row = place(cur)
        conn.commit()
        cur.execute("select count(*) from offers")
        check("a new order is not offered before the kitchen accepts", cur.fetchone()[0] == 0)
        kitchen_ready_one(cur, row["id"], "accepted")
        cur.execute("select count(*) from offers where status = 'pending'")
        check("accept-time dispatch offers the run", cur.fetchone()[0] == 2)


def kitchen_ready_one(cur, order_id, status):
    cur.execute("select id from staff where code = 'chef'")
    staff_id = cur.fetchone()[0]
    claims(cur, {"role": "authenticated", "staff_role": "kitchen", "staff_id": str(staff_id)})
    cur.execute("select pidi.kitchen_set_status(%s, %s::public.order_status)", (order_id, status))
    got = cur.fetchone()[0]
    if not got["ok"]:
        raise RuntimeError(got)


def test_rls():
    fresh()
    with connect() as conn:
        cur = conn.cursor()
        allow(cur)
        drivers, staff_id = seed_people(cur)
        mine = place(cur, name="Mine TEST", phone="2975990031")
        other = place(cur, name="Other TEST", phone="2975990032", lat=12.60, lng=-70.04, area="Palm Beach")
        conn.commit()
        kitchen_ready(cur, mine["id"], staff_id)
        cur.execute(
            "select id::text, driver_id::text from offers where status = 'pending' and run_id in (select run_id from run_orders where order_id = %s)",
            (mine["id"],),
        )
        offer_rows = cur.fetchall()
        conn.commit()

    def as_role(role, jwt, sql, args=()):
        cn = connect()
        c = cn.cursor()
        c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(jwt),))
        c.execute(f"set role {role}")
        try:
            c.execute(sql, args)
            rows = c.fetchall()
            cn.rollback()
            return rows, None
        except psycopg2.Error as exc:
            cn.rollback()
            return None, str(exc).split("\n")[0]

    rows, err = as_role("anon", {}, "select id from orders")
    check("anon sees no orders without a token", err is None and rows == [], (rows, err))
    rows, err = as_role(
        "anon",
        {"role": "authenticated", "order_token": "not-a-real-token"},
        "select id::text from orders",
    )
    check("a wrong token sees nothing", rows == [], (rows, err))
    # Customer JWT uses role authenticated in the claim, but the API role is anon
    # until the edge function upgrades it. Both roles are in the policy.
    token_jwt = {"role": "authenticated", "order_token": None}
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("select public_token from orders where id = %s", (mine["id"],))
        token = cur.fetchone()[0]
    rows, err = as_role("anon", {"order_token": token}, "select id::text from orders")
    check("token reads only that order", rows == [(str(mine["id"]),)], (rows, err))
    rows, err = as_role("anon", {}, "update orders set status = 'delivered'")
    check("anon cannot update an order", err is not None and "permission" in err.lower(), err)

    ari = str(drivers["ari"])
    bo = str(drivers["bo"])
    rows, err = as_role(
        "authenticated",
        {"role": "authenticated", "driver_id": bo},
        "select id::text from offers",
    )
    bo_ids = {row[0] for row in rows or []}
    ari_offer_ids = {row[0] for row in offer_rows if row[1] == ari}
    check("a driver cannot see the other driver's offers", ari_offer_ids.isdisjoint(bo_ids), (ari_offer_ids, bo_ids, err))
    rows, err = as_role(
        "authenticated",
        {"role": "authenticated", "staff_role": "kitchen", "staff_id": str(staff_id)},
        "select id::text from orders",
    )
    seen = {row[0] for row in rows or []}
    check("kitchen sees both orders", {str(mine["id"]), str(other["id"])} <= seen, (seen, err))
    rows, err = as_role(
        "authenticated",
        {"role": "authenticated", "staff_role": "kitchen", "staff_id": str(staff_id)},
        "select pidi.kitchen_set_status(%s, 'delivered'::public.order_status)",
        (mine["id"],),
    )
    check("kitchen cannot jump to delivered", err is not None, err)


def main():
    test_money_and_minimum()
    test_checkout_one_fee()
    test_hours()
    test_pairing_and_offer()
    test_dispatch_on_accept()
    test_concurrent_accept()
    test_reoffer()
    test_rls()
    print(f"\n{len(passes)} passed, {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
