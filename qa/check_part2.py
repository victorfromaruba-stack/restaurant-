"""Part 2 previews check: the kitchen preview (ops/kitchen-next/) and the driver preview (driver-next/).

    python3 qa/check_part2.py
    PART2_SHOTS=/some/folder python3 qa/check_part2.py     also saves screenshots: 390 and 1024 px, light and dark
    PART2_VIDEO=/some/file.mp4 python3 qa/check_part2.py   also records the ~20 s phone run (TEST order, kitchen to driver)

Every state the brief lists, against fake answers only: orders arriving, accept, cooking, ready, a driver takes it,
picked up, delivered, cash, cancel, sold out (the Menu tile, in check_kitchen.py), offline, error, empty and a slow
network. Nothing reaches the real order database: every call is answered here, anything else is stopped and fails
the check. No PIN, key or password is typed or read: the sessions are made-up strings the fakes accept. All names,
phones and addresses are invented TEST data. Then the service-worker rules: each preview's worker stays in its own
folder, uses its own cache names, never deletes a live app's caches, and never controls a live page; and the live
folders are byte for byte what origin/main has.
The clock is fixed at 11:30 PM Aruba time (America/Aruba, UTC-4)."""
import asyncio, copy, json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start
BASE = start()
KITCHEN, DRIVER = "ops/kitchen-next/", "driver-next/"
SHOTS = os.environ.get("PART2_SHOTS", "")
VIDEO = os.environ.get("PART2_VIDEO", "")
DB_HOST = "cdkopyphjvfxjqhasrae.supabase.co"
fails, passes = [], []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    (passes if ok else fails).append(msg)

AW = timezone(timedelta(hours=-4))
NOW = datetime(2026, 11, 19, 23, 30, tzinfo=AW)
def at(dt): return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
def ago(m): return at(NOW - timedelta(minutes=m))
KS, DS = "qa-fake-kitchen-session-part2", "qa-fake-driver-session-part2"

# ------------------------------------------------------------------ invented TEST data
def item(name, qty, cents): return {"name": name, "qty": qty, "price_cents": cents}
def order(oid, no, status, mins, **kw):
    o = {"id": oid, "status": status, "name": "TEST Maria", "phone": "297 555 0101", "area": "Noord", "address": "TEST, Palm Beach 12",
         "note": None, "pay": "cash", "food_cents": 2895, "fee_cents": 500, "total_cents": 3395, "pays_with_cents": 5000,
         "change_due_cents": 1605, "transfer_status": None, "outside_hours": False, "test": True, "created_at": ago(mins), "due_at": ago(mins),
         "pays_in_usd": False, "night_no": no, "eta_min": 35, "eta_max": 50, "busy_min": "0", "restaurant": "Dushi Wok",
         "restaurants": [{"restaurant": "Dushi Wok", "slug": "dushi-wok", "food_cents": 2895, "ready": False,
                          "items": [item("Chicken fried rice", 1, 1295), item("Sweet & sour crunch chicken with rice", 1, 1600)]}]}
    o.update(kw)
    return o
O1, O2, O3 = ("00000000-0000-4000-8000-00000000a201", "00000000-0000-4000-8000-00000000a202", "00000000-0000-4000-8000-00000000a203")
STUB = """export function createClient(url, key) {
  return {
    rpc: async (name, args) => {
      try {
        const r = await fetch(url + "/rest/v1/rpc/" + name, { method: "POST", headers: { "content-type": "application/json", apikey: key, authorization: "Bearer " + key }, body: JSON.stringify(args || {}) });
        const t = await r.text(); let b = null; try { b = t ? JSON.parse(t) : null; } catch (e) { b = null; }
        return r.ok ? { data: b, error: null } : { data: null, error: b || { message: "Try again." } };
      } catch (e) {
        // what supabase-js answers when the request never got out (no signal)
        return { data: null, error: { message: "TypeError: Failed to fetch", details: "", hint: "", code: "" } };
      }
    },
    channel: () => { const c = { on: () => c, subscribe: () => c }; return c; },
    removeChannel: () => {},
  };
}"""
INIT = """window.__sockets = []; window.__buzz = 0;
window.WebSocket = class { constructor(u) { window.__sockets.push(String(u)); this.readyState = 3; } send() {} close() {} addEventListener() {} removeEventListener() {} };
try { Object.defineProperty(navigator, 'vibrate', { value: () => { window.__buzz++; return true; }, configurable: true }); } catch (e) {}"""

