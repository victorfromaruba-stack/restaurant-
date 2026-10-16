"""Chef app check: python3 qa/check_kitchen.py from the repo folder (Python Playwright 1.56.0 and Pillow).
It serves the repo itself (any free port; QA_PORT=<n> picks one) and never calls GitHub, Book Keeper or the
order database: the browser gets fake answers for those. QA_SHOTS=<folder> saves 390px phone screenshots.

What it proves (pre-launch audit, 16 Oct 2026):
 1. two WhatsApp orders in one paste are refused, never merged into one
 2. ticket lines reach the right recipe card: restaurant + exact name on the website's menu, then the menu id.
    A new dish without a card says "No recipe card yet" with the menu's words; a renamed dish shows
    "Ticket says: ..."; a close name only ever matches inside its own restaurant
 3. a dish whose picture is hidden on the website ("hidePhoto") shows no picture in the chef app
 4. a chosen time reads "Deliver at <the ticket's time>"
 5. WhatsApp copy marks and "[22:14, 15/10/2026] Ana: " prefixes are ignored; the receipt finds the restaurant
 6. "Replaces order #..." puts a red banner on the new order and marks the old one; nothing is deleted
 7. "Orders" (the app's orders, live) is the first tile and "Cook an order" the second; both say when the
    order database couldn't be checked
 8. the offline cache answers within about 3 s on a slow network, keeps other apps' caches, and has site.json
 9. a Book Keeper 504, a non-JSON 5xx or a dropped connection = "may have arrived, don't send again"
10. menu editor: fine-grained keys only, a confirm step before Open / Opening soon / Hidden, plain errors
11. replies use site.json's delivery time, never offer pickup, and count a Family Table as one dish
12. a Menu-tile save on a phone signed in to Orders goes to the order database at once (it prices the orders)
Plus: every ticket in qa/wa-samples.json, and fresh tickets built by the customer site's own code for every
dish of every restaurant, parse to the right cards with the right totals."""
import asyncio, base64, copy, http.server, json, os, re, sys, tempfile, threading, time
from playwright.async_api import async_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.environ.get("QA_SHOTS", "")
fails = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)


# ------------------------------------------------------------------ a local server that can be slow on purpose
DELAY = {}   # path ending -> seconds to wait before answering (a weak kitchen signal)
HITS = {}    # path ending -> requests seen while delayed


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        for end, sec in list(DELAY.items()):
            if path.endswith(end):
                HITS[end] = HITS.get(end, 0) + 1
                time.sleep(sec)
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


srv = Server(("127.0.0.1", int(os.environ.get("QA_PORT", "0"))), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
APP = BASE + "ops/kitchen/index.html"

site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
brands = [b["id"] for b in site["brands"]]
menus = {b: json.load(open(os.path.join(ROOT, b, "menu.json"), encoding="utf-8")) for b in brands}
kdata = json.load(open(os.path.join(ROOT, "ops/kitchen/kitchen-data.json"), encoding="utf-8"))
samples = json.load(open(os.path.join(ROOT, "qa/wa-samples.json"), encoding="utf-8"))["samples"]
names = {b: menus[b]["name"] for b in brands}
LEAKS = ("one kitchen", "shared kitchen", "same kitchen", "from our kitchen", "our other restaurant", "sister restaurant", "all five", "kitchen order")


def expected_key(brand, name):
    """The recipe card a ticket line must reach: same restaurant (or any, for drinks), exact menu name."""
    for b in ([brand] if brand else []) + brands:
        for it in menus[b]["items"]:
            if it["name"] == name:
                return ("drink/" if it.get("kind") == "drink" else b + "/") + it["id"]
    return None


def card_count(key):
    d = kdata["dishes"][key]
    return (1 if d.get("ahead") else 0) + (1 if d.get("before") else 0) + len(d.get("steps") or []) + 2


EXTERNAL = re.compile(r"^https://(api\.github\.com|bookingkeepingaruba\.vercel\.app|[a-z0-9-]+\.supabase\.co)/")


async def new_ctx(browser, fake=None, sw="block"):
    """A phone. Anything outside this server is faked by `fake(route)` (returns True when it answered) or refused."""
    ctx = await browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers=sw)
    calls = []

    async def outside(route):
        req = route.request
        calls.append((req.method, req.url))
        if fake and await fake(route):
            return
        await route.abort()
    await ctx.route(EXTERNAL, outside)
    return ctx, calls


async def new_page(ctx, errs):
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(f"page error: {e}"))
    return pg


async def open_app(pg, hash_=""):
    await pg.goto(APP + hash_)
    await pg.wait_for_function("window.__kitchen && __kitchen.menus() !== null && !!document.querySelector('#bar b')", timeout=20000)
    await pg.wait_for_timeout(150)


async def shot(pg, name, bottom=False):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        await pg.evaluate("document.getElementById('toast').hidden = true")   # a passing message would cover the screen
        if bottom:
            await pg.evaluate("document.getElementById('main').scrollTop = 1e6; window.scrollTo(0, 1e6)")
        await pg.screenshot(path=os.path.join(SHOTS, name + ".png"))


async def paste(pg, text):
    await pg.evaluate("location.hash = '#/cook'")
    await pg.wait_for_selector("#paste")
    await pg.fill("#paste", text)
    await pg.click("[data-act=read]")
    await pg.wait_for_function("!!document.querySelector('#main .order-wrap, #main .err')")
    await pg.wait_for_timeout(150)


async def text(pg, sel):
    return await pg.evaluate("s => Array.from(document.querySelectorAll(s)).map(e => e.innerText).join('\\n')", sel)


async def orders(pg):
    return await pg.evaluate("JSON.parse(localStorage.getItem('kitchen.orders.v1') || '[]')")


async def parse(pg, t):
    return await pg.evaluate("t => __kitchen.parse(t)", t)


