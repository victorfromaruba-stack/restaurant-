"""Pidi's frame and the engine's API for its own pages: python3 qa/check_api.py (qa/check_site.py runs it too).
It serves the repo itself (qa/local_server.py); QA_BASE=<url> checks another server.

The checkout and the order status pages (checkout/, order/) are built on window.OrderApp from shared/order-app.js
(the API is written out at the top of that file). This loads the placeholder checkout/ and order/ pages and checks
that every member is there and does what it says: one delivery fee for a cart from two restaurants (the highest),
the food minimum, cart lines with their options after " · ", the pre-order times on the Aruba clock while the
phone is set to another time zone, the customer's details and the remembered orders, the four languages.
It also checks the frame on the restaurant pages: the ink ground, Pidi's fonts, the Pidi bar with the delivery fee
and the minimum, blue only on ordering actions, and an order under the minimum that can't be sent yet.
Nothing here places an order: every /rest/v1/ request is answered by a fake (and none is expected)."""
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
def short(c): return "ƒ" + (str(c // 100) if c % 100 == 0 else f"{c / 100:.2f}")
def money(c): return f"ƒ{c / 100:.2f}"
def fee_of(b): return next((x.get("fee") for x in site["brands"] if x["id"] == b), None) or site.get("deliveryFee", 0)
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
    "ready": "object", "site": "function", "menu": "function", "loadMenu": "function", "tr": "function", "money": "function",
    "lang": "function", "clock": "function", "arubaNow": "function", "shopStatus": "function", "slots": "function",
    "canOrderNow": "function", "lines": "function", "food": "function", "fee": "function", "total": "function",
    "minFood": "function", "shortBy": "function", "setLineQty": "function", "clear": "function", "details": "function",
    "saveDetails": "function", "rememberOrder": "function", "orders": "function", "onChange": "function",
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
    await pg.goto(BASE + "checkout/index.html", wait_until="networkidle")
    await pg.evaluate("localStorage.clear()")
    fired = await ready(pg, "checkout/index.html")
    check(fired == 1, f"checkout/: OrderApp.ready resolves and \"oa:ready\" fires once ({fired})")
    types = dict(await pg.evaluate("names => names.map(n => [n, typeof OrderApp[n]])", list(MEMBERS)))
    bad = {n: t for n, t in types.items() if t != MEMBERS[n]}
    check(not bad and await pg.evaluate("OrderApp.ready instanceof Promise"), f"OrderApp has every member of the API ({len(MEMBERS)})" + (f": {bad}" if bad else ""))
    drawn = await pg.evaluate("""() => ({extra: Array.from(document.querySelectorAll('#oa-bar, .bar, .oa-sheet, .oa-toast, .iab')).length,
        langs: Array.from(document.querySelectorAll('[data-oa-langs] button')).map(b => b.textContent + (b.getAttribute('aria-pressed') === 'true' ? '*' : '')),
        h1: document.querySelector('h1').textContent, lang: document.documentElement.lang, ready: document.body.classList.contains('oa-ready')})""")
    check(drawn["extra"] == 0 and drawn["langs"] == ["EN*", "PAP", "NL", "ES"] and drawn["h1"] == "Checkout is coming" and drawn["lang"] == "en",
          f"app mode draws nothing but the page's own words and the language switch ({drawn})")
    check(await pg.evaluate("[OrderApp.lang(), OrderApp.site().name, OrderApp.minFood(), OrderApp.tr('Add {gap} more food', {gap: 'ƒ3.50'})]")
          == ["en", site["name"], site.get("minFood") or 2400, "Add ƒ3.50 more food"], "lang(), site(), minFood() and tr() with a value")
    m = await pg.evaluate("[OrderApp.money(1295), OrderApp.money(1295, true), OrderApp.money(500)]")
    check(m[0] == "ƒ12.95" and m[2] == "ƒ5.00" and '<span aria-hidden="true">ƒ12.95</span>' in m[1] and 'class="sr"' in m[1] and "12.95 florins" in m[1],
          f"money(): ƒ12.95 on screen, \"12.95 florins\" for a screen reader ({m})")
    c = await pg.evaluate("[OrderApp.clock(1435), OrderApp.clock(1320), OrderApp.clock(1320, true), OrderApp.clock(0, true), OrderApp.clock(45)]")
    check(c == [f"11:55{NBSP}PM", f"10{NBSP}PM", f"10:00{NBSP}PM", f"12:00{NBSP}AM", f"12:45{NBSP}AM"], f"clock() in English, a no-break space before PM ({c})")

    # ---- time: the Aruba clock, whatever the phone's zone
    async def at(t):
        await pg.clock.set_fixed_time(t)
        return await pg.evaluate("({now: OrderApp.arubaNow(), open: OrderApp.shopStatus().open, can: OrderApp.canOrderNow(), slots: OrderApp.slots()})")
    r = await at(T_AFTERNOON)
    s = r["slots"]
    check(r["now"]["mins"] == 15 * 60 and r["now"]["day"] == 6 and r["now"]["date"] == "2026-10-10",
          f"arubaNow() is 3:00 PM Saturday in Aruba while the phone says 9 PM in Amsterdam ({r['now']})")
    check(not r["open"] and not r["can"], "3 PM: closed, no order for as soon as possible")
    check(len(s) == 16 and s[0] == {"m": 1320, "label": f"10:00{NBSP}PM", "iso": "2026-10-11T02:00:00.000Z"}
          and s[-1] == {"m": 105, "label": f"1:45{NBSP}AM", "iso": "2026-10-11T05:45:00.000Z"}
          and all(re.match(r"^\d\d:\d\d:00\.000Z$", x["iso"][11:]) and int(x["iso"][14:16]) % 15 == 0 for x in s),
          f"3 PM: tonight's 16 times, 10:00 PM to 1:45 AM Aruba, every 15 min, sent in UTC ({s[0] if s else None} .. {s[-1] if s else None})")
    r = await at(T_LATE)
    s = r["slots"]
    check(r["open"] and r["can"] and r["now"]["mins"] == 23 * 60 + 30, "11:30 PM: open, an order for as soon as possible goes in")
    check(bool(s) and s[0]["iso"] == "2026-10-11T04:00:00.000Z" and s[0]["label"] == f"12:00{NBSP}AM" and s[-1]["iso"] == "2026-10-11T05:45:00.000Z",
          f"11:30 PM: the times left tonight start 20 min or more from now, at midnight ({[x['label'] for x in s]})")
    r = await at(T_LAST)
    check(r["can"] and [x["iso"] for x in r["slots"]] == ["2026-10-11T05:45:00.000Z"], f"1:20 AM: still open, one time left (1:45 AM) ({r['slots']})")
    r = await at(T_AFTER)
    s = r["slots"]
    check(not r["can"] and not r["open"], "1:40 AM: after last orders, nothing as soon as possible")
    check(bool(s) and s[0]["iso"] == "2026-10-12T02:00:00.000Z" and s[-1]["iso"] == "2026-10-12T05:30:00.000Z",
          f"1:40 AM: the coming night's times, never more than 24 h ahead (10:00 PM to 1:30 AM) ({s[0]['label'] if s else None} .. {s[-1]['label'] if s else None})")
    await pg.clock.set_fixed_time(T_LATE)

    # ---- the cart: one fee, the minimum, the lines
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
        check(food == want_food and fee == max(fee_of(A), fee_of(B)) and total == food + fee,
              f"{menus[A]['name']} + {menus[B]['name']}: food {food}, one delivery fee {fee} (the higher of theirs), total {total}")
        check(await pg.evaluate("window.__changes") >= 3, "onChange() hears every change to the cart")
        k = la["k"] if la else ""
        await pg.evaluate("k => OrderApp.setLineQty(k, 0)", k)
        left = await pg.evaluate("OrderApp.lines().map(l => l.id)")
        check(a_item["id"] not in left and len(left) == 2, f"setLineQty(k, 0) takes the line out ({left})")
        await pg.evaluate("OrderApp.clear()")
        await pg.evaluate("a => OrderApp.addItem(a, 'ck', {}, 1)", A)
        r = await pg.evaluate("[OrderApp.food(), OrderApp.shortBy(), OrderApp.fee(), OrderApp.total()]")
        mf = site.get("minFood") or 2400
        check(r == [300, mf - 300, fee_of(A), 300 + fee_of(A)], f"one can: food ƒ3.00, {money(mf - 300)} short of the minimum ({r})")
        await pg.evaluate("([b, i]) => OrderApp.addItem(b, i, {}, 3)", [B, b_item["id"]])
        r = await pg.evaluate("[OrderApp.food(), OrderApp.shortBy()]")
        check(r[1] == max(0, mf - r[0]), f"shortBy() is the minimum less the food, never below 0 ({r})")
        await pg.evaluate("OrderApp.clear()")
        r = await pg.evaluate("[OrderApp.lines().length, OrderApp.food(), OrderApp.fee(), OrderApp.total()]")
        check(r == [0, 0, 0, 0], f"clear() empties the cart; an empty cart has no fee ({r})")

        # a restaurant with a higher fee in the same order: the order pays that one fee, once
        ctx2, p2 = await new_page(br)
        await p2.clock.set_fixed_time(T_LATE)
        dear = json.loads(json.dumps(site))
        for x in dear["brands"]:
            if x["id"] == B: x["fee"] = 1000
        await p2.route("**/shared/site.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(dear)))
        await ready(p2, "checkout/index.html")
        await p2.evaluate("([a, b]) => Promise.all([OrderApp.loadMenu(a), OrderApp.loadMenu(b)])", [A, B])
        await p2.evaluate("([a, i, b, j]) => { OrderApp.clear(); OrderApp.addItem(a, i, {}, 1); OrderApp.addItem(b, j, {}, 1); }", [A, a_item["id"], B, b_item["id"]])
        f2 = await p2.evaluate("[OrderApp.fee(), OrderApp.total() - OrderApp.food()]")
        check(f2 == [1000, 1000], f"with a ƒ10 restaurant in the order the one fee is ƒ10, not ƒ15 ({f2})")
        await p2.evaluate("OrderApp.clear()")
        await ctx2.close()

        # ---- the customer's details
        d = await pg.evaluate("""() => { OrderApp.saveDetails({name: 'Maria', phone: '5931234', area: 'Noord', addr: 'Weg 12, blue gate', note: 'Gate 4',
            pay: 'cash', paysWith: 5000, usd: false, junk: 1}); return [OrderApp.details(), JSON.parse(localStorage.getItem('pidi.me.v1'))]; }""")
        want = {"name": "Maria", "phone": "5931234", "area": "Noord", "addr": "Weg 12, blue gate", "note": "Gate 4", "pay": "cash", "paysWith": 5000, "usd": False}
        check(d[0] == want and d[1] == want, f"saveDetails() / details() round trip in localStorage pidi.me.v1 ({d[0]})")
        d = await pg.evaluate("OrderApp.saveDetails({area: 'Mars', usd: true}); OrderApp.details()")
        check(d["area"] == "" and d["usd"] is True and d["name"] == "Maria", "an area that isn't in site.json areas isn't kept")

        # ---- remembering placed orders, and Order again
        await pg.evaluate("([a, i, o, b, j]) => { OrderApp.clear(); OrderApp.addItem(a, i, o, 1); OrderApp.addItem(b, j, {}, 2); }",
                          [A, a_item["id"], chosen, B, b_item["id"]])
        basket = await pg.evaluate("OrderApp.lines()")
        res = {"public_token": "tok-1", "pay": "cash", "total_cents": 4321, "created_at": "2026-10-11T03:30:00Z",
               "restaurants": [{"slug": A, "name": menus[A]["name"]}, {"slug": B, "name": menus[B]["name"]}]}
        rec = await pg.evaluate("r => [OrderApp.rememberOrder(r), OrderApp.orders(), JSON.parse(localStorage.getItem('pidi.last.v1'))]", res)
        first = rec[1][0] if rec[1] else {}
        at = int(datetime.datetime(2026, 10, 11, 3, 30, tzinfo=datetime.timezone.utc).timestamp() * 1000)
        check(first == {"t": "tok-1", "at": at, "restaurants": [menus[A]["name"], menus[B]["name"]], "total_cents": 4321, "pay": "cash", "lines": basket},
              f"rememberOrder() keeps the token, time, restaurants, total, payment and the full basket ({ {k: first.get(k) for k in ('t', 'at', 'restaurants', 'total_cents', 'pay')} })")
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

    # ---- other languages, on both pages
    for code, url, key in (("nl", "checkout/index.html", "Checkout is coming"), ("es", "order/index.html", "Order status is coming"), ("pap", "checkout/index.html", "Checkout is coming")):
        await pg.evaluate("c => localStorage.setItem('pidi.lang.v1', c)", code)
        await ready(pg, url)
        r = await pg.evaluate("""() => [OrderApp.lang(), document.documentElement.lang, document.querySelector('h1').textContent, OrderApp.clock(1435),
            OrderApp.slots().map(s => s.label)[0] || '', OrderApp.tr('Add {gap} more food', {gap: 'ƒ3.50'}), OrderApp.money(300, true),
            document.querySelector('[data-oa-langs] [aria-pressed="true"]').textContent]""")
        w = words[code]
        check(r[:4] == [code, code, w[key], "23:55"] and re.match(r"^\d\d:\d\d$", r[4]) and r[5] == w["Add {gap} more food"].replace("{gap}", "ƒ3.50")
              and ("3.00 " + w["florins"]) in r[6] and r[7] == code.upper(),
              f"[{code}] {url}: lang(), <html lang>, its words, 24-hour times, tr() and money() in that language ({r[:6]})")
    await pg.evaluate("localStorage.removeItem('pidi.lang.v1')")
    check(not pg._errs, "checkout/ and order/ run with no errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

async def frame_checks(br):
    """the frame on the home page and the restaurant pages"""
    ctx, pg = await new_page(br, tz="America/Aruba")
    await pg.clock.set_fixed_time(T_LATE)
    pages = ["index.html"] + [f"{b['id']}/index.html" for b in site["brands"] if b.get("status") != "hidden"]
    for url in pages + ["checkout/index.html", "order/index.html"]:
        await ready(pg, url)
        f = await pg.evaluate("""() => {
          const sheets = Array.from(document.querySelectorAll('link[rel=stylesheet]')).map(l => l.getAttribute('href').split('/').pop());
          return {bg: getComputedStyle(document.body).backgroundColor, html: getComputedStyle(document.documentElement).backgroundColor,
            theme: (document.querySelector('meta[name=theme-color]') || {}).content, vp: (document.querySelector('meta[name=viewport]') || {}).content,
            sheets, font: getComputedStyle(document.querySelector('.pidibar, .top')).fontFamily.replace(/"/g, '')};
        }""")
        ok = f["bg"] == f["html"] == "rgb(18, 20, 58)" and f["theme"] == "#12143A" and "interactive-widget=resizes-content" in f["vp"] \
            and f["sheets"][:1] == ["pidi.css"] and f["font"].startswith("Pidi,")
        check(ok, f"{url}: Pidi's frame (ink ground, theme colour, viewport, pidi.css first, Pidi's type in its bar)" + ("" if ok else f": {f}"))
    # the florin sign comes from Jakarta's latin-ext file, so a price never falls back to a system font
    await ready(pg, pages[1])
    await pg.evaluate("document.fonts.ready")
    ext = await pg.evaluate("""() => Array.from(document.fonts).filter(f => f.family.replace(/"/g, '') === 'Pidi' && /U\\+192\\b/i.test(f.unicodeRange)).map(f => f.weight + ':' + f.status)""")
    check(any(x.endswith(":loaded") for x in ext) and len(ext) == 3, f"the florin sign is drawn in Pidi's own type (latin-ext faces: {ext})")
    # the Pidi bar: open state and delivery time, then this restaurant's fee and the food minimum
    mf = site.get("minFood") or 2400
    eta = f"{site['etaMin']}–{site['etaMax']} min"
    for b in site["brands"]:
        if b.get("status") == "hidden":
            continue
        await ready(pg, b["id"] + "/index.html")
        lines = await pg.evaluate("Array.from(document.querySelectorAll('[data-oa-bar-facts] > span')).map(s => s.textContent)")
        want1 = f"Open · {eta}" if b.get("status", "open") == "open" else "Opening soon"
        want2 = f"{short(fee_of(b['id']))} delivery · {short(mf)} minimum"
        check(lines == [want1, want2], f"{b['id']}: the Pidi bar says \"{want1}\" and \"{want2}\" ({lines})")
    if open_mix:
        A = open_mix[0]
        await pg.clock.set_fixed_time(T_AFTERNOON)
        await ready(pg, A + "/index.html")
        lines = await pg.evaluate("Array.from(document.querySelectorAll('[data-oa-bar-facts] > span')).map(s => s.textContent)")
        check(lines[:1] == [f"Opens 10{NBSP}PM · Pre-order"], f"{A} at 3 PM: the Pidi bar says when it opens, never when it closes ({lines})")
        await pg.clock.set_fixed_time(T_LATE)
        # under the food minimum: the cart bar says how much more food, and the order can't be sent yet
        await ready(pg, A + "/index.html")
        await pg.evaluate("a => { OrderApp.clear(); OrderApp.addItem(a, 'ck', {}, 1); }", A)
        bar = await pg.evaluate("""() => { const b = document.querySelector('#oa-bar .bar__btn');
          return [b && !b.closest('[hidden]'), b && b.classList.contains('is-short'), b && b.querySelector('.bar__label').textContent,
                  b && getComputedStyle(b).getPropertyValue('--fill').trim()]; }""")
        gap = money(mf - 300)
        check(bar[:3] == [True, True, f"Add {gap} more food"] and abs(float(bar[3] or 0) - 300 / mf) < 0.001,
              f"one can in the order: the cart bar says \"Add {gap} more food\" and the peach line is at {300 / mf:.0%} ({bar})")
        await pg.click("#oa-bar .bar__btn"); await pg.wait_for_timeout(400)
        sheet = await pg.evaluate("""() => [!!document.querySelector('.oa-sheet [data-send]'), !!document.querySelector('.oa-sheet [data-copy]'),
            (document.querySelector('.oa-sheet [data-short]') || {}).textContent || '']""")
        check(sheet == [False, False, f"Add {gap} more food"], f"under the minimum the order sheet has no Send, only \"Add {gap} more food\" ({sheet})")
        await pg.click(".oa-sheet [data-short]"); await pg.wait_for_timeout(500)
        focus = await pg.evaluate("document.activeElement && document.activeElement.matches('.addon .add, .bar__btn')")
        sent = await pg.evaluate("OrderApp.state().sentAt")
        check(focus and not sent, "tapping it goes to more food (the sides and drinks) and sends nothing")
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        big = max((i for i in menus[A]["items"] if i.get("kind") != "drink" and not i.get("soldOut")), key=lambda i: i["price"])
        n = -(-mf // big["price"])
        await pg.evaluate("([a, i, n]) => OrderApp.addItem(a, i, {}, n)", [A, big["id"], n])
        bar = await pg.evaluate("""() => { const b = document.querySelector('#oa-bar .bar__btn');
          return [b.classList.contains('is-short'), b.querySelector('.bar__label').textContent, b.querySelector('.bar__sub').textContent,
                  b.querySelector('.bar__total [aria-hidden]').textContent, OrderApp.total()]; }""")
        check(not bar[0] and bar[1] == "View order" and bar[2] == f"incl. {short(fee_of(A))} delivery" and bar[3] == money(bar[4]),
              f"at the minimum the cart bar shows the total with the delivery fee in it ({bar[:4]})")
        await pg.click("#oa-bar .bar__btn"); await pg.wait_for_timeout(400)
        # Pidi Blue only on ordering actions, each with its light edge
        blue = await pg.evaluate("""() => Array.from(document.querySelectorAll('body *')).filter(e => getComputedStyle(e).backgroundColor === 'rgb(45, 59, 232)')
            .map(e => [e.className, getComputedStyle(e).borderTopColor, getComputedStyle(e).borderTopWidth])""")
        ok = bool(blue) and all(re.search(r"\b(bar__btn|btn--send)\b", c) and t == "rgb(140, 150, 255)" and w == "2px" for c, t, w in blue)
        check(ok and any("btn--send" in c for c, _, _ in blue), f"Pidi Blue only on the cart bar and Send, each with a 2px light top edge ({blue})")
        await pg.evaluate("OrderApp.clear()")
    # the placeholder pages aren't linked from anywhere yet
    linked = []
    for url in pages:
        await ready(pg, url)
        await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); await pg.wait_for_timeout(600)
        linked += [h for h in await pg.evaluate("Array.from(document.querySelectorAll('a[href]')).map(a => a.href)")
                   if re.search(r"/(checkout|order)/", h)]
    sitemap = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read()
    check(not linked and "/checkout/" not in sitemap and "/order/" not in sitemap, "nothing links to checkout/ or order/ yet" + (f": {linked}" if linked else ""))
    check(not pg._errs, "the frame checks ran with no page errors" + (f": {pg._errs}" if pg._errs else ""))
    await ctx.close()

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        await api_checks(br)
        await frame_checks(br)
        await br.close()
asyncio.run(main())
check(not db_calls, f"nothing called the order database ({db_calls})")
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