class Fake:
    """Answers the database calls one context makes, remembers them, and can play slow, broken or gone."""
    def __init__(self, answers):
        self.answers, self.calls, self.stray, self.delay, self.down = answers, [], [], {}, set()
    async def handle(self, route):
        req = route.request
        u = urlparse(req.url)
        if u.hostname in ("127.0.0.1", "localhost", urlparse(BASE).hostname):
            return await route.continue_()
        if u.hostname == "cdn.jsdelivr.net" and "supabase-js" in u.path:
            return await route.fulfill(status=200, content_type="application/javascript", body=STUB)
        m = re.match(r"^/rest/v1/rpc/([a-z_]+)$", u.path)
        if u.hostname == DB_HOST and m and m.group(1) in self.answers and req.method == "POST":
            name = m.group(1)
            if name in self.down or "*" in self.down:
                return await route.abort("internetdisconnected")
            if self.delay.get(name):
                await asyncio.sleep(self.delay[name])
            args = json.loads(req.post_data or "{}")
            self.calls.append((name, args))
            status, body = self.answers[name](args)
            return await route.fulfill(status=status, content_type="application/json", body=json.dumps(body))
        self.stray.append(f"{req.method} {req.url}")
        return await route.abort()
    def named(self, n): return [a for (x, a) in self.calls if x == n]

def ok(body=None): return (200, body if body is not None else {"ok": True})

async def new_ctx(b, fake, w=390, h=844, scheme="dark", init="", video=None):
    opts = dict(viewport={"width": w, "height": h}, is_mobile=w < 700, has_touch=True, service_workers="block", color_scheme=scheme)
    if video:
        opts.update(record_video_dir=video, record_video_size={"width": w, "height": h})
    ctx = await b.new_context(**opts)
    await ctx.clock.set_fixed_time(NOW)
    await ctx.add_init_script(INIT + init)
    await ctx.route("**/*", fake.handle)
    return ctx

async def text(pg, sel):
    return await pg.evaluate("s => Array.from(document.querySelectorAll(s)).map(e => e.textContent.replace(/\\s+/g, ' ').trim())", sel)

async def shot(pg, name):
    if not SHOTS:
        return
    os.makedirs(SHOTS, exist_ok=True)
    await pg.screenshot(path=os.path.join(SHOTS, name), full_page=False)

def kitchen_fake(state):
    def find(a): return next(o for o in state["orders"] if o["id"] == a["order_id"])
    def accept(a): find(a)["status"] = "accepted"; return ok()
    def set_status(a): find(a)["status"] = a["status"]; return ok()
    def ready(a):
        o = find(a)
        for g in o["restaurants"]:
            if g["slug"] == a["restaurant"]: g["ready"] = True
        if all(g["ready"] for g in o["restaurants"]): o["status"] = "ready"
        return ok()
    def cancel(a): state["orders"] = [o for o in state["orders"] if o["id"] != a["order_id"]]; return ok()
    def feed(a):
        if state.get("feed_error"): return (400, {"message": state["feed_error"]})
        return ok(copy.deepcopy({"orders": state["orders"]}))
    return Fake({"pidi_kitchen_feed": feed, "pidi_kitchen_accept": accept, "pidi_kitchen_set_status": set_status,
                 "pidi_kitchen_mark_ready": ready, "pidi_kitchen_cancel": cancel,
                 "pidi_kitchen_sync_menu": lambda a: ok({"ok": True, "skipped": False}),
                 "pidi_kitchen_set_busy": lambda a: ok({"ok": True, "busy_min": a["minutes"]}),
                 "pidi_public_state": lambda a: ok({"ok": True, "busy_min": 0, "eta_min": 35, "eta_max": 50})})

KINIT = "localStorage.setItem('pidi.kitchen.session', JSON.stringify({ token: '%s', expires_at: '2099-01-01T00:00:00Z' }));" % KS

async def refresh(pg):
    await pg.evaluate("window.KitchenLive.show()")
    await pg.wait_for_timeout(250)

