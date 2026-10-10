"""Staff screens check: the kitchen's Orders screen (ops/kitchen/, live.js) and the driver app (driver/v2/).

    python3 qa/check_staff.py                 (qa/check_site.py runs it too)
    STAFF_SHOTS=/some/folder python3 qa/check_staff.py   also saves phone screenshots there

Fakes only. Every call to the order database is answered here with Playwright routes (service workers
blocked, so the routes see every request); anything else sent to the database is stopped and fails the
check. No WebSocket opens. The Supabase library the driver app loads from a CDN is swapped for a tiny
stand-in that makes the same POST /rest/v1/rpc/<name> calls. No PIN, key or password is used: the
sessions below are made-up strings the fakes accept.

The clock is fixed at 11:30 PM Aruba time (America/Aruba, UTC-4), so the times on screen are known."""
import asyncio, copy, json, os, re, sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start, serve_stoppable
BASE = start()
SHOTS = os.environ.get("STAFF_SHOTS", "")
DB_HOST = "cdkopyphjvfxjqhasrae.supabase.co"
fails = []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)

AW = timezone(timedelta(hours=-4))   # Aruba: no summer time
NOW = datetime(2026, 10, 10, 23, 30, tzinfo=AW)
def at(dt): return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
def ago(m): return at(NOW - timedelta(minutes=m))
KITCHEN_SESSION = "qa-fake-kitchen-session-0000"
DRIVER_SESSION = "qa-fake-driver-session-0000"

# ------------------------------------------------------------------ the kitchen feed: three orders
A, B, C = "00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000b2", "00000000-0000-4000-8000-0000000000c3"
def item(name, qty, cents): return {"name": name, "qty": qty, "price_cents": cents}
FEED = {"orders": [
    # C: a bank-transfer pre-order for 1:00 AM, accepted, not due yet (start at 11:45 PM = due minus the usual 60 min
    #    and tonight's 15 busy minutes)
    {"id": C, "status": "accepted", "name": "Carla", "phone": "297 599 0003", "area": "Santa Cruz", "address": "Near the church, green house",
     "note": None, "pay": "transfer", "food_cents": 3390, "fee_cents": 500, "total_cents": 3890, "pays_with_cents": None,
     "change_due_cents": None, "transfer_status": "awaiting", "outside_hours": False, "test": False,
     "created_at": ago(20), "due_at": at(datetime(2026, 10, 11, 1, 0, tzinfo=AW)), "pays_in_usd": False, "night_no": 11,
     "eta_min": 45, "eta_max": 60, "busy_min": "15", "restaurant": "Nonna's Night In",
     "restaurants": [{"restaurant": "Nonna's Night In", "slug": "nonnas-night-in", "food_cents": 3390, "ready": False,
                      "items": [item("Penne arrabbiata (vegetarian) · Heat: Extra spicy", 2, 1695)]}]},
    # A: as soon as possible, cash in florins, two restaurants, options with the right prices
    {"id": A, "status": "new", "name": "Ana", "phone": "297 599 0001", "area": "Noord", "address": "Palm Beach 12, blue gate",
     "note": "Ring twice", "pay": "cash", "food_cents": 3045, "fee_cents": 500, "total_cents": 3545, "pays_with_cents": 5000,
     "change_due_cents": 1455, "transfer_status": None, "outside_hours": False, "test": False,
     "created_at": ago(8), "due_at": ago(8), "pays_in_usd": False, "night_no": 12, "eta_min": 45, "eta_max": 60, "busy_min": "15",
     "restaurant": "Oranje Snack, Taco Brava",
     "restaurants": [
        {"restaurant": "Oranje Snack", "slug": "oranje-snack", "food_cents": 1295, "ready": False,
         "items": [item("Bitterballen (8) · Dip: Mustard", 1, 1295)]},
        {"restaurant": "Taco Brava", "slug": "taco-brava", "food_cents": 1750, "ready": False,
         "items": [item("Ground beef street tacos (3) · Salsa: On the side · No onion", 1, 1450), item("Coca-Cola (can)", 1, 300)]}]},
    # B: a TEST order, cash in US dollars, cooking, one price edited down to ƒ1.00 (the menu says ƒ16.95)
    {"id": B, "status": "cooking", "name": "Ben", "phone": "297 599 0002", "area": "Palm Beach", "address": "Hotel lobby, room 214",
     "note": None, "pay": "cash", "food_cents": 3895, "fee_cents": 500, "total_cents": 4395, "pays_with_cents": 4395,
     "change_due_cents": 0, "transfer_status": None, "outside_hours": False, "test": True,
     "created_at": ago(4), "due_at": ago(4), "pays_in_usd": True, "night_no": 13, "eta_min": 45, "eta_max": 60, "busy_min": "15",
     "restaurant": "Smash Shack",
     "restaurants": [{"restaurant": "Smash Shack", "slug": "smash-shack", "food_cents": 3895, "ready": False,
                      "items": [item("Smash cheeseburger · No onion", 1, 100), item("Loaded fries (cheddar sauce, beef, scallion)", 1, 1195),
                                item("Double smash cheeseburger · No pickles, No mayo", 1, 2600)]}]},
]}

