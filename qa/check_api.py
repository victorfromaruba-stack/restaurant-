"""The engine's API for the app's own pages: python3 qa/check_api.py (0 problems). It serves the repo itself
(qa/local_server.py); QA_BASE=<url> checks another server.

The checkout and the order status pages (checkout/, order/) are built on window.OrderApp from shared/order-app.js
(the API is written out at the top of that file). This boots those pages in app mode and checks that every member is
there and does what it says: one ƒ5 delivery for a cart from two restaurants, no minimum order, cart lines with their
options after " · ", the delivery times on the Aruba clock while the phone is set to another time zone, the delivery
time read from site.json "eta", the customer's details and the remembered orders, the move from the old storage keys
(orderaruba.*) to pidi.*, the four languages, and that both pages wear the lively look (night blue, Archivo,
shared/order.css), never the darker drafts' fonts or stylesheet.
Nothing here places an order: every /rest/v1/ request is answered by a fake, and none is expected."""
import asyncio, datetime, json, os, re, sys
from playwright.async_api import async_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start
BASE = start()
fails = []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)

site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
menus = {b["id"]: json.load(open(os.path.join(ROOT, b["id"], "menu.json"), encoding="utf-8")) for b in site["brands"]}
words = {c: json.load(open(os.path.join(ROOT, "shared/lang", c + ".json"), encoding="utf-8")) for c in ("pap", "nl", "es")}
open_mix = [b["id"] for b in site["brands"] if b.get("status", "open") == "open" and b.get("mix")]
NBSP = "\u00a0"
FEE = site["deliveryFee"]
ETA = [int(x) for x in re.findall(r"\d+", site["eta"])[:2]]
LEAD = max(15, ETA[0] - 25)   # minutes: the order database takes a pre-order at least this far ahead
def money(c): return f"ƒ{c / 100:.2f}"
def describe(item, chosen):
    """the option words order-app.js puts on a ticket line, in menu order"""
    out = []
    for g in item.get("options", []):
        v = chosen.get(g["id"])
        if g["type"] == "one":
            if v and v != g.get("default"):
                out += [f"{g['label']}: {c['label']}" for c in g["choices"] if c["id"] == v]
        elif v:
            labels = [c["label"] for c in g["choices"] if c["id"] in v]
            out += labels if g["id"] == "leave" else [f"{g['label']}: {', '.join(labels)}"]
    return out

MEMBERS = {   # name: what typeof gives
    "ready": "object", "site": "function", "ordering": "function", "eta": "function", "menu": "function", "loadMenu": "function",
    "tr": "function", "money": "function", "lang": "function", "clock": "function", "arubaNow": "function", "shopStatus": "function",
    "slots": "function", "canOrderNow": "function", "lines": "function", "food": "function", "fee": "function", "total": "function",
    "minFood": "function", "shortBy": "function", "setLineQty": "function", "clear": "function", "details": "function",
    "saveDetails": "function", "rememberOrder": "function", "orders": "function", "onChange": "function",
    "waNumber": "function", "waLink": "function", "esc": "function", "keep": "function", "listAnd": "function", "toast": "function",
    # kept from before (restaurant pages, QA)
    "buildMessage": "function", "checkoutLink": "function", "addItem": "function", "count": "function", "subtotal": "function",
    "state": "function", "_set": "function",
}
LINE_KEYS = {"k", "b", "brand", "id", "name", "title", "opts", "q", "p", "img", "drink", "soldOut", "o"}
# Saturday 10 Oct 2026. Aruba is UTC-4; the phone below is set to Amsterdam (UTC+2) to prove the phone's zone is ignored
T_AFTERNOON = "2026-10-10T19:00:00Z"   # 3 PM in Aruba (9 PM on the phone): closed, pre-order for tonight
T_LATE = "2026-10-11T03:30:00Z"        # 11:30 PM in Aruba: open
T_LAST = "2026-10-11T05:20:00Z"        # 1:20 AM in Aruba: still before last orders
T_AFTER = "2026-10-11T05:40:00Z"       # 1:40 AM in Aruba: after last orders, the coming night's times
def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:00.000Z")
def utc(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))

db_calls = []
async def fake_db(route):
    db_calls.append(route.request.url.split("/rest/v1/")[-1])
    await route.fulfill(status=200, content_type="application/json", body="null")

async def new_page(br, tz="Europe/Amsterdam", width=390, height=664):
    ctx = await br.new_context(viewport={"width": width, "height": height}, is_mobile=True, has_touch=True, service_workers="block",
                               timezone_id=tz, locale="en-US")
    await ctx.route("**/rest/v1/**", fake_db)
    await ctx.route("https://wa.me/**", lambda r: r.abort())
    await ctx.add_init_script("document.addEventListener('oa:ready', () => { window.__oaReady = (window.__oaReady || 0) + 1; });")
    pg = await ctx.new_page()
    pg._errs = []
    pg.on("pageerror", lambda e: pg._errs.append(f"page error: {e}"))
    pg.on("console", lambda m: pg._errs.append(f"console: {m.text}") if m.type == "error" else None)
    return ctx, pg

async def ready(pg, url):
    await pg.goto(BASE + url, wait_until="networkidle")
    return await pg.evaluate("OrderApp.ready.then(() => window.__oaReady || 0)")