# ================================================================== kitchen: one order from arriving to the driver
async def kitchen_flow(b):
    tag = "[kitchen]"
    state = {"orders": []}
    fake = kitchen_fake(state)
    ctx = await new_ctx(b, fake, init=KINIT)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(BASE + KITCHEN + "index.html#/live")
    await pg.wait_for_selector(".lv-empty", timeout=15000)
    e = (await text(pg, ".lv-empty"))[0]
    check("No orders right now" in e and "beep" in e, f"{tag} empty: says nothing is waiting and that new orders beep and show up by themselves: {e!r}")
    await shot(pg, "kitchen-empty-390-dark.png")
    # orders arriving: one new TEST order; the screen rings and the slip says NEW
    state["orders"].append(order(O1, 21, "new", 1))
    await refresh(pg)
    await pg.wait_for_selector(".lv-card.lv-new")
    buzz = await pg.evaluate("window.__buzz")
    head = (await text(pg, ".lv-card .lv-top"))[0]
    check(buzz >= 1 and "NEW" in head and "Order 21" in head, f"{tag} orders arriving: the phone buzzes and the slip says NEW with the big number: {head!r}, buzz {buzz}")
    lines = await text(pg, ".lv-card .lv-items li")
    check(lines == ["1 × Chicken fried rice", "1 × Sweet & sour crunch chicken with rice"], f"{tag} the ticket lines read exactly as the customer sent them: {lines}")
    clock = (await text(pg, ".lv-card .lv-clock"))[0]
    check(clock.startswith("1") and "min" in clock, f"{tag} the minutes since it came in show big on the slip: {clock!r}")
    # nobody accepted yet: it rings again after 20 s, and every other screen shows the yellow bar
    await ctx.clock.set_fixed_time(NOW + timedelta(seconds=25))
    await refresh(pg)
    buzz2 = await pg.evaluate("window.__buzz")
    check(buzz2 > buzz, f"{tag} an order nobody accepted rings again after 20 s ({buzz} then {buzz2} buzzes)")
    await pg.evaluate("location.hash = '#/'")
    await pg.wait_for_selector(".home-grid")
    await pg.wait_for_timeout(200)
    bar = await pg.evaluate("(() => { const a = document.getElementById('lv-alert'); return a && !a.hidden ? a.textContent : ''; })()")
    tile = await pg.evaluate("document.querySelector('.big-mode.live').className")
    check("New order 21" in bar and "lv-has-new" in tile, f"{tag} on the home screen the yellow bar and the Orders tile both say a new order waits: {bar!r}")
    await shot(pg, "kitchen-home-new-390-dark.png")
    await pg.click("#lv-alert")
    await pg.wait_for_selector(".lv-card.lv-new")
    gone = await pg.evaluate("document.getElementById('lv-alert').hidden")
    check(gone, f"{tag} the bar opens Orders and goes away there")
    await shot(pg, "kitchen-new-390-dark.png")
    # accept, cooking, ready
    await pg.click(f"[data-live='accept'][data-id='{O1}']")
    await pg.wait_for_selector(f"[data-live='cooking'][data-id='{O1}']")
    check(fake.named("pidi_kitchen_accept") == [{"session": KS, "order_id": O1}], f"{tag} accept: one tap sends Accept for that order with the kitchen session")
    check(await pg.locator(".lv-card.lv-new").count() == 0, f"{tag} after Accept the slip is no longer NEW")
    await pg.click(f"[data-live='cooking'][data-id='{O1}']")
    await pg.wait_for_selector(f"[data-live='ready'][data-id='{O1}']")
    check(fake.named("pidi_kitchen_set_status") == [{"session": KS, "order_id": O1, "status": "cooking"}], f"{tag} cooking: Start cooking sets it to cooking")
    label = (await text(pg, f"[data-live='ready'][data-id='{O1}']"))[0]
    check(label == "Food is ready", f"{tag} a one-restaurant order offers Food is ready: {label!r}")
    await shot(pg, "kitchen-cooking-390-dark.png")
    await pg.click(f"[data-live='ready'][data-id='{O1}']")
    await pg.wait_for_function("/Waiting for a driver/.test(document.querySelector('#main').textContent)")
    check(fake.named("pidi_kitchen_mark_ready") == [{"session": KS, "order_id": O1, "restaurant": "dushi-wok"}], f"{tag} ready: Food is ready marks the Dushi Wok bag ready")
    # a driver takes it, then has it
    state["orders"][0]["status"] = "assigned"
    await refresh(pg)
    m = (await text(pg, "#main"))[0]
    check("A driver took it and is coming for the bags." in m, f"{tag} assign a driver: the slip says a driver took it")
    state["orders"][0]["status"] = "picked_up"
    await refresh(pg)
    m = (await text(pg, "#main"))[0]
    check("The driver has it." in m and await pg.locator(f"[data-live='cancel'][data-id='{O1}']").count() == 0,
          f"{tag} picked up: the slip says the driver has it, and it can no longer be cancelled here")
    # cancel: a second order the kitchen can't do
    state["orders"].append(order(O2, 22, "new", 0, name="TEST Carlos", pay="transfer", transfer_status="awaiting", pays_with_cents=None, change_due_cents=None))
    await refresh(pg)
    await pg.click(f"[data-live='cancel'][data-id='{O2}']")
    await pg.wait_for_selector("#sheet:not([hidden]) [data-live='cancel-yes']")
    check(not fake.named("pidi_kitchen_cancel"), f"{tag} cancel asks first and cancels nothing yet")
    await shot(pg, "kitchen-cancel-ask-390-dark.png")
    await pg.click("#sheet [data-live='cancel-yes']")
    await pg.wait_for_function("!document.querySelector(\"[data-id='%s']\")" % O2)
    check(fake.named("pidi_kitchen_cancel") == [{"session": KS, "order_id": O2}], f"{tag} cancel: Yes, cancel the order cancels that order only")
    # time order: two cooking orders, the older one first; a new one above both
    state["orders"] = [order(O1, 23, "cooking", 6), order(O2, 24, "accepted", 14), order(O3, 25, "new", 0)]
    await refresh(pg)
    nos = await text(pg, ".lv-no")
    check(nos == ["Order 25", "Order 24", "Order 23"], f"{tag} the queue: new first, then oldest first: {nos}")
    ages = await pg.evaluate("Array.from(document.querySelectorAll('.lv-card')).map(c => c.className.match(/lv-age-\\w+/) ? c.className.match(/lv-age-\\w+/)[0] : '')")
    check(ages == ["", "lv-age-warn", ""], f"{tag} a slip waiting 10 min or more turns yellow: {ages}")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not await pg.evaluate("window.__sockets.length"), f"{tag} no live connection opened")
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