# ------------------------------------------------------------------ the driver: an offer with two drops, then the run
OFFER = [{"offer_id": "00000000-0000-4000-8000-0000000000f1", "run_id": "00000000-0000-4000-8000-0000000000e1", "seconds_left": 40,
          "stops": [
            {"stop_index": 1, "restaurant": "Oranje Snack, Taco Brava", "name": "Ana", "area": "Noord", "pay": "cash", "pays_in_usd": False,
             "night_no": 12, "fee_cents": 500, "total_cents": 3545},
            {"stop_index": 2, "restaurant": "Smash Shack", "name": "Ben", "area": "Palm Beach", "pay": "cash", "pays_in_usd": True,
             "night_no": 13, "fee_cents": 500, "total_cents": 4395}]}]
def run_stop(i, oid, status):
    o = OFFER[0]["stops"][i]
    s = dict(o, order_id=oid, status=status, phone="297 599 000" + str(i + 1), address=["Palm Beach 12, blue gate", "Hotel lobby, room 214"][i],
             lat=None, lng=None, note=None, pays_with_cents=[5000, 4395][i], change_due_cents=[1455, 0][i], transfer_status=None,
             bags=[{"restaurant": "Oranje Snack", "items": [{"name": "Bitterballen (8) · Dip: Mustard", "qty": 1}]},
                   {"restaurant": "Taco Brava", "items": [{"name": "Ground beef street tacos (3) · Salsa: On the side · No onion", "qty": 1}]}] if i == 0 else
                  [{"restaurant": "Smash Shack", "items": [{"name": "Smash cheeseburger · No onion", "qty": 1}]}])
    s["items"] = [x for b in s["bags"] for x in b["items"]]
    if i == 0:   # a pre-order. The live database doesn't send these two to drivers yet (10 Oct 2026); the screen shows them when it does.
        s["created_at"], s["due_at"] = ago(30), at(datetime(2026, 10, 11, 0, 15, tzinfo=AW))
    return s

STUB = """export function createClient(url, key) {
  return {
    rpc: async (name, args) => {
      const r = await fetch(url + "/rest/v1/rpc/" + name, { method: "POST", headers: { "content-type": "application/json", apikey: key, authorization: "Bearer " + key }, body: JSON.stringify(args || {}) });
      const t = await r.text(); let b = null; try { b = t ? JSON.parse(t) : null; } catch (e) { b = null; }
      return r.ok ? { data: b, error: null } : { data: null, error: b || { message: "Try again." } };
    },
    channel: () => { const c = { on: () => c, subscribe: () => c }; return c; },
    removeChannel: () => {},
  };
}"""
NO_SOCKETS = """window.__sockets = [];
window.WebSocket = class { constructor(u) { window.__sockets.push(String(u)); this.readyState = 3; } send() {} close() {} addEventListener() {} removeEventListener() {} };"""

class Fake:
    """Answers the database calls one context makes, and remembers them."""
    def __init__(self, answers):
        self.answers, self.calls, self.stray = answers, [], []
    async def handle(self, route):
        req = route.request
        u = urlparse(req.url)
        if u.hostname in ("127.0.0.1", "localhost", urlparse(BASE).hostname):   # the site under test
            return await route.continue_()
        if u.hostname == "cdn.jsdelivr.net" and "supabase-js" in u.path:
            return await route.fulfill(status=200, content_type="application/javascript", body=STUB)
        m = re.match(r"^/rest/v1/rpc/([a-z_]+)$", u.path)
        if u.hostname == DB_HOST and m and m.group(1) in self.answers and req.method == "POST":
            args = json.loads(req.post_data or "{}")
            self.calls.append((m.group(1), args))
            status, body = self.answers[m.group(1)](args)
            return await route.fulfill(status=status, content_type="application/json", body=json.dumps(body))
        self.stray.append(f"{req.method} {req.url}")
        return await route.abort()
    def named(self, n): return [a for (x, a) in self.calls if x == n]

async def shot(pg, name, full=True):
    if not SHOTS:
        return
    os.makedirs(SHOTS, exist_ok=True)
    size = pg.viewport_size
    if full:   # the kitchen app scrolls inside #main: grow the window to the whole list for one picture
        tall = await pg.evaluate("(() => { const m = document.querySelector('#shell #main'); return m ? m.scrollHeight - m.clientHeight : 0; })()")
        if tall > 0:
            await pg.set_viewport_size({"width": size["width"], "height": size["height"] + tall})
            await pg.wait_for_timeout(150)
    await pg.screenshot(path=os.path.join(SHOTS, name), full_page=full)
    if pg.viewport_size != size:
        await pg.set_viewport_size(size)
        await pg.wait_for_timeout(150)