def ticket_ok(o, label, want_sub=None, want_fee=None, want_total=None):
    lines = o["lines"]
    want = [expected_key(l["brandId"], l["raw"]) for l in lines]
    got = [l["key"] for l in lines]
    check(bool(lines) and got == want and all(got), f"[{label}] every line reaches its own recipe card" + ("" if got == want else f": got {got}, want {want}"))
    check(not any(i.get("unknown") or i.get("nocard") for i in o["items"]), f"[{label}] no line left unmatched")
    if want_sub is not None:
        check(o.get("subtotalC") == want_sub and o.get("feeC") == want_fee and o.get("totalC") == want_total
              and sum(l["price"] for l in lines) == want_sub,
              f"[{label}] totals read right (ƒ{want_total / 100:.2f})")
    check(not o.get("twoOrders"), f"[{label}] one order, not two")


# ------------------------------------------------------------------ the tickets
async def test_tickets(browser):
    errs = []
    ctx, _ = await new_ctx(browser)
    pg = await new_page(ctx, errs)
    await open_app(pg)
    check(sorted(await pg.evaluate("__kitchen.menus()")) == sorted(brands), "the chef app loads every restaurant's menu.json (soon and hidden ones too)")
    for s in samples:
        o = await parse(pg, s["message"])
        ticket_ok(o, "wa-samples: " + s["case"], s["subtotal_cents"], s["fee_cents"], s["total_cents"])
        r = await pg.evaluate("t => __kitchen.receipt(__kitchen.parse(t))", s["message"])
        check(bool(r) and r["total"] == s["total_cents"] and r["feeLabel"] == "Delivery", f"[wa-samples: {s['case']}] receipt total ƒ{s['total_cents'] / 100:.2f}, delivery")

    # fresh tickets from the customer site's own code: every dish of every restaurant, plus mixed orders with options
    gen, _ = await new_ctx(browser)
    open_site = copy.deepcopy(site)
    for b in open_site["brands"]:
        b["status"] = "open"
    await gen.route("**/shared/site.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(open_site)))
    gp = await new_page(gen, errs)
    await gp.goto(BASE + "taco-brava/index.html", wait_until="networkidle")
    meta = {"area": "Noord", "addr": "Palm Beach 12", "name": "Ana", "note": "", "pay": "Cash"}

    async def build(lines):
        await gp.evaluate("OrderApp.clear()")
        added = 0
        for (b, iid, opts, q) in lines:
            added += 1 if await gp.evaluate("([b,i,o,q]) => OrderApp.loadMenu(b).then(() => !!OrderApp.addItem(b,i,o,q))", [b, iid, opts, q]) else 0
        await gp.evaluate("m => OrderApp._set(m)", meta)
        return added, await gp.evaluate("OrderApp.buildMessage()"), await gp.evaluate("[OrderApp.subtotal(), OrderApp.fee(), OrderApp.total()]")
    built = []
    for b in brands:
        food = [(b, i["id"], {}, 1) for i in menus[b]["items"] if i.get("kind") != "drink" and not i.get("soldOut")]
        built.append((f"every {names[b]} dish", food + [(b, "ck", {}, 1), (b, "sp", {}, 2)]))
    built += [
        ("Dushi Wok options and a can", [("dushi-wok", "fr", {"leave": ["onion", "egg"]}, 2), ("dushi-wok", "ss", {"sauce": "on-the-side"}, 1), ("dushi-wok", "ck", {}, 1)]),
        ("three restaurants with a Family Table", [("dushi-wok", "ft", {}, 1), ("taco-brava", "bt", {}, 1), ("oranje-snack", "bb", {"dip": "mustard"}, 2),
                                                  ("taco-brava", "ck", {}, 1), ("taco-brava", "cz", {}, 1), ("taco-brava", "sp", {}, 2)]),
        ("all five restaurants", [(b, next(i["id"] for i in menus[b]["items"] if i.get("kind") != "drink"), {}, 1) for b in brands] + [("smash-shack", "cz", {}, 3)]),
    ]
    for label, lines in built:
        added, msg, (sub, fee, tot) = await build(lines)
        check(added == len(lines), f"[{label}] the customer site built the ticket ({added}/{len(lines)} lines)")
        o = await parse(pg, msg)
        ticket_ok(o, label, sub, fee, tot)
        ft = [i for i in o["items"] if (i.get("bundle") or {}).get("key") == "dushi-wok/ft"]
        if any(l["key"] == "dushi-wok/ft" for l in o["lines"]):
            check([i["key"] for i in ft] == kdata["dishes"]["dushi-wok/ft"]["includes"], f"[{label}] the Family Table opens into its three dishes")
    await gen.close()
    check(not errs, "no script errors while reading tickets" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 1 two orders, 4 deliver at, 5 copy marks, 6 replaces, 11 replies
async def test_orders(browser):
    errs = []
    ctx, _ = await new_ctx(browser)
    pg = await new_page(ctx, errs)
    await open_app(pg)

    # 1. two orders in one paste
    two = samples[0]["message"] + "\n\n" + samples[1]["message"]
    check((await parse(pg, two)).get("twoOrders") is True, "[1] two tickets pasted together are seen as two orders")
    copied = "[22:14, 15/10/2026] Carla: " + samples[0]["message"] + "\n[22:16, 15/10/2026] Eva: " + samples[1]["message"]
    await paste(pg, copied)
    err = await text(pg, "#main .err")
    check(err == "Two orders in one paste. Paste them one at a time." and not await orders(pg),
          f"[1] pasting two WhatsApp orders at once stops with a clear message and makes no order: {err!r}")
    await shot(pg, "1-two-orders")

    # 4. the time the customer picked is when it must be at the door
    await paste(pg, samples[0]["message"])
    when = await text(pg, ".ohead .when")
    body = await text(pg, "#main")
    picked = re.search(r"^Time: (.+)$", samples[0]["message"], re.M).group(1).replace("\u00a0", " ").strip()
    check(when.replace("\u00a0", " ") == "Deliver at " + picked and "Ready for" not in body, f"[4] a chosen time reads 'Deliver at {picked}': {when!r}")
    check("pickup" not in body.lower(), "[11] the order screen never mentions pickup")
    await shot(pg, "4-deliver-at")

    # 5. WhatsApp's invisible marks and "[time, date] Name:" prefixes
    clean = samples[1]["message"]
    rows = clean.split("\n")
    dirty_variants = {
        "Android copy": "\n".join(["[22:14, 15/10/2026] Eva: ‎" + rows[0]] + [("‎‪" + r + "‬") if r else r for r in rows[1:]]),
        "iPhone copy": "\n".join(["[15/10/26, 22:14:05] Eva: ‏" + rows[0]] + [("⁦" + r + "⁩") if r else r for r in rows[1:]]),
        "exported chat": "\n".join(["15/10/2026, 22:14 - Eva: " + rows[0]] + rows[1:]),
    }
    want = await parse(pg, clean)
    keyset = lambda o: (o["no"], o["brandId"], [l["key"] for l in o["lines"]], [l["price"] for l in o["lines"]], o.get("totalC"), o["name"], o["address"], o.get("pay"), o.get("time"), o["other"])
    for label, t in dirty_variants.items():
        got = await parse(pg, t)
        check(keyset(got) == keyset(want) and got["no"], f"[5] {label} with direction marks reads the same as the clean ticket" + ("" if keyset(got) == keyset(want) else f": {keyset(got)}"))
    odd = ("*Taco Brava Aruba order* #2314-K7\nDelivery · Noord\n\n1 × Birria tacos (3) with consommé — ƒ27.00\n1 × Chips & salsa — ƒ5.50\n\n"
           "Subtotal ƒ32.50\nDelivery ƒ5.00\n*Total ƒ37.50*\nPay: Cash\n\nName: Ana\nAddress: Noord 12")
    o = await parse(pg, odd)
    r = await pg.evaluate("t => __kitchen.receipt(__kitchen.parse(t))", odd)
    rt = await pg.evaluate("t => __kitchen.receiptText(__kitchen.parse(t))", odd)
    check(o["brandId"] is None and [l["key"] for l in o["lines"]] == ["taco-brava/bt", "taco-brava/cs"] and r["brands"] == ["Taco Brava"] and "Taco Brava" in rt,
          f"[5] header not recognised: the receipt still names the dish's own restaurant ({r['brands']})")

    # 6. "Replaces order #2300-EC"
    a = ("*Taco Brava order* #2300-EC\nDelivery · Noord\nTime: As soon as possible\n\n1 × Chicken quesadilla — ƒ16.00\n\n"
         "Subtotal ƒ16.00\nDelivery ƒ5.00\n*Total ƒ21.00*\nPay: Cash\n\nName: Ana\nAddress: Noord 12")
    b = ("*Taco Brava order* #2314-K7\nReplaces order #2300-EC\nDelivery · Noord\nTime: As soon as possible\n\n2 × Chicken quesadilla — ƒ32.00\n\n"
         "Subtotal ƒ32.00\nDelivery ƒ5.00\n*Total ƒ37.00*\nPay: Cash\n\nName: Ana\nAddress: Noord 12")
    ob = await parse(pg, b)
    check(ob.get("replaces") == "2300-EC" and not ob.get("twoOrders") and ob["no"] == "2314-K7" and ob.get("totalC") == 3700,
          "[6] 'Replaces order #2300-EC' is read as a note on this order, not as a second order")
    await pg.evaluate("localStorage.removeItem('kitchen.orders.v1')")
    await paste(pg, a)
    await paste(pg, b)
    ban = await text(pg, "#main .banner.replaces")
    check("Replaces order #2300-EC: don’t cook that one twice" in ban and "#2300-EC is still open here" in ban,
          f"[6] the new order has a red banner: {ban!r}")
    check(await pg.evaluate("getComputedStyle(document.querySelector('#main .banner.replaces')).backgroundColor") == "rgb(229, 56, 59)", "[6] the banner is red")
    await shot(pg, "6-replaces-banner")
    await pg.evaluate("location.hash = '#/cook'")
    await pg.wait_for_selector(".open-orders")
    flagged = await text(pg, ".oo--replaced")
    allo = await orders(pg)
    check("Replaced by #2314-K7" in flagged and "#2300-EC" in flagged.upper() and len(allo) == 2,
          f"[6] the old order is marked on the list and nothing was deleted ({len(allo)} orders): {flagged!r}")
    await shot(pg, "6-replaced-on-list")
    old = next(x for x in allo if x["no"] == "2300-EC")
    await pg.evaluate(f"location.hash = '#/order/{old['id']}'")
    await pg.wait_for_selector("#main .order-wrap")
    check("Replaced by order #2314-K7: don’t cook this one" in await text(pg, "#main .banner.replaces"), "[6] the old order says it was replaced")

    # 11. replies: delivery time from site.json, a Family Table is one dish, never pickup
    ft = ("*Dushi Wok order* #2320-FT\nDelivery · Noord\nTime: As soon as possible\n\n1 × Family Table — ƒ42.50\n"
          "   Includes: Chicken fried rice, Sweet & sour crunch chicken with rice, Chicken lo mein\n2 × Egg rolls (2) — ƒ9.00\n1 × Sprite (can) — ƒ3.00\n\n"
          "Subtotal ƒ54.50\nDelivery ƒ5.00\n*Total ƒ59.50*\nPay: Cash\n\nName: Ben\nAddress: Noord 4")
    rep = await pg.evaluate("t => __kitchen.replies(__kitchen.parse(t))", ft)
    allrep = " ".join(x["t"] for x in rep).lower()
    cook = next(x["t"] for x in rep if x["k"] == "Cooking")
    conf = next(x["t"] for x in rep if x["k"] == "Confirm")
    check(cook.endswith(": Family Table and 1 more."), f"[11] the Cooking reply counts order lines (a Family Table is one dish): {cook!r}")
    check(("about " + site["eta"]) in conf, f"[11] the Confirm reply takes the delivery time from site.json ({site['eta']}): {conf!r}")
    rt = await pg.evaluate("t => __kitchen.receiptText(__kitchen.parse(t))", ft)
    check("pickup" not in allrep and "pickup" not in rt.lower() and not [w for w in LEAKS if w in allrep or w in rt.lower()],
          "[11] replies and receipt never mention pickup or a shared kitchen")
    pick = await parse(pg, a.replace("Delivery · Noord", "Pickup"))
    rep2 = await pg.evaluate("t => __kitchen.replies(__kitchen.parse(t))", a.replace("Delivery · Noord", "Pickup"))
    check(pick.get("pickup") is True and "pickup" not in " ".join(x["t"] + x["k"] for x in rep2).lower(),
          "[11] a hand-typed 'Pickup' is flagged for the chef, and the replies still only offer delivery")
    check(not errs, "no script errors on the order screens" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 2 matching, 3 hidden pictures
async def test_matching(browser):
    errs = []
    ctx, _ = await new_ctx(browser)
    dw = copy.deepcopy(menus["dushi-wok"])
    for it in dw["items"]:
        if it["id"] == "lm":
            it["name"] = "Chicken chow mein"   # renamed on the Menu tile: same id, same recipe card
    sec = next(i["section"] for i in dw["items"] if i["id"] == "fr")
    dw["items"].insert(1, {"id": "sl", "name": "Shrimp lo mein", "section": sec, "price": 1750, "img": "dushi-wok/assets/dishes/lm.webp",
                           "desc": "Egg noodles with garlic shrimp, cabbage and scallion.", "allergens": ["gluten", "egg", "soy", "shellfish"], "flags": ["shrimp"]})
    osn = copy.deepcopy(menus["oranje-snack"])
    sec = next(i["section"] for i in osn["items"] if i["id"] == "fs")
    osn["items"].insert(1, {"id": "lf", "name": "Loaded fries", "section": sec, "price": 950, "img": "oranje-snack/assets/art/fs.webp",
                            "desc": "Fries with cheese sauce and fried onion.", "allergens": ["dairy"]})
    await ctx.route("**/dushi-wok/menu.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(dw)))
    await ctx.route("**/oranje-snack/menu.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(osn)))
    pg = await new_page(ctx, errs)
    await open_app(pg)

    t1 = ("*Dushi Wok order* #2201-AB\nDelivery · Noord\nTime: As soon as possible\n\n1 × Shrimp lo mein — ƒ17.50\n1 × Chicken chow mein — ƒ16.50\n   No egg\n\n"
          "Subtotal ƒ34.00\nDelivery ƒ5.00\n*Total ƒ39.00*\nPay: Cash\n\nName: Dana\nAddress: Palm Beach 3\nNote: allergic to shrimp")
    o = await parse(pg, t1)
    i0, i1 = o["items"][0], o["items"][1]
    check(i0.get("nocard") and i0["key"] is None and i0["brand"] == "dushi-wok" and i0["name"] == "Shrimp lo mein" and "garlic shrimp" in i0["info"]["desc"],
          f"[2] a new dish with no recipe card stays itself, with the menu's words (not Chicken lo mein): {i0}")
    check(i1["key"] == "dushi-wok/lm" and i1.get("ticket") == "Chicken chow mein" and not i1.get("fuzzy"),
          f"[2] a renamed dish reaches its own card by menu id, and keeps the ticket's name: {i1.get('key')}, {i1.get('ticket')!r}")
    t2 = ("*Oranje Snack order* #2202-CD\nDelivery · Noord\n\n1 × Loaded fries — ƒ9.50\n1 × Chicken tenders & fries — ƒ15.50\n\n"
          "Subtotal ƒ25.00\nDelivery ƒ5.00\n*Total ƒ30.00*")
    o = await parse(pg, t2)
    check(o["items"][0].get("nocard") and o["items"][0]["brand"] == "oranje-snack" and o["items"][0]["key"] is None,
          "[2] Oranje Snack's new 'Loaded fries' is never Smash Shack's card")
    check(o["items"][1].get("unknown") and o["items"][1]["key"] is None, "[2] a dish another restaurant sells is never matched across restaurants")
    t3 = ("*Order* #2203-EF · 2 restaurants\nDelivery · Noord\n\n*Smash Shack*\n1 × Loaded fries (cheddar sauce, beef, scallion) — ƒ11.95\n"
          "*Oranje Snack*\n1 × Loaded fries — ƒ9.50\n*Drinks*\n1 × Coca-Cola (can) — ƒ3.00\n\nSubtotal ƒ24.45\nDelivery ƒ5.00\n*Total ƒ29.45*")
    o = await parse(pg, t3)
    got = [(l["key"], (l.get("menu") or {}).get("b")) for l in o["lines"]]
    check([g[0] for g in got] == ["smash-shack/lf", None, "drink/ck"] and got[1][1] == "oranje-snack" and o["items"][1].get("nocard"),
          f"[2] mixed ticket: each restaurant's section decides the card: {got}")
    t4 = "*Smash Shack order* #2204-GH\nDelivery · Noord\n\n1 × Smash cheeseburgers — ƒ16.95\n\nSubtotal ƒ16.95\nDelivery ƒ5.00\n*Total ƒ21.95*"
    o = await parse(pg, t4)
    it = o["items"][0]
    check(it["key"] == "smash-shack/sc" and it.get("fuzzy") and it.get("ticket") == "Smash cheeseburgers",
          "[2] a close name matches only inside its own restaurant, and is flagged")

    # on screen: the plain line, the warning chip, and "Ticket says" on every step
    await paste(pg, t1)
    body = (await text(pg, "#main")).replace("\n", " ").lower()   # innerText follows CSS uppercase
    check("no recipe card yet" in body and "egg noodles with garlic shrimp" in body and "contains: gluten · egg · soy · shellfish" in body,
          "[2] the order screen shows 'No recipe card yet' with the menu's description and allergens")
    check("NOTE SAYS SHELLFISH!" in (await text(pg, "#main .item.nocard .chip.warn")).upper(), "[2] the allergy note still warns on a dish with no card")
    await shot(pg, "2-no-recipe-card")
    oid = (await orders(pg))[-1]["id"]
    n = card_count("dushi-wok/lm")
    said = []
    for step in (0, n - 1):
        await pg.evaluate(f"location.hash = '#/order/{oid}/1/{step}'")
        await pg.wait_for_selector("#main .card")
        said.append(await text(pg, "#main .banner.said"))
        if step == 0:
            await shot(pg, "2-ticket-says")
    check(all(s.startswith("Ticket says: Chicken chow mein") for s in said), f"[2] 'Ticket says: Chicken chow mein' on the first and last step: {said}")
    await paste(pg, t4)
    oid = (await orders(pg))[-1]["id"]
    await pg.evaluate(f"location.hash = '#/order/{oid}/0/0'")
    await pg.wait_for_selector("#main .card")
    s = await text(pg, "#main .banner.said")
    check("Ticket says: Smash cheeseburgers" in s and "right dish" in s, f"[2] a close-name match asks the chef to check: {s!r}")
    await shot(pg, "2-close-name")
    check(not errs, "no script errors with changed menus" + (f": {errs}" if errs else ""))
    await ctx.close()

    # menus that don't load: the cards' own names still match exactly
    ctx, _ = await new_ctx(browser)
    await ctx.route("**/menu.json", lambda r: r.abort())
    pg = await new_page(ctx, errs)
    await open_app(pg)
    for s in samples:
        ticket_ok(await parse(pg, s["message"]), "menus not loaded: " + s["case"], s["subtotal_cents"], s["fee_cents"], s["total_cents"])
    await ctx.close()

    # 3. hidePhoto: no picture anywhere in the chef app, every step kept
    ctx, _ = await new_ctx(browser)
    pg = await new_page(ctx, errs)
    await open_app(pg)
    hidden = [f"{b}/{i['id']}" for b in brands for i in menus[b]["items"] if i.get("hidePhoto") and f"{b}/{i['id']}" in kdata["dishes"]]
    shown = [f"{b}/{i['id']}" for b in brands for i in menus[b]["items"] if not i.get("hidePhoto") and i.get("kind") != "drink" and f"{b}/{i['id']}" in kdata["dishes"]]
    imgs = {k: await pg.evaluate("k => __kitchen.img(k)", k) for k in hidden + shown}
    check(hidden and all(imgs[k] is None for k in hidden), f"[3] dishes with hidePhoto have no picture in the chef app: {hidden}")
    check(all(imgs[k] for k in shown), "[3] every other dish keeps its picture")
    bad = ["../../" + i["img"] for b in brands for i in menus[b]["items"] if i.get("hidePhoto")]
    burger = samples[0]["message"] if "Smash cheeseburger" in samples[0]["message"] else \
        "*Smash Shack order* #2210-SC\nDelivery · Noord\n\n1 × Smash cheeseburger — ƒ16.95\n\nSubtotal ƒ16.95\nDelivery ƒ5.00\n*Total ƒ21.95*"
    await paste(pg, burger)
    srcs = await pg.evaluate("Array.from(document.querySelectorAll('#main img')).map(i => i.getAttribute('src'))")
    row = await pg.evaluate("(() => { const a = Array.from(document.querySelectorAll('#main a.item')).find(x => /Smash cheeseburger/.test(x.innerText)); return a ? [a.querySelector('.ph').className, !!a.querySelector('img')] : null; })()")
    check(row and "noimg" in row[0] and not row[1] and not [s for s in srcs if s in bad], f"[3] the order list shows the burger without its wrong picture: {row}")
    oid = (await orders(pg))[-1]["id"]
    idx = next(i for i, x in enumerate((await orders(pg))[-1]["items"]) if x["key"] == "smash-shack/sc")
    await pg.evaluate(f"location.hash = '#/order/{oid}/{idx}/0'")
    await pg.wait_for_selector("#main .card")
    prog = await text(pg, ".prog b")
    hero = await pg.evaluate("[document.querySelector('#main .card .ph.hero').className, document.querySelectorAll('#main .card img').length]")
    check("noimg" in hero[0] and hero[1] == 0 and prog.lower() == f"step 1 of {card_count('smash-shack/sc')}", f"[3] the cook card has no picture and keeps every step ({prog})")
    await shot(pg, "3-no-picture-step")
    await pg.evaluate("location.hash = '#/cook'")
    await pg.wait_for_selector(".grid")
    tile = await pg.evaluate("!!document.querySelector('[data-key=\"smash-shack/sc\"] img')")
    srcs = await pg.evaluate("Array.from(document.querySelectorAll('#main img')).map(i => i.getAttribute('src'))")
    check(not tile and not [s for s in srcs if s in bad], "[3] the 'Or pick dishes' tiles show no hidden picture")
    check(not errs, "no script errors on cook cards" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 7 the Orders tile
async def test_live(browser):
    errs = []

    async def fake(route):
        await route.abort("connectionrefused")   # the order database can't be reached
        return True
    ctx, calls = await new_ctx(browser, fake)
    pg = await new_page(ctx, errs)
    await pg.goto(BASE + "robots.txt")
    await pg.evaluate("localStorage.setItem('pidi.kitchen.session', JSON.stringify({token: 'test', expires_at: '2099-01-01T00:00:00Z', topic: 't'}))")
    await open_app(pg)
    await pg.wait_for_function("/Couldn/.test((document.getElementById('liveCount') || {}).textContent || '')", timeout=10000)
    tiles = await pg.evaluate("Array.from(document.querySelectorAll('.home-grid > a')).map(a => a.className.replace('big-mode ', '') + '|' + a.innerText.replace(/\\n/g, ' '))")
    check(tiles[0].startswith("live") and tiles[1].startswith("cook|"), f"[7] 'Orders' is the first tile, 'Cook an order' the second: {tiles[:2]!r}")
    live = tiles[0] if tiles[0].startswith("live") else ""
    check(live.upper().startswith("LIVE LV-FAILED|ORDERS") and "test" not in live.lower() and "WhatsApp" not in live,
          f"[7] the Orders tile is the real thing (no test label, no pointer to WhatsApp): {live!r}")
    check("Couldn’t check" in live, f"[7] a failed check says so on the tile instead of an old count: {live!r}")
    await shot(pg, "7-home")
    await shot(pg, "7-home-bottom", bottom=True)
    await pg.evaluate("location.hash = '#/live'")
    await pg.wait_for_function("/Couldn/.test(document.querySelector('#main').innerText)", timeout=10000)
    body = await text(pg, "#main")
    bar = await text(pg, "#bar")
    check("Couldn’t check" in body and "ORDERS" in bar.upper() and "test" not in (bar + body).lower(),
          f"[7] the Orders screen shows the failed check and no test label: {bar!r} / {body[:80]!r}")
    check(all("supabase.co" in u for _, u in calls), "[7] only the (faked) order database was called")
    await shot(pg, "7-orders")
    check(not errs, "no script errors on Orders" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 9 Book Keeper
async def test_books(browser):
    errs = []
    answer = {"mode": "504"}

    async def fake(route):
        if "bookingkeepingaruba.vercel.app" not in route.request.url:
            return False
        m = answer["mode"]
        if m == "504":
            await route.fulfill(status=504, content_type="text/html", body="<html><body>Gateway Timeout</body></html>")
        elif m == "502json":
            await route.fulfill(status=502, content_type="application/json", body='{"error":"Bad gateway"}')
        elif m == "500json":
            await route.fulfill(status=500, content_type="application/json", body='{"error":"Database error"}')
        elif m == "drop":
            await route.abort("connectionreset")
        else:
            await route.fulfill(status=201, content_type="application/json", body='{"status":"pending_review"}')
        return True
    ctx, calls = await new_ctx(browser, fake)
    pg = await new_page(ctx, errs)
    photo = os.path.join(tempfile.mkdtemp(), "receipt.jpg")
    Image.new("RGB", (600, 900), (245, 240, 230)).save(photo, "JPEG")
    await pg.goto(BASE + "robots.txt")
    await pg.evaluate("localStorage.setItem('kitchen.books.v1', JSON.stringify({key: 'bk_live_' + 'a'.repeat(43)}))")
    await open_app(pg, "#/receipts")

    async def send(mode):
        answer["mode"] = mode
        await pg.evaluate("location.hash = '#/'")
        await pg.evaluate("location.hash = '#/receipts'")
        await pg.wait_for_selector(".bk-file", state="attached")
        await pg.set_input_files(".bk-file >> nth=0", photo)
        await pg.wait_for_selector("[data-bact=send]")
        await pg.click("[data-bact=send]")
        await pg.wait_for_function("!document.getElementById('sheet').hidden || /Book Keeper|Sent/.test(document.getElementById('toast').textContent) && !document.getElementById('toast').hidden", timeout=15000)
        await pg.wait_for_timeout(200)
        sheet = await text(pg, "#sheet")
        toast = await pg.evaluate("document.getElementById('toast').hidden ? '' : document.getElementById('toast').textContent")
        return sheet, toast
    for mode, label in (("504", "a 504 gateway timeout"), ("502json", "a 502"), ("drop", "the connection dropping mid-upload")):
        sheet, toast = await send(mode)
        check("may have arrived anyway" in sheet and "Don’t send it again" in sheet and "send it again" not in toast.lower(),
              f"[9] {label}: 'may have arrived, check Book Keeper first', never 'send again': {sheet.splitlines()[:2]}")
        if mode == "504":
            await shot(pg, "9-books-unsure")
        await pg.evaluate("document.querySelector('[data-act=closesheet]') && document.querySelector('[data-act=closesheet]').click()")
    sheet, toast = await send("500json")
    check(not sheet and "had a problem and didn’t take it" in toast, f"[9] Book Keeper's own 500 answer still says it didn't take it: {toast!r}")
    sent = await pg.evaluate("JSON.parse(localStorage.getItem('kitchen.books.sent.v1') || '[]').map(x => x.s)")
    check(sent == ["unsure"] * 3, f"[9] the three unsure sends are listed as 'check Book Keeper before sending again' ({sent})")
    await pg.evaluate("document.querySelector('[data-bact=again]').click()")   # the 500 one is still waiting to be sent: back to the list
    await pg.wait_for_timeout(200)
    hist = await text(pg, "#main")
    check(hist.count("No answer: check Book Keeper before sending again") == 3, "[9] the list on the Receipts screen says so too")
    await shot(pg, "9-books-history")
    check(all("bookingkeepingaruba" in u for _, u in calls), "[9] only the (faked) Book Keeper was called")
    check(not errs, "no script errors on Receipts" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 10 menu editor
async def test_menu_editor(browser):
    errs = []
    puts = []
    mode = {"fail": False}

    def gh_file(path):
        raw = open(os.path.join(ROOT, path), "rb").read()
        return {"sha": "sha-" + path, "content": base64.b64encode(raw).decode()}

    async def fake(route):
        req = route.request
        if "api.github.com" not in req.url:
            return False
        if mode["fail"]:
            await route.fulfill(status=500, content_type="application/json", body='{"message":"Server Error: something exploded in the backend"}')
            return True
        m = re.search(r"/contents/([^?]+)", req.url)
        if req.method == "PUT" and m:
            puts.append((m.group(1), json.loads(req.post_data)))
            await route.fulfill(status=200, content_type="application/json", body='{"content":{"sha":"new"}}')
        elif m:
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(gh_file(m.group(1))))
        else:
            await route.fulfill(status=200, content_type="application/json", body="{}")
        return True
    ctx, calls = await new_ctx(browser, fake)
    pg = await new_page(ctx, errs)
    await open_app(pg, "#/menu")
    await pg.wait_for_selector("#me-token")
    await pg.fill("#me-token", "ghp_" + "A1b2" * 9)
    await pg.click("[data-mact=savetoken]")
    await pg.wait_for_timeout(300)
    sheet = (await text(pg, "#sheet")).lower()
    stored = await pg.evaluate("localStorage.getItem('kitchen.github.v1')")
    check("old-style github key" in sheet and "github_pat_" in sheet and not stored and not calls,
          "[10] a classic ghp_ key is refused with a plain reason, and nothing is saved or sent")
    await shot(pg, "10-classic-key")
    await pg.evaluate("localStorage.setItem('kitchen.github.v1', JSON.stringify({token: 'github_pat_' + 'x'.repeat(82)}))")
    await pg.evaluate("location.hash = '#/menu/smash-shack'")
    await pg.wait_for_selector(".me-row")
    rows = await pg.evaluate("Array.from(document.querySelectorAll('.me-row')).map(r => [r.querySelector('.me-t b').textContent, !!r.querySelector('img'), !!r.querySelector('.me-noimg')])")
    hid = {i["name"] for i in menus["smash-shack"]["items"] if i.get("hidePhoto")}
    check(all((not im and no) if nm in hid else im for nm, im, no in rows), f"[3] the Menu tile shows no picture for hidden ones ({sorted(hid)})")
    check(await pg.evaluate("!document.querySelector('[onerror]')"), "[10] no inline onerror handlers in the menu list")
    cur = next(b["status"] for b in site["brands"] if b["id"] == "smash-shack")
    other = "soon" if cur != "soon" else "open"
    await pg.click(f".me-segb[data-v={other}]")
    await pg.wait_for_timeout(300)
    sheet = await text(pg, "#sheet")
    check("?" in sheet and not puts, f"[10] tapping a status asks first, nothing saved yet: {sheet.splitlines()[:1]}")
    await shot(pg, "10-status-confirm")
    await pg.click("[data-mact=statusyes]")
    await pg.wait_for_function("/Saved/.test(document.getElementById('toast').textContent)", timeout=10000)
    saved = json.loads(base64.b64decode(puts[-1][1]["content"]).decode()) if puts else {}
    check(puts and puts[-1][0] == "shared/site.json" and next(b for b in saved["brands"] if b["id"] == "smash-shack")["status"] == other,
          "[10] after 'Yes' the status is saved to site.json")
    mode["fail"] = True
    await pg.evaluate("location.hash = '#/menu/taco-brava'")
    await pg.wait_for_function("/GitHub/.test(document.querySelector('#main').innerText)", timeout=10000)
    msg = await text(pg, "#main")
    check("GitHub isn’t working right now" in msg and "exploded" not in msg, f"[10] GitHub's own error sentence is replaced by plain words: {msg.splitlines()[:1]}")
    mode["fail"] = False
    await pg.evaluate("location.hash = '#/menu/smash-shack/sc'")
    await pg.wait_for_selector("#me-name")
    noimg = await pg.evaluate("[!!document.querySelector('#me-noimg:not([hidden])'), document.getElementById('me-prev').hidden]")
    check(noimg == [True, True], "[3] the dish editor doesn't show the hidden picture either")
    check(all("api.github.com" in u for _, u in calls), "[10] only the (faked) GitHub was called")
    check(not errs, "no script errors in the menu editor" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 12 a Menu-tile save reaches the order database
async def test_menu_sync(browser):
    errs, puts, synced = [], [], []
    session = "test-kitchen-session-" + "0" * 12

    async def fake(route):
        req = route.request
        if "api.github.com" in req.url:
            m = re.search(r"/contents/([^?]+)", req.url)
            if req.method == "PUT" and m:
                puts.append((m.group(1), json.loads(req.post_data)))
                await route.fulfill(status=200, content_type="application/json", body='{"content":{"sha":"new"}}')
            elif m:
                raw = open(os.path.join(ROOT, m.group(1)), "rb").read()
                await route.fulfill(status=200, content_type="application/json",
                                    body=json.dumps({"sha": "sha-" + m.group(1), "content": base64.b64encode(raw).decode()}))
            else:
                await route.fulfill(status=200, content_type="application/json", body="{}")
            return True
        m = re.search(r"\.supabase\.co/rest/v1/rpc/([a-z_]+)$", req.url)
        if not m:
            return False
        args = json.loads(req.post_data or "{}")
        if m.group(1) == "pidi_kitchen_sync_menu":
            synced.append(args)
            body = {"ok": True, "skipped": False, "items": len(args.get("items") or [])}
        elif m.group(1) == "pidi_kitchen_feed":
            body = {"orders": []}
        elif m.group(1) == "pidi_public_state":
            body = {"ok": True, "busy_min": 0, "eta_min": 35, "eta_max": 50}
        else:
            return False
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
        return True
    ctx, calls = await new_ctx(browser, fake)
    pg = await new_page(ctx, errs)
    await pg.goto(BASE + "robots.txt")
    await pg.evaluate("""s => { localStorage.setItem('pidi.kitchen.session', JSON.stringify({token: s, expires_at: '2099-01-01T00:00:00Z', topic: 't'}));
      localStorage.setItem('kitchen.github.v1', JSON.stringify({token: 'github_pat_' + 'x'.repeat(82)})); }""", session)
    await open_app(pg, "#/menu/taco-brava")
    await pg.wait_for_selector(".me-row [data-mact=soldout]")
    for _ in range(60):   # the website's copy of every menu goes first (signed in, nothing sent yet)
        if len(synced) >= len(brands):
            break
        await pg.wait_for_timeout(100)
    first = list(synced)
    check(sorted(a["restaurant"] for a in first) == sorted(brands) and all(a["from_save"] is False and a["session"] == session for a in first),
          f"[12] signed in, the phone sends each restaurant's menu from the website once: {[(a['restaurant'], a['from_save']) for a in first]}")
    dish = next(i for i in menus["taco-brava"]["items"] if not i.get("soldOut"))
    await pg.click(f".me-row [data-mact=soldout][data-id='{dish['id']}']")
    await pg.wait_for_function("/Saved/.test(document.getElementById('toast').textContent)", timeout=10000)
    for _ in range(30):
        if len(synced) > len(first):
            break
        await pg.wait_for_timeout(100)
    after = synced[len(first):]
    row = next((r for a in after for r in (a.get("items") or []) if r["id"] == dish["id"]), None)
    check(puts and puts[-1][0] == "taco-brava/menu.json" and len(after) == 1 and after[0]["restaurant"] == "taco-brava"
          and after[0]["from_save"] is True and row and row["soldOut"] is True,
          f"[12] marking {dish['name']} sold out sends the saved menu to the order database at once: {[(a['restaurant'], a['from_save']) for a in after]}")
    toast = await text(pg, "#toast")
    check("Saved" in toast and "few minutes" not in toast, f"[12] the save says Saved (the database took it too): {toast!r}")
    check(all("api.github.com" in u or ".supabase.co/" in u for _, u in calls), "[12] only the (faked) GitHub and order database were called")
    check(not errs, "no script errors when a save goes to the order database" + (f": {errs}" if errs else ""))
    await ctx.close()


# ------------------------------------------------------------------ 8 the offline cache
async def test_sw(browser):
    errs = []
    ctx, _ = await new_ctx(browser, sw="allow")
    pg = await new_page(ctx, errs)
    await pg.goto(BASE + "robots.txt")
    await pg.evaluate("""Promise.all(['orderaruba-test', 'driver-test', 'kitchen-v1'].map(n => caches.open(n).then(c => c.put('/x-' + n, new Response('x')))))""")
    await pg.goto(APP)
    await pg.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller", timeout=20000)
    await pg.wait_for_function("window.__kitchen && __kitchen.menus() !== null", timeout=20000)
    await pg.wait_for_timeout(800)
    keys = await pg.evaluate("caches.keys()")
    sw_src = open(os.path.join(ROOT, "ops/kitchen/sw.js"), encoding="utf-8").read()
    current = re.search(r"var CACHE = '([^']+)'", sw_src).group(1)
    check(current in keys and "kitchen-v1" not in keys and "orderaruba-test" in keys and "driver-test" in keys,
          f"[8] only old kitchen- caches are deleted; the website's and the driver app's stay ({sorted(keys)})")
    has_site = await pg.evaluate(f"caches.open('{current}').then(c => c.match(new URL('../../shared/site.json', location.href).href)).then(r => !!r)")
    check(has_site, "[8] site.json is in the offline cache (for receipts)")
    # a weak signal: the server takes 10 s; the saved copy must answer after about 3 s
    DELAY["ops/kitchen/kitchen-data.json"] = 10
    dt, ok = await pg.evaluate("""async () => { const t = performance.now(); const r = await fetch('kitchen-data.json', {cache: 'no-cache'});
        const j = await r.json(); return [performance.now() - t, !!(j && j.dishes)]; }""")
    check(ok and 2500 <= dt <= 6000, f"[8] slow network: the saved copy answers after about 3 s ({dt / 1000:.1f} s), not after 10 s")
    DELAY["shared/site.json"] = 10
    t0 = time.time()
    await pg.goto(APP)
    await pg.wait_for_selector(".home-grid", timeout=15000)
    took = time.time() - t0
    check(took < 8, f"[8] the app opens on a slow network ({took:.1f} s)")
    check(HITS.get("ops/kitchen/kitchen-data.json", 0) >= 2, "[8] the network was still asked (the copy updates behind it)")
    DELAY.clear()
    await ctx.set_offline(True)
    await pg.goto(APP)
    await pg.wait_for_selector(".home-grid", timeout=15000)
    off = await pg.evaluate("[(__kitchen.menus() || []).length, __kitchen.img('smash-shack/sc')]")
    check(off[0] == len(brands) and off[1] is None, f"[8] offline: the app, the menus and the hidden-picture rule all work ({off[0]} menus)")
    await ctx.set_offline(False)
    check(not errs, "no script errors with the offline cache" + (f": {errs}" if errs else ""))
    await ctx.close()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for t in (test_tickets, test_orders, test_matching, test_live, test_books, test_menu_editor, test_menu_sync, test_sw):
            try:
                await t(browser)
            except Exception as e:   # one broken group must not hide the others
                check(False, f"{t.__name__} crashed: {type(e).__name__}: {str(e)[:300]}")
        await browser.close()


asyncio.run(main())
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