# ================================================================== kitchen: offline, error, slow
async def kitchen_trouble(b):
    tag = "[kitchen trouble]"
    state = {"orders": [order(O1, 31, "cooking", 4)]}
    fake = kitchen_fake(state)
    fake.delay["pidi_kitchen_feed"] = 2.5
    ctx = await new_ctx(b, fake, init=KINIT)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(BASE + KITCHEN + "index.html#/live")
    await pg.wait_for_timeout(900)
    skel = await pg.evaluate("Array.from(document.querySelectorAll('.lv-skel')).filter(e => getComputedStyle(e).opacity > 0.5).length")
    load = await text(pg, "#main .loading")
    check(skel == 2 and load == ["Loading orders…"], f"{tag} slow network: slip-shaped placeholders and Loading orders… while the feed takes 2.5 s ({skel} shown)")
    await shot(pg, "kitchen-slow-390-dark.png")
    await pg.wait_for_selector(".lv-card", timeout=10000)
    check(True, f"{tag} slow network: the order shows once the answer comes")
    fake.delay.clear()
    # offline: the feed can't be reached; the last orders stay, the screen says so
    fake.down.add("pidi_kitchen_feed")
    await refresh(pg)
    await pg.wait_for_selector(".lv-offline")
    off = (await text(pg, ".lv-offline"))[0]
    sub = (await text(pg, "#bar small"))[0]
    check("Couldn’t check for orders" in off and "Try again" in off and await pg.locator(".lv-card").count() == 1,
          f"{tag} offline: says it couldn't check, keeps the last orders on screen, offers Try again: {off[:90]!r}")
    check("Couldn’t check" in sub and "last good" in sub, f"{tag} offline: the top bar says when the last good check was: {sub!r}")
    await shot(pg, "kitchen-offline-390-dark.png")
    fake.down.clear()
    await pg.click(".lv-offline [data-live='retry']")
    await pg.wait_for_function("!document.querySelector('.lv-offline')")
    check(True, f"{tag} offline: Try again brings it back when the connection returns")
    # error: the database answers with a problem
    state["feed_error"] = "TEST problem from the database."
    await refresh(pg)
    await pg.wait_for_selector(".banner.allergy")
    eb = (await text(pg, ".banner.allergy"))[0]
    check("Couldn’t check for orders: TEST problem from the database." in eb and "Try again" in eb, f"{tag} error: the database's words and Try again: {eb!r}")
    await shot(pg, "kitchen-error-390-dark.png")
    state.pop("feed_error")
    await pg.click(".banner.allergy [data-live='retry']")
    await pg.wait_for_function("!document.querySelector('.banner.allergy')")
    check(True, f"{tag} error: Try again clears it once the database answers")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

# ================================================================== driver: offer, pickup, cash, offline, delivered
OFFER = [{"offer_id": "00000000-0000-4000-8000-00000000f201", "run_id": "00000000-0000-4000-8000-00000000e201", "seconds_left": 40,
          "stops": [{"stop_index": 1, "restaurant": "Dushi Wok", "name": "TEST Maria", "area": "Noord", "pay": "cash", "pays_in_usd": False,
                     "night_no": 21, "fee_cents": 500, "total_cents": 3395},
                    {"stop_index": 2, "restaurant": "Taco Brava", "name": "TEST Carlos", "area": "Oranjestad", "pay": "cash", "pays_in_usd": True,
                     "night_no": 22, "fee_cents": 500, "total_cents": 3200}]}]