def ok(body=None): return (200, body if body is not None else {"ok": True})

async def new_ctx(b, fake, w, h, init=""):
    ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=True, has_touch=True, service_workers="block")
    await ctx.clock.set_fixed_time(NOW)
    await ctx.add_init_script(NO_SOCKETS + init)
    await ctx.route("**/*", fake.handle)
    return ctx

async def text(pg, sel):
    return (await pg.evaluate("s => Array.from(document.querySelectorAll(s)).map(e => e.textContent.replace(/\\s+/g, ' ').trim())", sel))

# ================================================================== kitchen
async def kitchen(b, w, h, deep):
    state = copy.deepcopy(FEED)
    public_busy = {"v": 0}
    def set_busy(a):
        for o in state["orders"]: o["busy_min"] = str(a["minutes"])
        return ok({"ok": True, "busy_min": a["minutes"]})
    def paid(a):
        for o in state["orders"]:
            if o["id"] == a["order_id"]: o["transfer_status"] = "paid"
        return ok({"ok": True, "transfer_status": "paid"})
    fake = Fake({"pidi_kitchen_feed": lambda a: ok(copy.deepcopy(state)), "pidi_kitchen_set_busy": set_busy,
                 "pidi_kitchen_transfer_paid": paid, "pidi_public_state": lambda a: ok({"ok": True, "busy_min": public_busy["v"], "eta_min": 45, "eta_max": 60})})
    init = "localStorage.setItem('pidi.kitchen.session', JSON.stringify({ token: '%s', expires_at: '2099-01-01T00:00:00Z' }));" % KITCHEN_SESSION
    ctx = await new_ctx(b, fake, w, h, init)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    tag = f"[kitchen {w}x{h}]"
    await pg.goto(BASE + "ops/kitchen/index.html#/live")
    await pg.wait_for_selector(".lv-card .lv-price", timeout=15000)   # the menus are in and checked
    await pg.wait_for_timeout(300)
    nos = await text(pg, ".lv-no")
    check(nos == ["Order 12", "Order 13", "Order 11"], f"{tag} cook-now orders first (new, then cooking), the pre-order last: {nos}")
    later = await text(pg, ".lv-later .lv-no")
    check(later == ["Order 11"], f"{tag} the 1:00 AM pre-order waits under Later tonight" + ("" if later == ["Order 11"] else f": {later}"))
    head = await text(pg, ".lv-later h2")
    check(head == ["Later tonight"], f"{tag} the group is called Later tonight")
    c = (await text(pg, ".lv-later .lv-card .ohead"))[0] if later else ""
    check(re.search(r"Deliver at 1:00\sAM", c) and re.search(r"Start cooking at 11:45\sPM", c),
          f"{tag} pre-order says Deliver at 1:00 AM and Start cooking at 11:45 PM (usual 60 min + 15 busy, Aruba time): {c[:160]!r}")
    cards = await text(pg, ".lv-card .ohead")
    check(re.search(r"Came in 11:22\sPM · 8 min ago", cards[0]) is not None, f"{tag} Order 12 shows when it came in (11:22 PM Aruba): {cards[0][:80]!r}")
    check("Deliver at" not in cards[0] and "Deliver at" not in cards[1], f"{tag} as-soon-as-possible orders show no delivery time")
    pays = await text(pg, ".lv-card .pay")
    want = ["Pays ƒ50.00 cash · ƒ14.55 change", "Pays in US dollars · ƒ43.95 total", "Bank transfer · not in yet"]
    check(pays == want, f"{tag} payment lines (florins with change, US dollars with the total, transfer not in yet): {pays}")
    shown = await pg.evaluate("Array.from(document.querySelectorAll('.lv-card .pay')).map(e => e.innerText)")
    fl = await pg.evaluate("Array.from(document.querySelectorAll('.lv-card .pay .fl')).every(e => getComputedStyle(e).textTransform === 'none')")
    check(fl and all("Ƒ" not in s for s in shown), f"{tag} the florin sign stays a small ƒ in the capitalised payment line: {shown}")
    tests = await text(pg, ".lv-card .lv-test")
    test_card = await pg.evaluate("Array.from(document.querySelectorAll('.lv-card')).map(c => !!c.querySelector('.lv-test'))")
    check(tests == ["TEST"] and test_card == [False, True, False], f"{tag} only the TEST order carries the TEST mark: {test_card}")
    warn = await text(pg, ".lv-price")
    where = await pg.evaluate("Array.from(document.querySelectorAll('.lv-card')).map(c => c.querySelectorAll('.lv-price').length)")
    check(warn == ["Check the price: ƒ1.00 here, the menu now says ƒ16.95."] and where == [0, 1, 0],
          f"{tag} the edited price gets one red line on its card, options priced right elsewhere: {warn} {where}")
    bad_li = await text(pg, ".lv-bad")
    check(len(bad_li) == 1 and bad_li[0].startswith("1 × Smash cheeseburger"), f"{tag} the warning sits under the dish it is about: {bad_li}")
    seg = await pg.evaluate("Array.from(document.querySelectorAll('.lv-segb')).map(b => [b.textContent, b.getAttribute('aria-pressed')])")
    check(seg == [["Normal", "false"], ["+15 min", "true"], ["+30 min", "false"]], f"{tag} Kitchen busy? shows +15 min from the feed: {seg}")
    busy_line = await text(pg, ".lv-busy-p")
    check(not busy_line, f"{tag} with orders to cook, Kitchen busy? is one row (the lit choice says what is on): {busy_line}")
    wide = await pg.evaluate("(() => { const m = document.querySelector('#main'); return [m.scrollWidth, m.clientWidth]; })()")
    check(wide[0] <= wide[1], f"{tag} the Orders list doesn't scroll sideways: {wide}")
    await shot(pg, f"kitchen-orders-{w}x{h}.png")
    await shot(pg, f"kitchen-first-screen-{w}x{h}.png", full=False)
    if deep:
        await pg.click(".lv-segb[data-min='0']")
        await pg.wait_for_function("document.querySelector('.lv-segb[data-min=\"0\"]').getAttribute('aria-pressed') === 'true'")
        check(fake.named("pidi_kitchen_set_busy") == [{"session": KITCHEN_SESSION, "minutes": 0}], f"{tag} Normal sets busy to 0 straight away")
        await pg.click(".lv-segb[data-min='30']")
        await pg.wait_for_selector("#sheet:not([hidden]) [data-live='busy-yes']")
        check(len(fake.named("pidi_kitchen_set_busy")) == 1, f"{tag} +30 min asks first and sets nothing yet")
        await shot(pg, f"kitchen-busy-confirm-{w}x{h}.png", full=False)
        await pg.click("#sheet [data-live='busy-yes']")
        await pg.wait_for_function("document.querySelector('.lv-segb[data-min=\"30\"]').getAttribute('aria-pressed') === 'true'")
        check(fake.named("pidi_kitchen_set_busy")[-1] == {"session": KITCHEN_SESSION, "minutes": 30}, f"{tag} Yes, +30 min sets busy to 30")
        await pg.click(f".lv-card [data-live='paid'][data-id='{C}']")
        await pg.wait_for_function("Array.from(document.querySelectorAll('.lv-card .pay')).some(e => /came in/.test(e.textContent))")
        check(fake.named("pidi_kitchen_transfer_paid") == [{"session": KITCHEN_SESSION, "order_id": C}], f"{tag} The transfer came in marks that order")
        check(await pg.locator(f"[data-live='paid'][data-id='{C}']").count() == 0, f"{tag} the transfer button goes once it came in")
        # Cook step by step keeps the delivery time, US dollars and TEST
        await pg.click(f".lv-card [data-live='cook'][data-id='{C}']")
        await pg.wait_for_selector(".order-wrap .ohead")
        head = (await text(pg, ".order-wrap .ohead"))[0]
        reply = (await text(pg, ".reply"))[0]
        check(re.search(r"Ready for 1:00\sAM", head) and re.search(r"booked for 1:00\sAM", reply) and "Paid by bank transfer" in head,
              f"{tag} the pre-order's cook screen says Ready for 1:00 AM and Paid by bank transfer, the Confirm reply booked for 1:00 AM: {head[:120]!r} / {reply[:90]!r}")
        await shot(pg, f"kitchen-cook-preorder-{w}x{h}.png", full=False)
        await pg.goto(BASE + "ops/kitchen/index.html#/live")
        await pg.wait_for_selector(f".lv-card [data-live='cook'][data-id='{B}']")
        await pg.click(f".lv-card [data-live='cook'][data-id='{B}']")
        await pg.wait_for_selector(".order-wrap .ohead")
        head = (await text(pg, ".order-wrap .ohead"))[0]
        check("TEST order" in head and re.search(r"Pays in US dollars to the driver · ƒ43\.95 total", head) and "Pays cash" not in head,
              f"{tag} the TEST US-dollar order's cook screen says TEST and Pays in US dollars: {head[:140]!r}")
        await shot(pg, f"kitchen-cook-test-usd-{w}x{h}.png", full=False)
        await pg.goto(BASE + "ops/kitchen/index.html#/live")
        await pg.wait_for_selector(".lv-card .lv-price", timeout=15000)
        # a price changed in the Menu tile tonight: the lines that matched before stay clean, a new order is checked
        # against the new price
        osm = json.load(open(os.path.join(ROOT, "oranje-snack/menu.json"), encoding="utf-8"))
        for it in osm["items"]:
            if it["name"] == "Bitterballen (8)": it["price"] += 100
        await pg.route("**/oranje-snack/menu.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(osm)))
        # at 12:05 AM the pre-order is due: it moves up to the orders to cook now (and the menus are read again)
        await ctx.clock.set_fixed_time(datetime(2026, 10, 11, 0, 5, tzinfo=AW))
        async with pg.expect_response(lambda r: "oranje-snack/menu.json" in r.url):
            await pg.evaluate("window.KitchenLive.show()")
        await pg.wait_for_timeout(300)
        # a new order after the change, at the old price
        state["orders"].append(dict(copy.deepcopy(FEED["orders"][1]), id="00000000-0000-4000-8000-0000000000e5", night_no=15, created_at=ago(-20), due_at=ago(-20),
            busy_min=state["orders"][0]["busy_min"],
            restaurants=[{"restaurant": "Oranje Snack", "slug": "oranje-snack", "food_cents": 1295, "ready": False, "items": [item("Bitterballen (8) · Dip: Mustard", 1, 1295)]}]))
        await pg.evaluate("window.KitchenLive.show()")
        await pg.wait_for_function("document.querySelectorAll('.lv-price').length >= 2", timeout=10000)
        nos = await text(pg, ".lv-no")
        check(await pg.locator(".lv-later").count() == 0 and "Order 11" in nos, f"{tag} at 12:05 AM the pre-order is with the orders to cook now: {nos}")
        per = await pg.evaluate("Array.from(document.querySelectorAll('.lv-card')).map(c => [c.querySelector('.lv-no').textContent, Array.from(c.querySelectorAll('.lv-price')).map(e => e.textContent)])")
        per = dict(per)
        check(per.get("Order 12") == [] and per.get("Order 15") == ["Check the price: ƒ12.95 here, the menu now says ƒ13.95."] and len(per.get("Order 13", [])) == 1,
              f"{tag} after a price change tonight, Order 12 (right when it came in) stays clean and a new order is checked: {per}")
        # no orders open: the busy minutes come from the public state
        state["orders"] = []
        public_busy["v"] = 15
        pg2 = await ctx.new_page()
        await pg2.goto(BASE + "ops/kitchen/index.html#/live")
        await pg2.wait_for_selector(".lv-empty")
        await pg2.wait_for_function("(document.querySelector('.lv-segb.on') || {}).textContent === '+15 min'", timeout=10000)
        check(True, f"{tag} with no orders open, Kitchen busy? reads +15 min from the public state")
        line = await text(pg2, ".lv-busy-p")
        check(line and "15 min later" in line[0], f"{tag} with nothing to cook, a sentence says what the busy switch is doing: {line}")
        await pg2.close()
        # an option with an extra price: the menu here charges ƒ1.50 for jalapeños (the live menu doesn't, yet)
        tb = json.load(open(os.path.join(ROOT, "taco-brava/menu.json"), encoding="utf-8"))
        for it in tb["items"]:
            for g in it.get("options", []):
                for ch in g["choices"]:
                    if ch["id"] == "jalapeños": ch["price"] = 150
        state["orders"] = [dict(FEED["orders"][1], id="00000000-0000-4000-8000-0000000000d4", night_no=14, status="accepted", restaurants=[
            {"restaurant": "Taco Brava", "slug": "taco-brava", "food_cents": 4650, "ready": False, "items": [
                item("Beef nachos (fried tortilla chips) · Add: Jalapeños", 1, 2150),
                item("Beef nachos (fried tortilla chips) · Jalapeños, No cream", 1, 2000),
                item("Taco of the day", 1, 500)]}])]
        pg3 = await ctx.new_page()
        await pg3.route("**/taco-brava/menu.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(tb)))
        await pg3.goto(BASE + "ops/kitchen/index.html#/live")
        await pg3.wait_for_selector(".lv-card .lv-price", timeout=15000)
        await pg3.wait_for_timeout(300)
        warn = await text(pg3, ".lv-items li")
        want = [None, "Check the price: ƒ20.00 here, the menu now says ƒ21.50.", "Check this dish: it is not on the Taco Brava menu."]
        got = [(re.search(r"Check .*$", w) or [None])[0] for w in warn]
        check(got == want, f"{tag} an option's extra price counts; a dish not on the menu is flagged: {got}")
        await pg3.close()
    for name, a in fake.calls:
        if name.startswith("pidi_kitchen_") and a.get("session") != KITCHEN_SESSION:
            check(False, f"{tag} {name} carried the kitchen session")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not await pg.evaluate("window.__sockets.length"), f"{tag} no live connection opened")
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

# ================================================================== kitchen: the edges
MAPS = "https://www.google.com/maps/place/12%C2%B033'31.2%22N+70%C2%B002'41.9%22W/@12.5586667,-70.0449722,17z/data=!3m1"
async def kitchen_edges(b, w, h):
    """One new one-dish order (a Google Maps link as its address), an afternoon pre-order for tonight (a Maps link as
    its note) and a pre-order for tomorrow night, taken tonight."""
    one = lambda slug, rest, it: [{"restaurant": rest, "slug": slug, "food_cents": it["price_cents"], "ready": False, "items": [it]}]
    base = dict(FEED["orders"][1], busy_min="0", note=None)
    state = {"orders": [
        dict(base, id="00000000-0000-4000-8000-0000000000a6", night_no=16, status="new", address=MAPS, note="Ring twice",
             pays_with_cents=5000, food_cents=1295, total_cents=1795, change_due_cents=3205,
             restaurants=one("oranje-snack", "Oranje Snack", item("Bitterballen (8) · Dip: Mustard", 1, 1295))),
        dict(base, id="00000000-0000-4000-8000-0000000000a7", night_no=17, status="accepted", name="Pre", note=MAPS,
             created_at=at(datetime(2026, 10, 10, 16, 5, tzinfo=AW)), due_at=at(datetime(2026, 10, 11, 1, 30, tzinfo=AW)),
             restaurants=one("taco-brava", "Taco Brava", item("Coca-Cola (can)", 1, 300))),
        dict(base, id="00000000-0000-4000-8000-0000000000a8", night_no=18, status="accepted", name="Sunday",
             created_at=ago(30), due_at=at(datetime(2026, 10, 11, 22, 30, tzinfo=AW)),
             restaurants=one("taco-brava", "Taco Brava", item("Coca-Cola (can)", 1, 300)))]}
    fake = Fake({"pidi_kitchen_feed": lambda a: ok(copy.deepcopy(state)),
                 "pidi_public_state": lambda a: ok({"ok": True, "busy_min": 0, "eta_min": 45, "eta_max": 60})})
    init = "localStorage.setItem('pidi.kitchen.session', JSON.stringify({ token: '%s', expires_at: '2099-01-01T00:00:00Z' }));" % KITCHEN_SESSION
    ctx = await new_ctx(b, fake, w, h, init)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    tag = f"[kitchen edges {w}x{h}]"
    await pg.goto(BASE + "ops/kitchen/index.html#/live")
    await pg.wait_for_selector(".lv-later .lv-card", timeout=15000)
    await pg.wait_for_timeout(600)
    fold = await pg.evaluate("""(() => { const c = document.querySelector('.lv-card'), r = s => c.querySelector(s).getBoundingClientRect().bottom;
      return [innerHeight, Math.round(r('.lv-items li')), Math.round(r("[data-live='accept']"))]; })()""")
    check(fold[2] <= fold[0], f"{tag} a new one-dish order shows its dish and the whole Accept button on the first screen (screen, dish, Accept bottoms): {fold}")
    wide = await pg.evaluate("(() => { const m = document.querySelector('#main'); return [m.scrollWidth, m.clientWidth]; })()")
    check(wide[0] <= wide[1], f"{tag} a Google Maps link as address or note doesn't push the list sideways: {wide}")
    heads = await text(pg, ".lv-card .ohead")
    check(re.search(r"Came in 4:05\sPM · 7 hours ago", heads[1]) is not None, f"{tag} an afternoon pre-order says 7 hours ago, not 445 min: {heads[1][:60]!r}")
    check(re.search(r"Deliver Sunday night at 10:30\sPM", heads[2]) and re.search(r"Start cooking Sunday night at 9:30\sPM", heads[2]),
          f"{tag} a pre-order for tomorrow night names the night: {heads[2][:120]!r}")
    check(await text(pg, ".lv-later h2") == ["Pre-orders for later"], f"{tag} with a pre-order for another night the group is Pre-orders for later")
    await shot(pg, f"kitchen-edges-first-{w}x{h}.png", full=False)
    await shot(pg, f"kitchen-edges-{w}x{h}.png")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

# ================================================================== driver v2
async def driver(b, w, h, deep):
    st = {"run": None}
    def accept(a):
        st["run"] = {"run_id": OFFER[0]["run_id"], "pickup": {"name": "", "address": "", "lat": None, "lng": None},
                     "stops": [run_stop(0, A, "assigned"), run_stop(1, B, "assigned")]}
        return ok({"ok": True, "run_id": OFFER[0]["run_id"]})
    def picked(a):
        for s in st["run"]["stops"]: s["status"] = "picked_up"
        return ok()
    def delivered(a):
        for s in st["run"]["stops"]:
            if s["order_id"] == a["order_id"]: s["status"] = "delivered"
        return ok()
    fake = Fake({"pidi_ping": lambda a: ok({"ok": True}), "pidi_driver_offers": lambda a: ok([] if st["run"] else OFFER),
                 "pidi_driver_set_online": lambda a: ok({"ok": True, "online": a.get("online")}), "pidi_driver_accept": accept,
                 "pidi_driver_run": lambda a: ok(st["run"]), "pidi_driver_picked_up": picked, "pidi_driver_delivered": delivered,
                 "pidi_driver_location": lambda a: ok()})
    init = ("sessionStorage.setItem('pidi.v2.token', '%s'); sessionStorage.setItem('pidi.v2.driver', JSON.stringify({ name: 'Test driver' }));"
            "sessionStorage.setItem('pidi.v2.online', '1');") % DRIVER_SESSION
    ctx = await new_ctx(b, fake, w, h, init)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    tag = f"[driver {w}x{h}]"
    await pg.goto(BASE + "driver/v2/index.html")
    await pg.wait_for_selector("#offers .stop", timeout=15000)
    stops = await text(pg, "#offers .stop")
    nos = await text(pg, "#offers .order-no")
    check(nos == ["Order 12", "Order 13"], f"{tag} the offer shows each drop's order number: {nos}")
    col = await text(pg, "#offers .collect")
    check(col == ["Collect ƒ35.45", "Collect in US dollars: ƒ43.95 total"], f"{tag} florins: collect the total; US dollars: collect in dollars, the total in florins: {col}")
    check(not any("change" in s.lower() for s in stops), f"{tag} the offer shows no change line")
    dock = await text(pg, "#dock button")
    seen = await pg.evaluate("(() => { const b = document.querySelector('#dock button'); const r = b && b.getBoundingClientRect(); return !!r && r.bottom <= innerHeight && r.top >= 0; })()")
    check(dock == ["Accept"] and seen, f"{tag} with one offer, Accept is the big button on the first screen: {dock}")
    # the offers don't carry transfer_status (the run does): an offer never says "Awaiting" for a transfer
    lines = await pg.evaluate("""import('%sdriver/v2/js/client.js').then(m => [m.collectLine({ pay: 'transfer', total_cents: 3890 }),
      m.collectLine({ pay: 'transfer', transfer_status: 'awaiting' }), m.collectLine({ pay: 'transfer', transfer_status: 'paid' })])""" % BASE)
    check(lines == ["Bank transfer. Don't collect cash.", "Awaiting transfer. Don't collect cash.", "Paid by bank transfer. Don't collect cash."],
          f"{tag} a transfer on an offer says Bank transfer; the run says awaiting or paid: {lines}")
    await shot(pg, f"driver-offer-{w}x{h}.png", full=False)
    if deep:
        await pg.click("#dock button:has-text('Accept')")
        await pg.wait_for_url("**/driver/v2/run.html")
        await pg.wait_for_selector("h2.stop-no")
        pick = await text(pg, "h2.stop-no")
        check(pick == ["Order 12 · Ana", "Order 13 · Ben"], f"{tag} pickup lists the bags under each order number: {pick}")
        await shot(pg, f"driver-pickup-{w}x{h}.png")
        await pg.click("#dock button")
        await pg.wait_for_function("document.querySelector('main .quiet') && /Drop 1 of 2/.test(document.querySelector('main .quiet').textContent)")
        d1 = (await text(pg, "main"))[0]
        check("Drop 1 of 2 · Order 12" in d1 and "Pays with ƒ50.00" in d1 and "Give ƒ14.55 change" in d1, f"{tag} drop 1 (florins) shows its number, what they pay with and the change: {d1[:200]!r}")
        check(re.search(r"Deliver at 12:15\sAM", d1) is not None, f"{tag} a pre-order drop says Deliver at 12:15 AM (when the stop carries its time)")
        await shot(pg, f"driver-drop-florins-{w}x{h}.png")
        await pg.click("#dock button")
        await pg.wait_for_function("/Drop 2 of 2/.test(document.querySelector('main .quiet').textContent)")
        d2 = (await text(pg, "main"))[0]
        box = (await text(pg, "main .money"))[0]
        check("Drop 2 of 2 · Order 13" in d2 and box.startswith("Collect in US dollars") and "ƒ43.95 total" in box and "change" not in box.lower() and "Pays with" not in box,
              f"{tag} drop 2 (US dollars): collect in US dollars, the total, no florin change: {box!r}")
        check("Deliver at" not in d2, f"{tag} an as-soon-as-possible drop shows no delivery time")
        await shot(pg, f"driver-drop-usd-{w}x{h}.png")
        sess = {a.get("session") for n, a in fake.calls if n.startswith("pidi_driver_")}
        check(sess == {DRIVER_SESSION}, f"{tag} every driver call carried the driver session")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not await pg.evaluate("window.__sockets.length"), f"{tag} no live connection opened")
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