async def api_checks(br):
    ctx, pg = await new_page(br)
    await pg.clock.set_fixed_time(T_AFTERNOON)
    await pg.goto(BASE + "404.html")
    await pg.evaluate("localStorage.clear()")
    fired = await ready(pg, "checkout/index.html")
    check(fired == 1, f"checkout/: OrderApp.ready resolves and \"oa:ready\" fires once ({fired})")
    types = dict(await pg.evaluate("names => names.map(n => [n, typeof OrderApp[n]])", list(MEMBERS)))
    bad = {n: t for n, t in types.items() if t != MEMBERS[n]}
    check(not bad and await pg.evaluate("OrderApp.ready instanceof Promise"), f"OrderApp has every member of the API ({len(MEMBERS)})" + (f": {bad}" if bad else ""))
    drawn = await pg.evaluate("""() => ({extra: Array.from(document.querySelectorAll('#oa-bar, .bar, .oa-sheet, .iab')).length,
        langs: Array.from(document.querySelectorAll('[data-oa-langs] button')).map(b => b.textContent + (b.getAttribute('aria-pressed') === 'true' ? '*' : '')),
        app: (document.querySelector('[data-oa-app]') || {}).textContent, lang: document.documentElement.lang})""")
    check(drawn["extra"] == 0 and drawn["langs"] == ["EN*", "PAP", "NL", "ES"] and drawn["app"] == site["name"] and drawn["lang"] == "en",
          f"app mode draws no order bar or sheet, fills the language switch and the app's name ({drawn})")
    r = await pg.evaluate("[OrderApp.lang(), OrderApp.site().name, OrderApp.minFood(), OrderApp.shortBy(), OrderApp.tr('{name} added', {name: 'Fries'}), OrderApp.ordering()]")
    want_mode = "app" if site.get("ordering") == "app" else "whatsapp"
    check(r == ["en", site["name"], 0, 0, "Fries added", want_mode], f"lang(), site(), no minimum (minFood 0, shortBy 0), tr() with a value, ordering() ({r})")
    e = await pg.evaluate("[OrderApp.eta(), OrderApp.site().etaMin, OrderApp.site().etaMax]")
    check(e == [{"min": ETA[0], "max": ETA[1], "text": site["eta"]}, ETA[0], ETA[1]], f"eta() and site().etaMin/etaMax come from site.json \"eta\" ({e})")
    m = await pg.evaluate("[OrderApp.money(1295), OrderApp.money(1295, true), OrderApp.money(500)]")
    check(m[0] == "ƒ12.95" and m[2] == "ƒ5.00" and '<span aria-hidden="true">ƒ12.95</span>' in m[1] and 'class="sr"' in m[1] and "12.95 florins" in m[1],
          f"money(): ƒ12.95 on screen, \"12.95 florins\" for a screen reader ({m})")
    c = await pg.evaluate("[OrderApp.clock(1435), OrderApp.clock(1320), OrderApp.clock(1320, true), OrderApp.clock(0, true), OrderApp.clock(45)]")
    check(c == [f"11:55{NBSP}PM", f"10{NBSP}PM", f"10:00{NBSP}PM", f"12:00{NBSP}AM", f"12:45{NBSP}AM"], f"clock() in English, a no-break space before PM ({c})")
    w = await pg.evaluate("[OrderApp.waNumber(), OrderApp.waLink('Hi! Order 4')]")
    check(w[0] == f"+297{NBSP}747{NBSP}7794" and w[1] == "https://wa.me/" + site["whatsapp"] + "?text=Hi!%20Order%204", f"waNumber() and waLink() ({w})")

    # ---- time: the Aruba clock, whatever the phone's zone
    async def at(t):
        await pg.clock.set_fixed_time(t)
        return await pg.evaluate("({now: OrderApp.arubaNow(), open: OrderApp.shopStatus().open, can: OrderApp.canOrderNow(), slots: OrderApp.slots()})")
    r = await at(T_AFTERNOON)
    s = r["slots"]
    check(r["now"]["mins"] == 15 * 60 and r["now"]["day"] == 6 and r["now"]["date"] == "2026-10-10",
          f"arubaNow() is 3:00 PM Saturday in Aruba while the phone says 9 PM in Amsterdam ({r['now']})")
    check(not r["open"] and not r["can"], "3 PM: closed, no order for as soon as possible")
    check(len(s) == 16 and s[0] == {"m": 1320, "label": f"10:00{NBSP}PM", "iso": "2026-10-11T02:00:00.000Z", "tonight": True, "day": 6, "early": True}
          and s[-1]["iso"] == "2026-10-11T05:45:00.000Z" and s[-1]["label"] == f"1:45{NBSP}AM" and s[-1]["tonight"] and not s[-1]["early"]
          and [x["early"] for x in s].count(True) == 2
          and all(re.match(r"^\d\d:\d\d:00\.000Z$", x["iso"][11:]) and int(x["iso"][14:16]) % 15 == 0 for x in s),
          f"3 PM: tonight's 16 times, 10:00 PM to 1:45 AM Aruba, every 15 min, sent in UTC, the first half hour marked early ({s[0] if s else None} .. {s[-1] if s else None})")
    r = await at(T_LATE)
    s = r["slots"]
    first = utc(T_LATE) + datetime.timedelta(minutes=LEAD)
    first += datetime.timedelta(minutes=(-first.minute) % 15)
    check(r["open"] and r["can"] and r["now"]["mins"] == 23 * 60 + 30, "11:30 PM: open, an order for as soon as possible goes in")
    check(bool(s) and s[0]["iso"] == iso(first) and s[-1]["iso"] == "2026-10-11T05:45:00.000Z" and all(x["tonight"] for x in s),
          f"11:30 PM: the times left tonight start {LEAD} min or more from now ({[x['label'] for x in s]})")
    r = await at(T_LAST)
    check(r["can"] and [x["iso"] for x in r["slots"]] == ["2026-10-11T05:45:00.000Z"], f"1:20 AM: still open, one time left (1:45 AM) ({r['slots']})")
    r = await at(T_AFTER)
    s = r["slots"]
    check(not r["can"] and not r["open"], "1:40 AM: after last orders, nothing as soon as possible")
    check(bool(s) and s[0]["iso"] == "2026-10-12T02:00:00.000Z" and s[-1]["iso"] == "2026-10-12T05:30:00.000Z" and not s[0]["tonight"] and s[0]["day"] == 0,
          f"1:40 AM: the coming (Sunday) night's times, never more than 24 h ahead (10:00 PM to 1:30 AM) ({s[0]['label'] if s else None} .. {s[-1]['label'] if s else None})")
    await pg.clock.set_fixed_time(T_LATE)

    # ---- the cart: one fee, no minimum, the lines
    check(len(open_mix) >= 2, f"two restaurants that are open can share one order ({open_mix})")
    if len(open_mix) >= 2:
        A, B = open_mix[0], open_mix[1]
        a_item = next(i for i in menus[A]["items"] if i.get("options") and not i.get("soldOut") and i.get("kind") != "drink")
        g = a_item["options"][0]
        pick = next(c["id"] for c in g["choices"] if c["id"] != g.get("default")) if g["type"] == "one" else [g["choices"][0]["id"]]
        chosen = {g["id"]: pick}
        b_item = next(i for i in menus[B]["items"] if i.get("kind") not in ("drink",) and not i.get("soldOut"))
        await pg.evaluate("OrderApp.clear(); window.__changes = 0; OrderApp.onChange(() => window.__changes++)")
        await pg.evaluate("([a, b]) => Promise.all([OrderApp.loadMenu(a), OrderApp.loadMenu(b)])", [A, B])
        await pg.evaluate("([a, i, o]) => OrderApp.addItem(a, i, o, 2)", [A, a_item["id"], chosen])
        await pg.evaluate("([b, i]) => OrderApp.addItem(b, i, {}, 1)", [B, b_item["id"]])
        await pg.evaluate("a => OrderApp.addItem(a, 'ck', {}, 1)", A)
        ls = await pg.evaluate("OrderApp.lines()")
        la = next((l for l in ls if l["id"] == a_item["id"]), None)
        opts = describe(a_item, chosen)
        check(all(set(l) == LINE_KEYS for l in ls) and len(ls) == 3, f"lines() gives every field for every line ({sorted(set(ls[0]) if ls else [])})")
        check(la and la["opts"] == opts and la["title"] == a_item["name"] and la["name"] == " · ".join([a_item["name"]] + opts)
              and la["brand"] == menus[A]["name"] and la["b"] == A and la["q"] == 2 and la["p"] == a_item["price"] and not la["drink"],
              f"a line's ticket name is the dish then each option after \" · \" ({la and la['name']!r})")
        img_ok = la and (la["img"].endswith("thumbs/" + a_item["img"].split("/")[-1]) if not a_item.get("hidePhoto") else la["img"] == "")
        drink = next((l for l in ls if l["id"] == "ck"), {})
        check(img_ok and drink.get("drink") is True and drink.get("img") == "" and drink.get("name") == "Coca-Cola (can)",
              f"a line has its thumbnail (none for a can) and marks drinks ({la and la['img']})")
        food, fee, total = await pg.evaluate("[OrderApp.food(), OrderApp.fee(), OrderApp.total()]")
        want_food = a_item["price"] * 2 + b_item["price"] + 300
        check(food == want_food and fee == FEE and total == food + fee,
              f"{menus[A]['name']} + {menus[B]['name']}: food {food}, one {money(FEE)} delivery, total {total}")
        check(await pg.evaluate("window.__changes") >= 3, "onChange() hears every change to the cart")
        k = la["k"] if la else ""
        await pg.evaluate("k => OrderApp.setLineQty(k, 0)", k)
        left = await pg.evaluate("OrderApp.lines().map(l => l.id)")
        check(a_item["id"] not in left and len(left) == 2, f"setLineQty(k, 0) takes the line out ({left})")
        await pg.evaluate("OrderApp.clear()")
        await pg.evaluate("a => OrderApp.addItem(a, 'ck', {}, 1)", A)
        r = await pg.evaluate("[OrderApp.food(), OrderApp.shortBy(), OrderApp.fee(), OrderApp.total()]")
        check(r == [300, 0, FEE, 300 + FEE], f"one can on its own is an order: food ƒ3.00, nothing short, {money(FEE)} delivery ({r})")
        await pg.evaluate("OrderApp.clear()")
        r = await pg.evaluate("[OrderApp.lines().length, OrderApp.food(), OrderApp.fee(), OrderApp.total()]")
        check(r == [0, 0, 0, 0], f"clear() empties the cart; an empty cart has no fee ({r})")

        # ---- the customer's details
        d = await pg.evaluate("""() => { OrderApp.saveDetails({name: 'Maria', phone: '5931234', area: 'Noord', addr: 'Weg 12, blue gate', note: 'Gate 4',
            pay: 'cash', paysWith: 5000, usd: false, junk: 1}); return [OrderApp.details(), JSON.parse(localStorage.getItem('pidi.me.v1'))]; }""")
        want = {"name": "Maria", "phone": "5931234", "area": "Noord", "addr": "Weg 12, blue gate", "note": "Gate 4", "pay": "cash", "paysWith": 5000, "usd": False}
        check(d[0] == want and d[1] == want, f"saveDetails() / details() round trip in localStorage pidi.me.v1 ({d[0]})")
        d = await pg.evaluate("OrderApp.saveDetails({area: 'Mars', usd: true, pay: 'card'}); OrderApp.details()")
        check(d["area"] == "" and d["usd"] is True and d["name"] == "Maria" and d["pay"] == "", "an area that isn't in site.json areas, or a way to pay that isn't cash or transfer, isn't kept")

        # ---- remembering placed orders, and Order again
        await pg.evaluate("([a, i, o, b, j]) => { OrderApp.clear(); OrderApp.addItem(a, i, o, 1); OrderApp.addItem(b, j, {}, 2); }",
                          [A, a_item["id"], chosen, B, b_item["id"]])
        basket = await pg.evaluate("OrderApp.lines()")
        res = {"public_token": "tok-1", "pay": "cash", "total_cents": 4321, "created_at": "2026-10-11T03:30:00Z", "night_no": 14, "due_at": "2026-10-11T03:30:00Z",
               "restaurants": [{"slug": A, "name": menus[A]["name"]}, {"slug": B, "name": menus[B]["name"]}]}
        rec = await pg.evaluate("r => [OrderApp.rememberOrder(r), OrderApp.orders(), JSON.parse(localStorage.getItem('pidi.last.v1'))]", res)
        first = rec[1][0] if rec[1] else {}
        at = int(datetime.datetime(2026, 10, 11, 3, 30, tzinfo=datetime.timezone.utc).timestamp() * 1000)
        check(first == {"t": "tok-1", "at": at, "no": 14, "restaurants": [menus[A]["name"], menus[B]["name"]], "total_cents": 4321, "pay": "cash",
                        "due": "2026-10-11T03:30:00Z", "lines": basket},
              f"rememberOrder() keeps the token, time, number, restaurants, total, payment and the full basket ({ {k: first.get(k) for k in ('t', 'at', 'no', 'restaurants', 'total_cents', 'pay')} })")
        again = rec[2] or {}
        check([(l["b"], l["id"], l["q"], l["o"]) for l in again.get("lines", [])] == [(l["b"], l["id"], l["q"], l["o"]) for l in basket],
              "the remembered basket is the Order again basket (pidi.last.v1)")
        check(await pg.evaluate("OrderApp.lines().length") == len(basket), "rememberOrder() leaves the cart for the page to clear")
        for n in range(2, 8):
            await pg.evaluate("t => OrderApp.rememberOrder({public_token: t, pay: 'transfer', total_cents: 3000})", f"tok-{n}")
        toks = await pg.evaluate("OrderApp.orders().map(o => o.t)")
        check(toks == ["tok-7", "tok-6", "tok-5", "tok-4", "tok-3"], f"orders() keeps the newest 5, newest first ({toks})")
        await pg.evaluate("OrderApp.clear()")
        await ready(pg, "order/index.html")
        got = await pg.evaluate("([a, b]) => [OrderApp.orders().length, !!OrderApp.menu(a), !!OrderApp.menu(b), OrderApp.lines().length]", [A, B])
        check(got == [5, True, True, 0], f"order/: after a reload the orders are there and their restaurants' menus are loaded ({got})")

    # ---- the move from the old storage keys: nobody loses a cart
    await pg.evaluate("localStorage.clear()")
    if open_mix:
        A = open_mix[0]
        dish = next(i for i in menus[A]["items"] if i.get("kind") != "drink" and not i.get("soldOut"))
        old_cart = {"v": 2, "lines": [{"k": f"{A}|{dish['id']}|", "b": A, "id": dish["id"], "q": 2, "o": {}, "d": [], "n": dish["name"], "p": dish["price"]}],
                    "mode": "delivery", "area": "Noord", "addr": "Weg 1", "name": "Ana", "note": "", "pay": "", "no": "", "sentAt": 0, "updated": 0}
        await pg.evaluate("""c => { localStorage.setItem('orderaruba.cart.v2', JSON.stringify(c)); localStorage.setItem('orderaruba.lang.v1', 'es');
            localStorage.setItem('orderaruba.last.v1', JSON.stringify({at: Date.now(), lines: [{b: c.lines[0].b, id: c.lines[0].id, q: 1, o: {}}]})); }""", old_cart)
        await ready(pg, "checkout/index.html")
        r = await pg.evaluate("[Object.keys(localStorage).sort(), OrderApp.lines().map(l => [l.b, l.id, l.q]), OrderApp.lang(), OrderApp.details().name]")
        check(r[0] == ["pidi.cart.v1", "pidi.lang.v1", "pidi.last.v1"] and r[1] == [[A, dish["id"], 2]] and r[2] == "es" and r[3] == "Ana",
              f"an order, Order again and the language saved under the old names move to pidi.* once, and the old keys go ({r})")
        await pg.evaluate("localStorage.clear()")

    # ---- other languages, on both pages
    for code, url in (("nl", "checkout/index.html"), ("es", "order/index.html"), ("pap", "checkout/index.html")):
        await pg.evaluate("c => localStorage.setItem('pidi.lang.v1', c)", code)
        await ready(pg, url)
        r = await pg.evaluate("""() => [OrderApp.lang(), document.documentElement.lang, OrderApp.clock(1435),
            OrderApp.slots().map(s => s.label)[0] || '', OrderApp.tr('{name} added', {name: 'X'}), OrderApp.money(300, true),
            document.querySelector('[data-oa-langs] [aria-pressed="true"]').textContent]""")
        w = words[code]
        check(r[:3] == [code, code, "23:55"] and re.match(r"^\d\d:\d\d$", r[3]) and r[4] == w["{name} added"].replace("{name}", "X")
              and ("3.00 " + w["florins"]) in r[5] and r[6] == code.upper(),
              f"[{code}] {url}: lang(), <html lang>, 24-hour times, tr() and money() in that language ({r[:5]})")
    await pg.evaluate("localStorage.removeItem('pidi.lang.v1')")
    check(not pg._errs, "checkout/ and order/ run with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

async def look_checks(br):
    """the app's own pages wear the lively look: night blue, Archivo, shared/order.css (never the darker drafts)"""
    ctx, pg = await new_page(br, tz="America/Aruba")
    await pg.clock.set_fixed_time(T_LATE)
    for url in ("checkout/index.html", "order/index.html"):
        await ready(pg, url)
        await pg.evaluate("document.fonts.ready")
        f = await pg.evaluate("""() => ({bg: getComputedStyle(document.body).backgroundColor,
            theme: (document.querySelector('meta[name=theme-color]') || {}).content,
            sheets: Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.getAttribute('href').split('/').pop()),
            font: getComputedStyle(document.querySelector('.top')).fontFamily.replace(/"/g, ''),
            faces: Array.from(document.fonts).filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g, '')),
            robots: (document.querySelector('meta[name=robots]') || {}).content, title: document.title})""")
        ok = f["bg"] == "rgb(11, 29, 58)" and f["theme"] == "#0B1D3A" and f["sheets"][:1] == ["order.css"] and "pidi.css" not in f["sheets"] \
            and f["font"].startswith("Archivo") and set(f["faces"]) <= {"Archivo"} and f["robots"] == "noindex" and f["title"].startswith(site["name"] + " · ")
        check(ok, f"{url}: the lively look (night blue, Archivo, order.css), noindex, titled \"{site['name']} · …\"" + ("" if ok else f": {f}"))
    sitemap = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
    check("/checkout/" not in sitemap and "/order/" not in sitemap, "checkout/ and order/ are not in the sitemap")
    check(not pg._errs, "the look checks ran with no page errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

# ---------------------------------------------------------------- checkout/ and order/, against a fake order database
# Every /rest/v1/rpc/ call is answered here, the way driver/v2/supabase/PIDI_SETUP.sql answers it: the real database is
# never reached (and any other request to it is stopped and counted). QA_SHOTS=<folder> saves phone screenshots of every
# checkout step and every order state at 390 and 320 px wide.
SHOTS = os.environ.get("QA_SHOTS")
APP_SITE = dict(site, ordering="app")
NAMES = {b: m["name"] for b, m in menus.items()}
leaks = []

def iso_now(t): return t if t.endswith("Z") else t + "Z"

class FakeDB:
    """the order database's answers, from what each test sets"""
    def __init__(self, now):
        self.now, self.calls, self.place, self.orders, self.by_client, self.n = now, [], ["ok"], {}, {}, 0
    def order_from(self, p, n):
        food = sum(i["qty"] * i.get("price_cents", 0) for i in p["items"])
        usd, pays = bool(p.get("pays_in_usd")), p.get("pays_with_cents")
        rest = []
        for i in p["items"]:
            if i["restaurant"] not in [r["slug"] for r in rest]:
                rest.append({"slug": i["restaurant"], "name": NAMES.get(i["restaurant"], i["restaurant"]), "food_cents": 0, "ready": False})
        return {"order_id": f"id-{n}", "public_token": f"tok-{n}", "food_cents": food, "fee_cents": 500, "total_cents": food + 500,
                "change_due_cents": (pays - food - 500) if p["pay"] == "cash" and not usd else None, "pay": p["pay"],
                "pays_with_cents": pays if p["pay"] == "cash" and not usd else None, "pays_in_usd": usd,
                "transfer_status": "awaiting" if p["pay"] == "transfer" else None, "transfer_paid_at": None,
                "due_at": p.get("due_at") or self.now, "created_at": self.now, "first_name": p["name"].split(" ")[0], "area": p["area"],
                "night_no": 10 + n, "eta_min": ETA[0], "eta_max": ETA[1], "test": False, "restaurant": ", ".join(r["name"] for r in rest),
                "restaurants": rest, "items": [{"restaurant": i["restaurant"], "name": i["name"], "qty": i["qty"], "price_cents": i.get("price_cents", 0)} for i in p["items"]],
                "events": [{"status": "new", "at": self.now}], "status": "new", "label": "Received", "topic": f"pidi:order:tok-{n}"}
    async def handle(self, route):
        req = route.request
        name = req.url.split("/rpc/")[-1].split("?")[0] if "/rpc/" in req.url else req.url
        body = json.loads(req.post_data or "{}") if req.method == "POST" else {}
        self.calls.append((name, body))
        async def answer(v, status=200):
            await route.fulfill(status=status, content_type="application/json", body=json.dumps(v))
        if name == "pidi_place_order":
            what = self.place.pop(0) if len(self.place) > 1 else self.place[0]
            if what == "abort":
                return await route.abort("failed")
            p = body.get("payload") or {}
            if what not in ("ok", "ok-lost"):
                return await answer({"code": "P0001", "details": None, "hint": None, "message": what}, 400)
            ct = p.get("client_token")
            if ct not in self.by_client:
                self.n += 1
                o = self.order_from(p, self.n)
                self.orders[o["public_token"]], self.by_client[ct] = o, o["public_token"]
            if what == "ok-lost":   # it went in, but the answer never reached the phone
                return await route.abort("failed")
            return await answer(self.orders[self.by_client[ct]])
        if name == "pidi_find_order":
            return await answer(self.orders.get(self.by_client.get(body.get("client_token"))))
        if name == "pidi_order_status":
            o = self.orders.get(body.get("token"))
            return await answer(o) if o else await answer({"code": "P0001", "details": None, "hint": None, "message": "NOT_FOUND"}, 400)
        await answer({"message": "no such function"}, 404)
    def placed(self): return [b["payload"] for n, b in self.calls if n == "pidi_place_order"]

async def app_page(br, fake, t, width=390, site_json=APP_SITE, lang=None, fixed=True):
    ctx = await br.new_context(viewport={"width": width, "height": 780}, is_mobile=True, has_touch=True, service_workers="block", device_scale_factor=2 if SHOTS else 1,
                               timezone_id="Europe/Amsterdam", locale="en-US", geolocation={"latitude": 12.5711, "longitude": -70.0412}, permissions=["geolocation"])
    await ctx.route("**/rest/v1/**", fake.handle)
    async def stop(route):
        leaks.append(route.request.url); await route.abort()
    await ctx.route(re.compile(r"^https://[^/]*supabase\.co/(?!rest/v1/)"), stop)
    await ctx.route("**/shared/site.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(site_json)))
    await ctx.route("https://wa.me/**", lambda r: r.abort())
    pg = await ctx.new_page()
    pg._errs = []
    pg.on("pageerror", lambda e: pg._errs.append(f"page error: {e}"))
    pg.on("console", lambda m: pg._errs.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
    if fixed:
        await pg.clock.set_fixed_time(t)
    else:
        await pg.clock.install(time=t)
    await pg.goto(BASE + "404.html")
    await pg.evaluate("localStorage.clear(); sessionStorage.clear()")
    if lang:
        await pg.evaluate("l => localStorage.setItem('pidi.lang.v1', l)", lang)
    return ctx, pg

shot_n = {}
async def shot(pg, name, end=False):
    """a phone screenshot: the first screen, and with end=True also the bottom of the page"""
    if not SHOTS:
        return
    os.makedirs(SHOTS, exist_ok=True)
    w = pg.viewport_size["width"]
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(120)
    await pg.screenshot(path=os.path.join(SHOTS, f"{name}-{w}.png"))
    if end:
        await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=os.path.join(SHOTS, f"{name}-{w}-end.png"))
        await pg.evaluate("window.scrollTo(0, 0)")

async def fits(pg):
    return await pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

def tap(value, name):
    return f"label:has(> input[name={name}][value=\"{value}\"])"

async def fill_cart(pg, a, ia, b=None, ib=None):
    await pg.goto(BASE + a + "/index.html", wait_until="networkidle")
    await pg.evaluate("""([a, ia, b, ib]) => (b ? OrderApp.loadMenu(b) : Promise.resolve()).then(() => {
        OrderApp.clear(); OrderApp.addItem(a, ia, {}, 1); if (b) OrderApp.addItem(b, ib, {}, 2); OrderApp.addItem(a, 'ck', {}, 1); })""", [a, ia, b, ib])
    return await pg.evaluate("[OrderApp.lines(), OrderApp.total()]")

async def step_of(pg):
    return await pg.evaluate("[location.hash.slice(1), (document.querySelector('.step__t') || {}).textContent || '']")

def dish(b, skip=()):
    return next(i for i in menus[b]["items"] if i.get("kind") not in ("drink", "side") and not i.get("soldOut") and i["id"] not in skip)

async def checkout_flow(br, width):
    """a first-time customer at 11:30 PM: every step, then Place order"""
    fake = FakeDB(iso_now(T_LATE))
    ctx, pg = await app_page(br, fake, T_LATE, width)
    A, B = open_mix[0], open_mix[1]
    ia, ib = dish(A)["id"], dish(B)["id"]
    lines, total = await fill_cart(pg, A, ia, B, ib)
    await pg.goto(BASE + f"checkout/?from={A}", wait_until="networkidle"); await pg.wait_for_timeout(200)
    tag = f"[{width}px]"
    st = await step_of(pg)
    asap = await pg.evaluate("(document.querySelector('input[name=ck-when]:checked') || {}).value")
    check(st == ["where", "Where do we bring it?"] and asap == "asap" and await fits(pg),
          f"{tag} checkout opens on step 1, \"Where do we bring it?\", with as soon as possible picked while open ({st}, {asap})")
    await shot(pg, "checkout-1-where")
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    bad = await pg.evaluate("[Array.from(document.querySelectorAll('.is-bad')).map(f => f.getAttribute('data-err')), document.activeElement && document.activeElement.name, location.hash]")
    check(bad[0] == ["area", "addr"] and bad[1] == "ck-area" and bad[2] == "#where", f"{tag} Continue with nothing filled in says what's missing and stays ({bad})")
    await shot(pg, "checkout-1-where-missing")
    await pg.click(tap("Noord", "ck-area"))
    await pg.fill("#ck-addr", "Weg Fontein 12, yellow house, blue gate")
    await pg.click("[data-loc]"); await pg.wait_for_timeout(300)
    loc = await pg.evaluate("!!document.querySelector('.loc--on')")
    check(loc and not await pg.evaluate("document.querySelector('.is-bad')"), f"{tag} the area, the address and the phone's location go in ({loc})")
    await shot(pg, "checkout-1-where-filled", end=True)
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    st = await step_of(pg)
    check(st == ["you", "Who’s it for?"] and await fits(pg), f"{tag} step 2: \"Who’s it for?\" ({st})")
    await pg.fill("#ck-name", "Maria Croes")
    await pg.fill("#ck-phone", "12")
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    check(await pg.evaluate("[...document.querySelectorAll('.is-bad')].map(f => f.getAttribute('data-err'))") == ["phone"], f"{tag} a phone number too short to call is caught")
    await pg.fill("#ck-phone", "+297 593 1234")
    await shot(pg, "checkout-2-you")
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    st = await step_of(pg)
    check(st == ["pay", "How will you pay?"], f"{tag} step 3: \"How will you pay?\" ({st})")
    await shot(pg, "checkout-3-pay")
    await pg.click(tap("cash", "ck-pay")); await pg.wait_for_timeout(150)
    chips = await pg.evaluate("Array.from(document.querySelectorAll('[data-cash]')).map(b => +b.getAttribute('data-cash'))")
    check(chips[0] == total and all(c > total for c in chips[1:]) and len(chips) >= 3, f"{tag} cash: \"Exact amount\" and the notes above the total ({chips}, total {total})")
    await pg.fill("#ck-cash", str((total - 100) / 100))
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    check(await pg.evaluate("[...document.querySelectorAll('.is-bad')].map(f => f.getAttribute('data-err'))") == ["cash"], f"{tag} paying with less than the total is caught")
    await pg.click(f"[data-cash='{chips[1]}']"); await pg.wait_for_timeout(150)
    change = await pg.evaluate("document.querySelector('[data-change]').textContent")
    check(change == f"The driver brings {money(chips[1] - total)} change.", f"{tag} the change the driver brings ({change})")
    await shot(pg, "checkout-3-pay-cash", end=True)
    await pg.click(tap("usd", "ck-cur")); await pg.wait_for_timeout(150)
    await shot(pg, "checkout-3-pay-usd")
    await pg.click(tap("transfer", "ck-pay")); await pg.wait_for_timeout(150)
    await shot(pg, "checkout-3-pay-transfer")
    await pg.click(tap("cash", "ck-pay")); await pg.wait_for_timeout(150)
    await pg.click(tap("awg", "ck-cur")); await pg.wait_for_timeout(150)
    await pg.click(f"[data-cash='{chips[1]}']"); await pg.wait_for_timeout(150)
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    st = await step_of(pg)
    page = await pg.evaluate("document.getElementById('oa-main').innerText")
    groups = await pg.evaluate("Array.from(document.querySelectorAll('.lines__brand')).map(h => h.textContent)")
    pics = await pg.evaluate("Array.from(document.querySelectorAll('.line__pic')).length")
    btn = await pg.evaluate("document.querySelector('[data-place]').innerText.replace(/\\s+/g, ' ')")
    check(st == ["check", "Check your order"] and groups[:2] == [NAMES[A], NAMES[B]] and pics == len(lines) and page.count("ƒ5.00") == 1
          and "You pay ƒ5 delivery once." in page and money(total) in btn and "Place order" in btn and await fits(pg),
          f"{tag} step 4: the dishes by restaurant with a picture each, ƒ5 delivery once, the total on Place order ({groups}, {btn})")
    await shot(pg, "checkout-4-check", end=True)
    await pg.fill("#ck-note", "Gate code 4411")
    await pg.click("[data-place]")
    await pg.wait_for_function("location.pathname.endsWith('/order/')"); await pg.wait_for_timeout(400)
    p = fake.placed()[-1] if fake.placed() else {}
    want_items = [{"restaurant": l["b"], "id": l["id"], "name": l["name"], "qty": l["q"], "price_cents": l["p"]} for l in lines]
    check(p.get("items") == want_items and p.get("name") == "Maria Croes" and p.get("phone") == "+297 593 1234" and p.get("area") == "Noord"
          and p.get("address") == "Weg Fontein 12, yellow house, blue gate" and p.get("note") == "Gate code 4411" and p.get("pay") == "cash"
          and p.get("pays_with_cents") == chips[1] and "pays_in_usd" not in p and "due_at" not in p and p.get("lat") == "12.571100"
          and p.get("lng") == "-70.041200" and len(p.get("client_token") or "") >= 16 and "pickup" not in p,
          f"{tag} Place order sends pidi_place_order every line by id, the details, cash with the note, the map pin and a client_token ({ {k: v for k, v in p.items() if k != 'items'} })")
    after = await pg.evaluate("""() => [location.hash, JSON.parse(localStorage.getItem('pidi.cart.v1')).lines.length, (JSON.parse(localStorage.getItem('pidi.orders.v1')) || [{}])[0].t,
        JSON.parse(localStorage.getItem('pidi.me.v1')).phone, (document.querySelector('.st__t') || {}).textContent]""")
    check(after == ["#t=tok-1", 0, "tok-1", "+297 593 1234", "Received"], f"{tag} then: the order is remembered, the cart emptied, the phone number kept, and its status page shows Received ({after})")
    await shot(pg, "status-0-just-placed", end=True)
    check(not pg._errs, f"{tag} the checkout ran with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()
    return fake

async def checkout_cases(br):
    """a returning customer, every error code, a retry with the same token, a pre-order, WhatsApp mode, an empty cart"""
    A, B = open_mix[0], open_mix[1]
    a1, b1 = dish(A), dish(B)
    fake = FakeDB(iso_now(T_LATE))
    ctx, pg = await app_page(br, fake, T_LATE)
    await fill_cart(pg, A, a1["id"], B, b1["id"])
    await pg.evaluate("OrderApp.saveDetails({name: 'Ben', phone: '5931234', area: 'Oranjestad', addr: 'Caya G.F. Betico Croes 10', pay: 'transfer'})")
    await pg.goto(BASE + f"checkout/?from={A}", wait_until="networkidle"); await pg.wait_for_timeout(200)
    st = await step_of(pg)
    check(st[0] == "check", f"a returning customer (details on this phone) lands on Check your order, as soon as possible while open ({st})")
    # every answer from the database becomes a sentence, and the customer lands where it can be fixed
    lines = await pg.evaluate("OrderApp.lines()")
    cases = [("REST_CLOSED:" + B, f"{NAMES[B]} isn’t taking orders right now. Take its dishes out and try again.", "check", "edit"),
             ("SOLD_OUT:0", f"Sorry, {lines[0]['title']} just sold out tonight. Remove it to send the order.", "check", "edit"),
             ("BAD_ITEM:1", f"{lines[1]['title']} changed on the menu. Take it out and add it again.", "check", "edit"),
             ("BAD_PHONE", "That phone number doesn’t look right. Check it and try again.", "you", ""),
             ("CASH_SHORT", "The cash you pay with doesn’t cover the whole total. Pick a bigger amount.", "pay", ""),
             ("BAD_TIME", "That delivery time can’t be booked any more. Pick another time.", "where", ""),
             ("CLOSED", "We just stopped taking orders for right now. Pick a time for later.", "where", ""),
             ("RATE_LIMIT", "This phone number already has orders waiting. To add something, message us on WhatsApp.", "check", "wa"),
             ("MIN_FOOD", "Add a little more food to this order and try again.", "check", "edit"),
             ("FEE_NOT_SET", "Something went wrong on our side. Try again in a minute, or send this order on WhatsApp.", "check", "wa")]
    for n, (code, text, where, extra) in enumerate(cases):
        fake.place = [code]
        await pg.goto(BASE + f"checkout/?from={A}&n={n}#check", wait_until="networkidle"); await pg.wait_for_timeout(150)
        await pg.click("[data-place]"); await pg.wait_for_timeout(400)
        got = await pg.evaluate("""() => { const e = document.querySelector('.ck-err'); return [e ? e.querySelector('p').textContent : '', location.hash.slice(1),
            e ? (e.querySelector('[data-wa]') || {}).href || '' : '', e ? !!Array.from(e.querySelectorAll('a')).find(a => /#o$/.test(a.href)) : false]; }""")
        ok = got[0].replace("\xa0", " ") == text and got[1] == where and (extra != "wa" or got[2].startswith("https://wa.me/")) and (extra != "edit" or got[3])
        check(ok, f"{code}: \"{text}\" on the {where} step" + (" with a WhatsApp link" if extra == "wa" else " with a way back to the order" if extra == "edit" else "") + ("" if ok else f" ({got})"))
        if code == "FEE_NOT_SET":
            from urllib.parse import unquote
            msg = unquote(got[2].split("text=", 1)[-1])
            check(msg.startswith("*Order* #") and f"*{NAMES[A]}*" in msg and "Pay: Bank transfer" in msg and "Name: Ben" in msg and "Phone 5931234." in msg,
                  f"when the database can't take it, the same order goes out on WhatsApp, written out like before ({msg.splitlines()[0] if msg else ''})")
        if n == 0:
            await shot(pg, "checkout-error-restaurant-closed", end=True)
        if code == "FEE_NOT_SET":
            await shot(pg, "checkout-error-whatsapp-fallback", end=True)
    check(len(fake.orders) == 0, "none of those went in")
    # the same sentence in the visitor's language
    await pg.evaluate("localStorage.setItem('pidi.lang.v1', 'nl')")
    fake.place = ["REST_CLOSED:" + B]
    await pg.goto(BASE + f"checkout/?from={A}&n=nl#check", wait_until="networkidle"); await pg.wait_for_timeout(150)
    await pg.click("[data-place]"); await pg.wait_for_timeout(400)
    nl = await pg.evaluate("(document.querySelector('.ck-err p') || {}).textContent")
    check(nl == words["nl"]["{restaurant} isn’t taking orders right now. Take its dishes out and try again."].replace("{restaurant}", NAMES[B]), f"[nl] the same answer in Dutch ({nl})")
    await shot(pg, "checkout-error-nl", end=True)
    await pg.evaluate("localStorage.removeItem('pidi.lang.v1')")
    # no connection, then Place order again: the same client_token, one order
    fake.place = ["abort", "ok"]
    await pg.goto(BASE + f"checkout/?from={A}&n=retry#check", wait_until="networkidle"); await pg.wait_for_timeout(150)
    before = len(fake.placed())
    await pg.click("[data-place]"); await pg.wait_for_timeout(400)
    off = await pg.evaluate("[(document.querySelector('.ck-err p') || {}).textContent, location.hash]")
    check(off == ["No connection. Check your internet and tap Place order again: it won’t go in twice.", "#check"], f"no connection: it says so and stays ({off})")
    await shot(pg, "checkout-error-offline", end=True)
    await pg.click("[data-place]"); await pg.wait_for_function("location.pathname.endsWith('/order/')"); await pg.wait_for_timeout(300)
    toks = [p["client_token"] for p in fake.placed()[before:]]
    check(len(toks) == 2 and toks[0] == toks[1] and len(fake.orders) == 1, f"tapped again, it goes with the same client_token, and there is one order ({toks})")
    # the answer got lost after the order went in, and then the cart changed: the earlier order is found, not doubled
    fake.place = ["ok-lost"]
    await fill_cart(pg, A, a1["id"])
    await pg.goto(BASE + f"checkout/?from={A}&n=lost#check", wait_until="networkidle"); await pg.wait_for_timeout(150)
    await pg.click("[data-place]"); await pg.wait_for_timeout(400)
    first_tok = fake.placed()[-1]["client_token"]
    await pg.evaluate("a => OrderApp.addItem(a, 'cz', {}, 1)", A); await pg.wait_for_timeout(150)
    fake.place = ["ok"]
    await pg.click("[data-place]"); await pg.wait_for_function("location.pathname.endsWith('/order/')"); await pg.wait_for_timeout(500)
    finds = [b for n, b in fake.calls if n == "pidi_find_order"]
    note = await pg.evaluate("Array.from(document.querySelectorAll('.note')).map(n => n.textContent).join(' ')")
    check(finds and finds[-1] == {"client_token": first_tok} and len(fake.orders) == 2 and "went in the first time" in note and "earlier=1" in pg.url,
          f"after an answer that never came and a changed cart, it asks pidi_find_order first, finds the order and shows it, no second one ({len(fake.orders)} orders)")
    # a changed cart after a failure where nothing went in: a new token
    fake.place = ["abort"]
    await fill_cart(pg, A, a1["id"])
    await pg.goto(BASE + f"checkout/?from={A}&n=new#check", wait_until="networkidle"); await pg.wait_for_timeout(150)
    await pg.click("[data-place]"); await pg.wait_for_timeout(400)
    t1 = fake.placed()[-1]["client_token"]
    await pg.evaluate("a => OrderApp.addItem(a, 'sp', {}, 1)", A); await pg.wait_for_timeout(150)
    fake.place = ["ok"]
    await pg.click("[data-place]"); await pg.wait_for_function("location.pathname.endsWith('/order/')"); await pg.wait_for_timeout(300)
    t2 = fake.placed()[-1]["client_token"]
    check(t1 != t2 and len(fake.orders) == 3, f"a changed order after a try that didn't go in gets a new client_token ({t1[:8]} then {t2[:8]})")
    # an empty cart, and WhatsApp mode
    await pg.goto(BASE + "checkout/", wait_until="networkidle")
    empty = await pg.evaluate("(document.querySelector('.empty__t') || {}).textContent")
    check(empty == "Your order is empty", f"checkout with nothing in the cart says so ({empty})")
    check(not pg._errs, "the error and retry cases ran with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()
    ctx, pg = await app_page(br, fake, T_LATE, site_json=dict(site, ordering="whatsapp"))
    await fill_cart(pg, A, a1["id"])
    await pg.goto(BASE + f"checkout/?from={A}", wait_until="networkidle")
    off = await pg.evaluate("[document.getElementById('oa-main').innerText, (document.querySelector('.empty .btn') || {}).href || '']")
    check("Orders go in on WhatsApp right now." in off[0] and off[1].endswith(f"/{A}/#o"), "with site.json \"ordering\": \"whatsapp\" the checkout takes no order and sends people back to the order sheet")
    await ctx.close()

async def preorder(br, width=390):
    """3 PM, closed: no as soon as possible, a time tonight, sent as due_at"""
    fake = FakeDB(iso_now(T_AFTERNOON))
    ctx, pg = await app_page(br, fake, T_AFTERNOON, width)
    A = open_mix[0]
    await fill_cart(pg, A, dish(A)["id"])
    await pg.evaluate("OrderApp.saveDetails({name: 'Eva', phone: '5601234', area: 'Eagle Beach', addr: 'Hotel lobby, room 214', pay: 'cash', usd: true})")
    await pg.goto(BASE + f"checkout/?from={A}", wait_until="networkidle"); await pg.wait_for_timeout(200)
    r = await pg.evaluate("""() => [location.hash, !!document.querySelector('input[name=ck-when]'), (document.querySelector('.note') || {}).textContent,
        Array.from(document.querySelectorAll('.time span')).map(s => s.textContent)]""")
    check(r[0] == "#where" and not r[1] and r[2] == "We’re closed now. Opens tonight 10 PM. Pick a time and it’s a pre-order: we start on it when we open." and r[3][:1] == ["10:30 PM"]
          and r[3][-1] == "1:45 AM" and await fits(pg),
          f"[{width}px] 3 PM: closed, no as soon as possible, times tonight from 10:30 PM (half an hour after opening) to 1:45 AM ({r[2]!r}, {r[3][:2]}..)")
    await shot(pg, "checkout-1-preorder", end=True)
    await pg.click(tap("2026-10-11T03:00:00.000Z", "ck-time"))
    await pg.click("[data-next]"); await pg.wait_for_timeout(250)
    r = await pg.evaluate("[location.hash, (document.querySelector('.note') || {}).textContent, document.querySelector('.recap').innerText]")
    check(r[0] == "#check" and r[1] == "Pre-order for tonight, 11:00 PM" and "Cash in US dollars" in r[2], f"[{width}px] the check step says it's a pre-order for 11:00 PM ({r[1]!r})")
    await shot(pg, "checkout-4-check-preorder", end=True)
    await pg.click("[data-place]"); await pg.wait_for_function("location.pathname.endsWith('/order/')"); await pg.wait_for_timeout(300)
    p = fake.placed()[-1]
    check(p.get("due_at") == "2026-10-11T03:00:00.000Z" and p.get("pays_in_usd") is True and "pays_with_cents" not in p,
          f"[{width}px] the pre-order goes in with due_at (11 PM Aruba in UTC) and cash in US dollars ({p.get('due_at')})")
    eta = await pg.evaluate("(document.querySelector('.st__eta') || {}).textContent")
    check(eta == "Arrives around 11 PM", f"[{width}px] its status page: arrives around 11 PM ({eta!r})")
    await shot(pg, "status-1-preorder", end=True)
    check(not pg._errs, f"[{width}px] the pre-order ran with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

STAGE_WORDS = ["Received", "Cooking", "On the way", "Delivered"]
async def status_checks(br, width=390):
    """every state of an order, its times, how they pay, a link nobody knows, and the page asking again by itself"""
    fake = FakeDB(iso_now(T_LATE))
    ctx, pg = await app_page(br, fake, T_LATE, width, fixed=False)
    A, B = open_mix[0], open_mix[1]
    base = {"name": "Maria", "phone": "5931234", "area": "Noord", "address": "Weg 12", "pay": "cash", "pays_with_cents": 10000,
            "items": [{"restaurant": A, "id": dish(A)["id"], "name": dish(A)["name"], "qty": 1, "price_cents": dish(A)["price"]},
                      {"restaurant": B, "id": dish(B)["id"], "name": dish(B)["name"] + " · No onion", "qty": 2, "price_cents": dish(B)["price"]},
                      {"restaurant": A, "id": "ck", "name": "Coca-Cola (can)", "qty": 1, "price_cents": 300}]}
    o = fake.order_from(base, 1)
    fake.orders["tok-1"] = o
    def at(minutes): return (utc(T_LATE) + datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    flow = [("new", 0), ("accepted", 1), ("cooking", 3), ("ready", 22), ("assigned", 24), ("picked_up", 27), ("delivered", 41)]
    await pg.goto(BASE + "order/#t=tok-1", wait_until="networkidle"); await pg.wait_for_timeout(300)
    async def read():
        return await pg.evaluate("""() => ({t: (document.querySelector('.st__t') || {}).textContent, eta: (document.querySelector('.st__eta') || {}).textContent || '',
            line: (document.querySelector('.st__line') || {}).textContent, k: (document.querySelector('.st__k') || {}).textContent,
            track: Array.from(document.querySelectorAll('.track__s')).map(s => s.className.replace('track__s is-', '') + (s.querySelector('.track__t') ? '@' + s.querySelector('.track__t').textContent : '')),
            pay: (document.querySelector('.st-pay') || {}).textContent, wa: (document.querySelector('.st-wa') || {}).href || ''})""")
    r = await read()
    check(r["t"] == "Received" and r["k"] == "Order 11 for Maria · Noord" and r["eta"] == "Arrives between 12:05 and 12:20 AM"
          and r["line"] == f"{NAMES[A]} and {NAMES[B]} got your order." and r["track"][0] == "now@11:30 PM" and r["track"][1:] == ["todo", "todo", "todo"]
          and r["pay"] == f"Cash: you pay with ƒ100.00, the driver brings {money(10000 - o['total_cents'])} change." and r["wa"].startswith("https://wa.me/" + site["whatsapp"]) and await fits(pg),
          f"[{width}px] Received: the order number and name, when it arrives ({ETA[0]}–{ETA[1]} min after it went in), who has it, the steps, the change ({r['eta']!r})")
    await shot(pg, "status-2-received", end=True)
    calls = len([c for c in fake.calls if c[0] == "pidi_order_status"])
    for status, minutes in flow[1:]:
        o["events"].append({"status": status, "at": at(minutes)})
        o["status"] = status
        await pg.clock.run_for(16000); await pg.wait_for_timeout(150)
        r = await read()
        i = {"accepted": 0, "cooking": 1, "ready": 1, "assigned": 2, "picked_up": 2, "delivered": 3}[status]
        want = {"cooking": f"Your order is being made right now.", "picked_up": "The driver has your order. Keep your phone close."}.get(status)
        ok = r["t"] == STAGE_WORDS[i] and (status == "delivered" or r["track"][i].startswith("now")) and (not want or r["line"] == want)
        if status == "delivered":
            ok = ok and r["line"] == f"Delivered at {at_clock(41)}. Danki." and all(x.startswith("done@") for x in r["track"]) and r["eta"] == ""
        check(ok, f"[{width}px] {status}: the page asks again by itself within 15 s and shows \"{STAGE_WORDS[i]}\" ({r['t']}, {r['track']})")
        if status in ("cooking", "picked_up", "delivered"):
            await shot(pg, "status-" + {"cooking": "3-cooking", "picked_up": "4-on-the-way", "delivered": "5-delivered"}[status], end=True)
    n_calls = len([c for c in fake.calls if c[0] == "pidi_order_status"])
    await pg.clock.run_for(60000); await pg.wait_for_timeout(150)
    check(len([c for c in fake.calls if c[0] == "pidi_order_status"]) == n_calls and n_calls >= calls + 6, f"[{width}px] once delivered it stops asking ({n_calls} asks)")
    # cancelled, US dollars, bank transfer, a link nobody knows, the list of this phone's orders
    o2 = fake.order_from(dict(base, pay="transfer", pays_with_cents=None), 2)
    o2.update(status="cancelled", events=[{"status": "new", "at": at(0)}, {"status": "cancelled", "at": at(4)}])
    o3 = fake.order_from(dict(base, pays_in_usd=True, pays_with_cents=None), 3)
    o4 = fake.order_from(dict(base, pay="transfer", pays_with_cents=None), 4)
    o4.update(status="cooking", transfer_status="paid", events=[{"status": "new", "at": at(0)}, {"status": "cooking", "at": at(2)}])
    fake.orders.update({"tok-2": o2, "tok-3": o3, "tok-4": o4})
    await pg.evaluate("ts => ts.forEach(t => OrderApp.rememberOrder({public_token: t, night_no: 12, total_cents: 4321, created_at: '" + T_LATE + "', restaurants: [{slug: 'x', name: 'Taco Brava'}]}))", ["tok-3", "tok-2"])
    for tokn, name, want in (("tok-2", "status-6-cancelled", {"t": "Cancelled", "pay": "Bank transfer. We send the bank details on WhatsApp when we confirm."}),
                              ("tok-3", "status-7-usd", {"t": "Received", "pay": "Cash in US dollars. The driver tells you the amount at the door."}),
                              ("tok-4", "status-8-transfer-paid", {"t": "Cooking", "pay": "Bank transfer: received. Danki."})):
        await pg.goto(BASE + "order/#t=" + tokn, wait_until="networkidle"); await pg.reload(wait_until="networkidle"); await pg.wait_for_timeout(300)
        r = await read()
        ok = all(r[k] == v for k, v in want.items()) and (tokn != "tok-2" or (r["track"] == [] and r["eta"] == ""))
        check(ok, f"[{width}px] {name.split('-', 2)[-1]}: \"{want['t']}\", and how they pay: \"{want['pay']}\"" + ("" if ok else f" ({r})"))
        await shot(pg, name, end=True)
    others = await pg.evaluate("Array.from(document.querySelectorAll('.ord')).map(a => a.getAttribute('href'))")
    check(others == ["#t=tok-2", "#t=tok-3"] or set(others) >= {"#t=tok-2"}, f"[{width}px] under it, this phone's other orders link to their own status ({others})")
    await pg.goto(BASE + "order/#t=nobody-knows", wait_until="networkidle"); await pg.reload(wait_until="networkidle"); await pg.wait_for_timeout(300)
    nf = await pg.evaluate("[(document.querySelector('h1') || {}).textContent, (document.querySelector('.btn--wa') || {}).href || '']")
    check(nf[0] == "We can’t find this order" and nf[1].startswith("https://wa.me/"), f"[{width}px] a link nobody knows: \"We can’t find this order\" and WhatsApp ({nf[0]})")
    await shot(pg, "status-9-not-found")
    await pg.goto(BASE + "order/", wait_until="networkidle"); await pg.reload(wait_until="networkidle"); await pg.wait_for_timeout(300)
    lst = await pg.evaluate("[(document.querySelector('h1') || {}).textContent, document.querySelectorAll('.ord').length]")
    check(lst == ["Your orders", 2], f"[{width}px] order/ without a link lists this phone's orders ({lst})")
    # in Spanish
    await pg.evaluate("localStorage.setItem('pidi.lang.v1', 'es')")
    await pg.goto(BASE + "order/#t=tok-4", wait_until="networkidle"); await pg.reload(wait_until="networkidle"); await pg.wait_for_timeout(300)
    r = await read()
    check(r["t"] == words["es"]["Cooking"] and r["pay"] == words["es"]["Bank transfer: received. Danki."] and r["track"][0].endswith("23:30"),
          f"[{width}px] [es] the status page in Spanish, 24-hour times ({r['t']}, {r['track'][0]})")
    await shot(pg, "status-es-cooking")
    check(not pg._errs, f"[{width}px] the status page ran with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

async def brand_app_mode(br, width=390):
    """a restaurant page in app mode: its order sheet (Continue, no WhatsApp form), and the way back to a placed order"""
    fake = FakeDB(iso_now(T_LATE))
    ctx, pg = await app_page(br, fake, T_LATE, width)
    A, B = open_mix[0], open_mix[1]
    await pg.goto(BASE + A + "/index.html", wait_until="networkidle"); await pg.wait_for_timeout(300)
    await shot(pg, "restaurant-page")
    await fill_cart(pg, A, dish(A)["id"], B, dish(B)["id"])
    await pg.wait_for_timeout(200)
    await shot(pg, "restaurant-page-with-order")
    await pg.click(".bar__btn"); await pg.wait_for_timeout(450)
    r = await pg.evaluate("""() => { const s = document.querySelector('.oa-sheet__panel');
        return [s.querySelector('[data-go]').getAttribute('href'), !!s.querySelector('[data-send], #oa-addr, .ticket'), document.documentElement.scrollWidth <= innerWidth + 1]; }""")
    check(r == [f"../checkout/?from={A}", False, True], f"[{width}px] app mode: {NAMES[A]}'s order sheet goes on to checkout/ ({r})")
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        await pg.screenshot(path=os.path.join(SHOTS, f"restaurant-order-sheet-{width}.png"))
        await pg.evaluate("document.querySelector('.oa-sheet__panel').scrollTo(0, 99999)"); await pg.wait_for_timeout(200)
        await pg.screenshot(path=os.path.join(SHOTS, f"restaurant-order-sheet-{width}-end.png"))
    await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
    # after an order: a row at the top of the restaurant page and on the home page leads back to its status
    await pg.evaluate("a => { OrderApp.rememberOrder({public_token: 'tok-9', night_no: 19, total_cents: 4321, restaurants: [{slug: a, name: 'x'}]}); OrderApp.clear(); }", A)
    await pg.goto(BASE + A + "/index.html", wait_until="networkidle"); await pg.wait_for_timeout(300)
    row = await pg.evaluate("[(document.querySelector('#oa-track a') || {}).getAttribute ? document.querySelector('#oa-track a').getAttribute('href') : '', (document.querySelector('#oa-track') || {}).innerText]")
    check(row[0] == "../order/#t=tok-9" and "Track it" in (row[1] or ""), f"[{width}px] after an order, the restaurant page has \"Track it\" back to its status ({row})")
    await shot(pg, "restaurant-page-track")
    await pg.goto(BASE + "index.html", wait_until="networkidle"); await pg.wait_for_timeout(300)
    home = await pg.evaluate("Array.from(document.querySelectorAll('#oa-mine a')).map(a => a.getAttribute('href'))")
    check("order/#t=tok-9" in home, f"[{width}px] and the home page's \"Your order\" row does too ({home})")
    await shot(pg, "home-track")
    check(not pg._errs, f"[{width}px] the restaurant page in app mode ran with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

def at_clock(minutes):
    t = utc(T_LATE) + datetime.timedelta(minutes=minutes, hours=-4)
    h, m = t.hour, t.minute
    return f"{h % 12 or 12}{':%02d' % m if m else ''} {'PM' if h >= 12 else 'AM'}"

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        await api_checks(br)
        await look_checks(br)
        if len(open_mix) >= 2:
            for w in (390, 320):
                await checkout_flow(br, w)
            await checkout_cases(br)
            for w in (390, 320):
                await preorder(br, w)
                await status_checks(br, w)
                await brand_app_mode(br, w)
        else:
            check(False, "the checkout tests need two open restaurants that share one order")
        await br.close()
asyncio.run(main())
check(not db_calls, f"the API checks never called the order database ({db_calls})")
check(not leaks, f"nothing reached the real order database ({leaks})")
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