def run_of(status):
    s1 = dict(OFFER[0]["stops"][0], order_id=O1, status=status, phone="297 555 0101", address="TEST, Palm Beach 12", note="TEST order. Green gate.",
              lat=None, lng=None, pays_with_cents=5000, change_due_cents=1605, transfer_status=None,
              bags=[{"restaurant": "Dushi Wok", "items": [{"name": "Chicken fried rice", "qty": 1}, {"name": "Sweet & sour crunch chicken with rice", "qty": 1}]}])
    s2 = dict(OFFER[0]["stops"][1], order_id=O2, status=status, phone="297 555 0102", address="TEST, Wilhelminastraat 8", note=None,
              lat=None, lng=None, pays_with_cents=None, change_due_cents=None, transfer_status=None,
              bags=[{"restaurant": "Taco Brava", "items": [{"name": "Birria tacos (3) with consommé", "qty": 1}]}])
    for s in (s1, s2): s["items"] = [x for bg in s["bags"] for x in bg["items"]]
    return {"run_id": OFFER[0]["run_id"], "pickup": {"name": "TEST pickup", "address": "", "lat": None, "lng": None}, "stops": [s1, s2]}

def driver_fake(st):
    def accept(a): st["run"] = run_of("assigned"); return ok({"ok": True, "run_id": OFFER[0]["run_id"]})
    def picked(a):
        for s in st["run"]["stops"]: s["status"] = "picked_up"
        return ok()
    def delivered(a):
        if st.get("refuse"): return (400, {"message": st["refuse"]})
        for s in st["run"]["stops"]:
            if s["order_id"] == a["order_id"]: s["status"] = "delivered"
        return ok()
    return Fake({"pidi_ping": lambda a: ok({"ok": True}),
                 "pidi_driver_offers": lambda a: ok([] if (st["run"] or st.get("none")) else OFFER),
                 "pidi_driver_set_online": lambda a: ok({"ok": True, "online": a.get("online")}), "pidi_driver_accept": accept,
                 "pidi_driver_run": lambda a: ok(st["run"]), "pidi_driver_picked_up": picked, "pidi_driver_delivered": delivered,
                 "pidi_driver_decline": lambda a: ok(), "pidi_driver_location": lambda a: ok(),
                 "pidi_driver_login": lambda a: ok({"ok": False, "error": "That PIN does not match."})})

DINIT = ("sessionStorage.setItem('pidi.v2.token', '%s'); sessionStorage.setItem('pidi.v2.driver', JSON.stringify({ name: 'TEST driver' }));"
         "sessionStorage.setItem('pidi.v2.online', '1');") % DS