# ================================================================== old addresses
async def redirects(b):
    fake = Fake({"pidi_ping": lambda a: ok({"ok": True}), "pidi_driver_offers": lambda a: ok([]), "pidi_driver_set_online": lambda a: ok()})
    ctx = await new_ctx(b, fake, 390, 844)
    pg = await ctx.new_page()
    for old, new in [("driver/", "driver/v2/"), ("driver/index.html?from=home#x=1", "driver/v2/?from=home#x=1"),
                     ("driver/run.html#eyJydW4iOjF9", "driver/v2/run.html#eyJydW4iOjF9"), ("driver/cash.html", "driver/v2/"),
                     ("driver/dispatch.html", "driver/v2/"), ("driver/help.html", "driver/v2/help.html"),
                     ("driver/v2/status/#t=abc123", "order/#t=abc123")]:
        try:
            await pg.goto(BASE + old)
            await pg.wait_for_url(BASE + new, timeout=8000)
            check(True, f"/{old} goes on to /{new}")
        except Exception:
            check(False, f"/{old} goes on to /{new}: landed on {pg.url}")
    await pg.goto(BASE + "driver/v2/help.html")
    check("Call 911" in (await text(pg, "main"))[0], "the driver help page (Call 911, Police 100, WhatsApp) is there in v2")
    for f in ["index.html", "run.html", "cash.html", "dispatch.html", "help.html"]:
        html = open(os.path.join(ROOT, "driver", f), encoding="utf-8").read()
        check('http-equiv="refresh"' in html and "location.replace" in html and "js/app.js" not in html, f"driver/{f} only sends the phone on to v2 (script and refresh fallback)")
    man = json.load(open(os.path.join(ROOT, "driver/manifest.webmanifest"), encoding="utf-8"))
    check(man.get("start_url") == "v2/" and man.get("id") == "./" and man.get("scope") == "./", "the installed driver app opens v2 (same app id and scope)")
    check(not fake.stray, "the old addresses sent nothing to the database" + (f": {fake.stray}" if fake.stray else ""))
    await ctx.close()

