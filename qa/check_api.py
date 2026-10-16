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

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        await api_checks(br)
        await look_checks(br)
        await br.close()
asyncio.run(main())
check(not db_calls, f"nothing called the order database ({db_calls})")
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