async def driver_flow(b):
    tag = "[driver]"
    st = {"run": None}
    fake = driver_fake(st)
    fake.delay["pidi_driver_offers"] = 1.5
    ctx = await new_ctx(b, fake, init=DINIT)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(BASE + DRIVER + "index.html")
    await pg.wait_for_selector("#offers .checking", timeout=10000)
    check(True, f"{tag} slow network: Checking for runs… shows while the offers take 1.5 s")
    await pg.wait_for_selector("#offers .stop", timeout=10000)
    fake.delay.clear()
    buzz = await pg.evaluate("window.__buzz")
    nos = await text(pg, "#offers .order-no")
    col = await text(pg, "#offers .collect")
    secs = (await text(pg, "#offers .clock .figure"))[0] + " " + (await text(pg, "#offers .clock .small"))[0]
    check(buzz >= 1 and nos == ["Order 21", "Order 22"], f"{tag} a run offer rings and buzzes and shows each drop's number: {nos}")
    check(col == ["Collect ƒ33.95", "Collect in US dollars: ƒ32.00 total"], f"{tag} what to collect per drop, in florins: {col}")
    check(re.match(r"^\d+s to accept$", secs) is not None, f"{tag} the seconds left to accept: {secs!r}")
    dock = await pg.evaluate("(() => { const b = document.querySelector('#dock button'); const r = b.getBoundingClientRect(); return [b.textContent, Math.round(r.height), r.bottom <= innerHeight]; })()")
    check(dock[0] == "Accept" and dock[1] >= 56 and dock[2], f"{tag} Accept is the big thumb button on the first screen: {dock}")
    await shot(pg, "driver-offer-390-dark.png")
    await pg.click("#dock button")
    await pg.wait_for_url("**/" + DRIVER + "run.html")
    await pg.wait_for_selector(".bagslip")
    pick = await text(pg, "h2.stop-no")
    check(pick == ["Order 21 · TEST Maria", "Order 22 · TEST Carlos"], f"{tag} pickup: the bags under each order number: {pick}")
    await shot(pg, "driver-pickup-390-dark.png")
    await pg.click("#dock button")
    await pg.wait_for_function("/Drop 1 of 2/.test((document.querySelector('main .quiet') || {}).textContent || '')")
    check(fake.named("pidi_driver_picked_up") == [{"session": DS, "run_id": OFFER[0]["run_id"]}], f"{tag} picked up: one tap sends Picked up for the run")
    box = (await text(pg, "main .money"))[0]
    check("Collect" in box and "ƒ33.95" in box and "Pays with ƒ50.00" in box and "Give ƒ16.05 change" in box,
          f"{tag} cash: collect ƒ33.95, pays with ƒ50.00, give ƒ16.05 change: {box!r}")
    fold = await pg.evaluate("""(() => { const a = Array.from(document.querySelectorAll('.actions .btn')); const dock = document.querySelector('.dock').getBoundingClientRect().top;
      return [a.map(x => x.textContent), Math.round(Math.max(...a.map(x => x.getBoundingClientRect().bottom))), Math.round(dock)]; })()""")
    check(fold[0] == ["Google Maps", "Waze", "Call", "WhatsApp"] and fold[1] <= fold[2], f"{tag} Maps, Waze, Call and WhatsApp sit above the Delivered bar: {fold}")
    await shot(pg, "driver-drop-cash-390-dark.png")
    # offline: no signal; the run stays and the Delivered tap waits on the phone
    await ctx.set_offline(True)
    fake.down.add("*")   # the routes would still answer an offline page: nothing gets through now
    await pg.wait_for_selector(".signal:not([hidden])")
    await pg.click("#dock button")
    await pg.wait_for_function("/Drop 2 of 2/.test((document.querySelector('main .quiet') || {}).textContent || '')")
    pend = await text(pg, "main .pending")
    check(pend == ["1 tap saved on this phone. It sends when the signal is back."] and not fake.named("pidi_driver_delivered"),
          f"{tag} offline: Delivered without signal is saved on the phone and the next drop shows: {pend}")
    box2 = (await text(pg, "main .money"))[0]
    check(box2.startswith("Collect in US dollars") and "ƒ32.00 total" in box2 and "change" not in box2.lower(), f"{tag} cash in US dollars: the total, no florin change: {box2!r}")
    await shot(pg, "driver-offline-390-dark.png")
    fake.down.clear()
    await ctx.set_offline(False)
    await pg.evaluate("window.dispatchEvent(new Event('online'))")
    await pg.wait_for_function("!document.querySelector('main .pending')", timeout=10000)
    check(fake.named("pidi_driver_delivered") == [{"session": DS, "order_id": O1}], f"{tag} back online: the saved tap goes out once, for drop 1")
    # error: the database refuses a tap; the screen says why and stays on the drop
    st["refuse"] = "TEST: this order was cancelled by the kitchen."
    await pg.click("#dock button")
    await pg.wait_for_selector("main .err")
    er = (await text(pg, "main .err"))[0]
    still = (await text(pg, "main .quiet"))[0]
    check(er == "TEST: this order was cancelled by the kitchen." and "Drop 2 of 2" in still, f"{tag} error: a refused tap says why and the drop stays: {er!r}")
    await shot(pg, "driver-error-390-dark.png")
    st.pop("refuse")
    await pg.click("#dock button")
    await pg.wait_for_selector("text=Run finished")
    done = (await text(pg, "main .money"))[0]
    check(fake.named("pidi_driver_delivered")[-1] == {"session": DS, "order_id": O2} and "Order 21: ƒ33.95 cash" in done and "Order 22: US dollars, ƒ32.00 total" in done,
          f"{tag} delivered: the run finishes with the cash from each drop: {done!r}")
    await shot(pg, "driver-done-390-dark.png")
    sess = {a.get("session") for n, a in fake.calls if n.startswith("pidi_driver_")}
    check(sess == {DS}, f"{tag} every driver call carried the driver session")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

async def driver_edges(b):
    tag = "[driver edges]"
    st = {"run": None, "none": True}
    fake = driver_fake(st)
    ctx = await new_ctx(b, fake, init=DINIT)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(BASE + DRIVER + "index.html")
    await pg.wait_for_selector("#offers .empty")
    emp = (await text(pg, "#offers .empty"))[0]
    check("No offer right now." in emp and "rings" in emp, f"{tag} empty: no offer, and a new run rings: {emp!r}")
    await shot(pg, "driver-empty-390-dark.png")
    fake.down.add("pidi_driver_offers")
    await pg.evaluate("window.dispatchEvent(new Event('online'))")
    await pg.wait_for_selector("#offers .err.soft")
    soft = (await text(pg, "#offers .err"))[0]
    check(soft.startswith("No signal.") and "keeps trying" in soft, f"{tag} offline: the offers say no signal and keep trying: {soft!r}")
    fake.down.clear()
    await ctx.close()
    # signed out: the sign-in screen; a refused sign-in keeps the name (no PIN is typed here)
    ctx = await new_ctx(b, fake)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(BASE + DRIVER + "index.html")
    await pg.wait_for_selector("#code")
    labels = await text(pg, ".field span")
    check(labels == ["Name", "PIN"], f"{tag} sign in: labels above the fields: {labels}")
    await shot(pg, "driver-signin-390-dark.png")
    await pg.fill("#code", "TEST driver")
    await pg.click("#dock button")
    await pg.wait_for_selector("main .err")
    er = (await text(pg, "main .err"))[0]
    kept = await pg.input_value("#code")
    check(er == "That PIN does not match." and kept == "TEST driver", f"{tag} sign-in error: plain words, the name stays typed: {er!r}")
    check(not fake.stray, f"{tag} nothing else went to the database or the internet" + (f": {fake.stray}" if fake.stray else ""))
    check(not errs, f"{tag} no page errors" + (f": {errs}" if errs else ""))
    await ctx.close()