# ================================================================== the driver app offline
async def offline(p):
    """The driver app's service worker with the server gone: pages it has open, old links, a page it never saved.
    None may loop (it did: the old index.html, served in place of a missing page, forwards to v2/ relative to it)."""
    base, srv = serve_stoppable()
    # the database's name points nowhere in this browser: nothing can reach the real one
    b = await p.chromium.launch(args=[f"--host-resolver-rules=MAP {DB_HOST} 127.0.0.1:9"])
    fake = Fake({"pidi_ping": lambda a: ok({"ok": True}), "pidi_driver_offers": lambda a: ok([]), "pidi_driver_set_online": lambda a: ok()})
    async def handle(route):
        try:
            await fake.handle(route)
        except Exception:   # the server is gone
            try: await route.abort()
            except Exception: pass
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    await ctx.add_init_script(NO_SOCKETS)
    await ctx.route("**/*", handle)
    pg = await ctx.new_page()
    await pg.goto(base + "driver/v2/")
    try:
        await pg.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=15000)
    except Exception:
        check(False, "the driver app's offline cache starts on /driver/v2/")
    srv.shutdown(); srv.server_close()
    for target, end in [("driver/v2/", "driver/v2/"), ("driver/v2/?x=1#y", "driver/v2/?x=1#y"), ("driver/?x=1#y", "driver/v2/?x=1#y"),
                        # (v2's run page with nobody signed in goes on to the v2 home screen by itself)
                        ("driver/run.html#abc", "driver/v2/index.html"), ("driver/install/", "driver/install/"), ("driver/v2/status/", "driver/v2/")]:
        navs = []
        def seen(f): navs.append(f.url) if f == pg.main_frame else None
        pg.on("framenavigated", seen)
        try:
            await pg.goto(base + target, timeout=5000)
        except Exception:
            pass
        await pg.wait_for_timeout(1500)
        pg.remove_listener("framenavigated", seen)
        last = (navs[-1] if navs else pg.url).replace(base, "")
        check(len(navs) <= 3 and last == end and not any("v2/v2" in u for u in navs),
              f"offline, /{target} ends on /{end} without going round in circles ({len(navs)} page loads: {[u.replace(base, '/') for u in navs][:4]})")
    check(not fake.stray, "the offline driver app sent nothing to the database" + (f": {fake.stray}" if fake.stray else ""))
    await b.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await kitchen(b, 390, 844, True)
        await kitchen(b, 360, 640, False)
        await kitchen_edges(b, 390, 844)
        await kitchen_edges(b, 360, 640)
        await driver(b, 390, 844, True)
        await driver(b, 360, 640, True)
        await redirects(b)
        await b.close()
        await offline(p)

asyncio.run(main())
print(f"\n{len(fails)} problem(s) on the staff screens")
sys.exit(1 if fails else 0)