# ================================================================== service workers and the live folders
async def workers(p):
    tag = "[workers]"
    # the order database's name points nowhere in this browser: nothing can reach the real one
    b = await p.chromium.launch(args=[f"--host-resolver-rules=MAP {DB_HOST} 127.0.0.1:9"])
    ctx = await b.new_context(viewport={"width": 390, "height": 844})
    await ctx.add_init_script(INIT)
    await ctx.route("https://cdn.jsdelivr.net/**", lambda r: r.fulfill(status=200, content_type="application/javascript", body=STUB))
    pg = await ctx.new_page()
    await pg.goto(BASE + "robots.txt")
    live = ["kitchen-v18", "pidi-driver-v5", "pidi-site-v17", "next-kitchen-v0", "next-driver-v0"]
    await pg.evaluate("names => Promise.all(names.map(n => caches.open(n).then(c => c.put('/x-' + n, new Response('x')))))", live)
    for path, scope in [(KITCHEN + "index.html", "/" + KITCHEN), (DRIVER + "index.html", "/" + DRIVER)]:
        await pg.goto(BASE + path)
        try:
            await pg.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=20000)
        except Exception:
            check(False, f"{tag} the preview's worker starts on /{path}")
            continue
        reg = await pg.evaluate("navigator.serviceWorker.getRegistration().then(r => [r.scope, r.active && r.active.scriptURL])")
        check(urlparse(reg[0]).path == scope and urlparse(reg[1]).path == scope + "sw.js", f"{tag} /{path} is served by its own worker, scope {scope} only: {reg}")
        await pg.wait_for_timeout(800)
    keys = await pg.evaluate("caches.keys()")
    check(all(k in keys for k in ["kitchen-v18", "pidi-driver-v5", "pidi-site-v17"]), f"{tag} the live apps' caches are all still there: {sorted(keys)}")
    check("next-kitchen-v0" not in keys and "next-driver-v0" not in keys and "next-kitchen-v1" in keys and "next-driver-v1" in keys,
          f"{tag} the previews keep only their own new next-… caches and delete only their own old ones: {sorted(keys)}")
    regs = await pg.evaluate("navigator.serviceWorker.getRegistrations().then(rs => rs.map(r => new URL(r.scope).pathname))")
    check(sorted(regs) == sorted(["/" + KITCHEN, "/" + DRIVER]), f"{tag} no preview worker sits on a live folder: {regs}")
    for live_page in ["ops/kitchen/index.html", "driver/v2/index.html", "index.html"]:
        await pg.goto(BASE + live_page)
        await pg.wait_for_timeout(1200)
        ctl = await pg.evaluate("navigator.serviceWorker.controller ? navigator.serviceWorker.controller.scriptURL : ''")
        check("-next" not in ctl, f"{tag} the live page /{live_page} is never run by a preview worker (controller: {urlparse(ctl).path or 'none yet'})")
    await b.close()
    for d in ["ops/kitchen-next", "driver-next"]:
        for root, _, files in os.walk(os.path.join(ROOT, d)):
            for f in files:
                if not f.endswith((".js", ".html", ".webmanifest")): continue
                src = open(os.path.join(root, f), encoding="utf-8").read()
                bad = [x for x in [r'register\(new URL\("\.\./\.\./sw\.js"', r"CACHE = ['\"](kitchen-|pidi-driver-|pidi-site-)", r"MINE = ['\"]kitchen-", r"eyJ[A-Za-z0-9_-]{20,}"] if re.search(x, src)]
                check(not bad, f"{tag} {d}/{f} names no live worker, no live cache and carries no key" + (f": {bad}" if bad else ""))
    diff = subprocess.run(["git", "diff", "--stat", "origin/main", "--", "ops/kitchen", "driver", "sw.js", "shared"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check(diff == "", f"{tag} ops/kitchen/, driver/, sw.js and shared/ are exactly what origin/main has" + (f": {diff}" if diff else ""))

# ================================================================== screenshots: 390 and 1024, light and dark
async def gallery(b):
    for scheme in ["dark", "light"]:
        for w, h in [(390, 844), (1024, 768)]:
            state = {"orders": [order(O3, 41, "new", 0, name="TEST Ana", note="TEST: ring twice"),
                                order(O1, 39, "cooking", 12, test=True),
                                order(O2, 40, "accepted", 3, name="TEST Carlos", pay="transfer", transfer_status="awaiting", pays_with_cents=None, change_due_cents=None,
                                      restaurants=[{"restaurant": "Taco Brava", "slug": "taco-brava", "food_cents": 2700, "ready": False,
                                                    "items": [item("Birria tacos (3) with consommé", 1, 2700)]}])]}
            fake = kitchen_fake(state)
            ctx = await new_ctx(b, fake, w, h, scheme, KINIT)
            pg = await ctx.new_page()
            await pg.goto(BASE + KITCHEN + "index.html#/live")
            await pg.wait_for_selector(".lv-card")
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=os.path.join(SHOTS, f"kitchen-orders-{w}-{scheme}.png"))
            await pg.evaluate("location.hash = '#/'")
            await pg.wait_for_selector(".home-grid")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=os.path.join(SHOTS, f"kitchen-home-{w}-{scheme}.png"))
            await ctx.close()
            st = {"run": None}
            fake = driver_fake(st)
            ctx = await new_ctx(b, fake, w, h, scheme, DINIT)
            pg = await ctx.new_page()
            await pg.goto(BASE + DRIVER + "index.html")
            await pg.wait_for_selector("#offers .stop")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=os.path.join(SHOTS, f"driver-offer-{w}-{scheme}.png"))
            await pg.click("#dock button")
            await pg.wait_for_selector(".bagslip")
            await pg.click("#dock button")
            await pg.wait_for_function("/Drop 1 of 2/.test((document.querySelector('main .quiet') || {}).textContent || '')")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=os.path.join(SHOTS, f"driver-drop-{w}-{scheme}.png"))
            await ctx.close()
    check(True, f"[gallery] screenshots saved in {SHOTS}")

# ================================================================== the ~20 s phone recording
async def record(b):
    tmp = tempfile.mkdtemp()
    state = {"orders": []}
    kf = kitchen_fake(state)
    st = {"run": None}
    df = driver_fake(st)
    both = Fake({**kf.answers, **df.answers})
    ctx = await new_ctx(b, both, 390, 844, "dark", KINIT + DINIT, video=tmp)
    pg = await ctx.new_page()
    await pg.goto(BASE + KITCHEN + "index.html#/live")
    await pg.wait_for_selector(".lv-empty")
    await pg.wait_for_timeout(1800)
    state["orders"].append(order(O1, 21, "new", 0))
    await refresh(pg)
    await pg.wait_for_timeout(2200)
    for sel, pause in [(f"[data-live='accept'][data-id='{O1}']", 1600), (f"[data-live='cooking'][data-id='{O1}']", 1600), (f"[data-live='ready'][data-id='{O1}']", 1800)]:
        await pg.click(sel)
        await pg.wait_for_timeout(pause)
    await pg.goto(BASE + DRIVER + "index.html")
    await pg.wait_for_selector("#offers .stop")
    await pg.wait_for_timeout(2200)
    await pg.click("#dock button")
    await pg.wait_for_selector(".bagslip")
    await pg.wait_for_timeout(1800)
    await pg.click("#dock button")
    await pg.wait_for_function("/Drop 1 of 2/.test((document.querySelector('main .quiet') || {}).textContent || '')")
    await pg.wait_for_timeout(2600)
    await pg.click("#dock button")
    await pg.wait_for_timeout(1400)
    await pg.click("#dock button")
    await pg.wait_for_selector("text=Run finished")
    await pg.wait_for_timeout(1800)
    raw = await pg.video.path()
    await ctx.close()
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-movflags", "+faststart", "-an", VIDEO],
                       capture_output=True, text=True)
    check(r.returncode == 0 and os.path.exists(VIDEO), f"[recording] saved {VIDEO}" + (f": {r.stderr[:200]}" if r.returncode else ""))

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for t in (kitchen_flow, kitchen_trouble, driver_flow, driver_edges):
            try:
                await t(b)
            except Exception as e:
                check(False, f"{t.__name__} crashed: {type(e).__name__}: {str(e)[:300]}")
        if SHOTS:
            await gallery(b)
        if VIDEO:
            await record(b)
        await b.close()
        await workers(p)

asyncio.run(main())
print(f"\n{len(passes)} passed, {len(fails)} problem(s) on the part 2 previews")
sys.exit(1 if fails else 0)
