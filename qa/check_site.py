"""Site check: python3 qa/check_site.py from the repo folder. It serves the repo itself for the run
(qa/local_server.py), so there is no server to start first. QA_BASE=<url> checks another server instead.
Checks every menu image exists, every page loads with no errors, and builds the WhatsApp sample
messages in qa/wa-samples.json from the real ordering code, testing the owner's rules.
Order Aruba is a delivery app, like Uber Eats (Victor, 9 Oct 2026): the home page lists the restaurants,
and customers must believe each one is its own business. Nothing may say or hint that they share a
kitchen, one order never mixes restaurants, and a restaurant's order, ticket and receipt never name
another restaurant."""
import asyncio, json, os, re, subprocess, sys
from playwright.async_api import async_playwright
from PIL import Image, ImageChops, ImageStat
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start
BASE = start()
fails = []
def square_sample(path):
    im = Image.open(path).convert("L"); s = min(im.size); l, t = (im.width - s) // 2, (im.height - s) // 2
    return im.crop((l, t, l + s, t + s)).resize((24, 24), Image.LANCZOS)
def thumb_ok(img):
    d, f = os.path.split(os.path.join(ROOT, img)); th = os.path.join(d, "thumbs", f)   # same name as the picture
    if not os.path.exists(th): return False
    return ImageStat.Stat(ImageChops.difference(square_sample(os.path.join(ROOT, img)), square_sample(th))).mean[0] < 8
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)

site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
brands = [b["id"] for b in site["brands"]]
menus = {b: json.load(open(os.path.join(ROOT, b, "menu.json"), encoding="utf-8")) for b in brands}
for b, m in menus.items():
    for key in ("logo", "mark", "hero"):
        check(os.path.exists(os.path.join(ROOT, m[key])), f"{b} {key} file exists ({m[key]})")
    if m.get("video"):
        for k in ("src", "poster"):
            check(os.path.exists(os.path.join(ROOT, m["video"][k])), f"{b} cover video {k} exists ({m['video'][k]})")
        src = os.path.join(ROOT, m["video"]["src"])
        check(not os.path.exists(src) or os.path.getsize(src) <= 1.5 * 1024 * 1024, f"{b} cover video is under 1.5 MB")
    ids = [i["id"] for i in m["items"]]
    check(len(ids) == len(set(ids)), f"{b} item ids are unique")
    secs = {s["id"] for s in m["sections"]}
    for it in m["items"]:
        check(os.path.exists(os.path.join(ROOT, it["img"])), f"{b}/{it['id']} image exists ({it['img']})")
        if it.get("kind") != "drink" and os.path.exists(os.path.join(ROOT, it["img"])):
            check(thumb_ok(it["img"]), f"{b}/{it['id']} row thumbnail is there and up to date (else run: python3 build/thumbs.py)")
        check(it["section"] in secs, f"{b}/{it['id']} is in a real section")
        check(isinstance(it["price"], int) and it["price"] > 0, f"{b}/{it['id']} has a price in cents")
        for inc in it.get("includes", []):
            check(inc in ids, f"{b}/{it['id']} bundle item {inc} exists")
    drinks = {i["id"]: (i["name"], i["price"]) for i in m["items"] if i.get("kind") == "drink"}
    check(drinks == {"ck": ("Coca-Cola (can)", 300), "cz": ("Coca-Cola Zero (can)", 300), "sp": ("Sprite (can)", 300)},
          f"{b} sells Coke, Coke Zero and Sprite as separate ƒ3 items")
    mains = [i for i in m["items"] if i.get("kind") not in ("drink",)]
    check(6 <= len(mains) <= 9, f"{b} has a tight menu ({len(mains)} food items)")
# Allergens on the site must cover what the kitchen's own recipe cards put in the dish (ops/kitchen/kitchen-data.json).
# Found 8 Oct 2026: tenders in buttermilk brine, sesame garnish and oyster sauce were missing from the site.
ALLERGEN_WORDS = {
    "dairy": r"buttermilk|\bmilk\b|cream|cheese|cheddar|mozzarella|parmesan|(?<!peanut )\bbutter\b(?!-sheen)",
    "gluten": r"flour|\bbuns?\b|bread|panko|noodle|pasta|penne|spaghetti|wrapper|tortilla",
    "egg": r"\beggs?\b|mayo", "soy": r"\bsoy\b|ketjap", "shellfish": r"shrimp|prawn|oyster",
    "sesame": r"sesame", "peanut": r"peanut", "mustard": r"mustard", "fish": r"fish sauce|anchov",
}
kdata = os.path.join(ROOT, "ops/kitchen/kitchen-data.json")
if os.path.exists(kdata):
    kdishes = json.load(open(kdata, encoding="utf-8"))["dishes"]
    for b, m in menus.items():
        for it in m["items"]:
            card = kdishes.get(f"{b}/{it['id']}")
            if it.get("kind") == "drink" or not card:
                continue
            recipe = json.dumps({k: card.get(k) for k in ("ahead", "before", "steps", "plating", "ingredients", "options")}, ensure_ascii=False).lower()
            need = {a for a, pat in ALLERGEN_WORDS.items() if re.search(pat, recipe)} | set(card.get("allergens", []))
            missing = sorted(need - set(it.get("allergens", [])))
            check(not missing, f"{b}/{it['id']} lists every allergen its recipe card uses" + (f": missing {missing}" if missing else ""))
tb = {i["id"]: i for i in menus["taco-brava"]["items"]}
check(tb["bt"]["price"] == 2700, "Birria tacos stay at ƒ27.00")
check(site["deliveryFee"] == 500, "Delivery fee is ƒ5.00")
lang = subprocess.run([sys.executable, os.path.join(ROOT, "build/lang_keys.py"), "--check"], capture_output=True, text=True)
seo = subprocess.run([sys.executable, os.path.join(ROOT, "build/seo.py"), "--check"], capture_output=True, text=True)
check(seo.returncode == 0, "Google listing data matches site.json and the menus (else run: python3 build/seo.py)" + ("" if seo.returncode == 0 else ": " + seo.stdout.strip()))
check(lang.returncode == 0, "every screen phrase has a Papiamento, Dutch and Spanish translation" + ("" if lang.returncode == 0 else ":\n" + lang.stdout[-1500:]))

# one restaurant per order: each sample runs on its own restaurant's page
SAMPLES = [
  ("Dushi Wok, modifiers and a can", "dushi-wok", [("fr", {"leave": ["onion", "egg"]}, 2), ("ss", {"sauce": "on-the-side"}, 1), ("ck", {}, 1)],
   {"area": "Noord", "addr": "Palm Beach 12, blue gate", "name": "Ana", "note": "no peanuts please", "pay": "Cash"}),
  ("Taco Brava, all three cans", "taco-brava", [("bt", {}, 1), ("ck", {}, 1), ("cz", {}, 1), ("sp", {}, 2)],
   {"area": "Oranjestad", "addr": "Caya G.F. Betico Croes 10", "name": "Ben", "note": "", "pay": "Bank transfer"}),
  ("Smash Shack, leave-offs", "smash-shack", [("sc", {"leave": ["onion", "pickles"]}, 1), ("fs", {}, 2)],
   {"area": "Santa Cruz", "addr": "Near the church, green house", "name": "Carla", "note": "extra napkins", "pay": "Cash"}),
  ("Nonna's Night In, heat choice", "nonnas-night-in", [("pa", {"heat": "extra-spicy"}, 1)],
   {"area": "Paradera", "addr": "Piedra Plat 3", "name": "Dave", "note": "", "pay": "Cash"}),
  ("Oranje Snack, dip choice", "oranje-snack", [("bb", {"dip": "mustard"}, 2)],
   {"area": "Eagle Beach", "addr": "Hotel lobby, room 214", "name": "Eva", "note": "", "pay": "Bank transfer"}),
]
names = {b: menus[b]["name"] for b in brands}
is_open = {b["id"]: b.get("status", "open") == "open" for b in site["brands"]}
# words that say or hint the restaurants share a kitchen or an owner (Order Aruba itself is fine: it's the app)
KITCHEN_TALK = ("one kitchen", "shared kitchen", "same kitchen", "from our kitchen", "our other restaurant", "sister restaurant",
                "all five", "one delivery", "kitchen order", "mix dishes")
def talk(text):
    return [w for w in KITCHEN_TALK if w in text.lower()]
def others_in(text, here):
    return [n for b, n in names.items() if b != here and (n in text or n.replace("’", "'") in text)]
# public files the pages load: nothing in them may hint at a shared kitchen
pub = ["index.html", "404.html", "sw.js", "shared/site.json", "shared/order.css", "shared/hub.css", "shared/order-app.js",
       "shared/lang/pap.json", "shared/lang/nl.json", "shared/lang/es.json"] + [f"{b}/index.html" for b in brands] + [f"{b}/menu.json" for b in brands]
for f in pub:
    bad = talk(open(os.path.join(ROOT, f), encoding="utf-8").read())
    check(not bad, f"{f} says nothing about a shared kitchen" + (f": {bad}" if bad else ""))
for b in brands:
    html = open(os.path.join(ROOT, b, "index.html"), encoding="utf-8").read()
    others = [x for x in brands if x != b and (x + "/" in html or names[x] in html)]
    check(not others and "parentOrganization" not in html, f"{b}/index.html (title, Google data) stands on its own" + (f": mentions {others}" if others else ""))
check(not os.path.exists(os.path.join(ROOT, "cart.html")), "no shared cart page: each restaurant is its own order")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(f"page error: {e}"))
        pg.on("console", lambda m: errs.append(f"console: {m.text}") if m.type == "error" and "404" not in m.text else None)
        # ops/chef.html is private (not on the public site); the chef app checks for it on purpose
        pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and not r.url.endswith("ops/chef.html") else None)
        for url in ["index.html", "404.html", "ops/kitchen/index.html"] + [f"{x}/index.html" for x in brands]:
            errs.clear()
            await pg.goto(BASE + url, wait_until="networkidle")
            h = await pg.evaluate("document.body.scrollHeight")
            for y in range(0, h, 700):
                await pg.evaluate(f"window.scrollTo(0,{y})"); await pg.wait_for_timeout(40)
            await pg.wait_for_timeout(300)
            broken = await pg.evaluate("Array.from(document.images).filter(i => i.complete && i.naturalWidth === 0).map(i => i.src)")
            check(not errs and not broken, f"{url} loads with no errors or broken images" + (f": {errs + broken}" if errs or broken else ""))
        out = []
        for title, br, lines, meta in [x for x in SAMPLES if is_open.get(x[1])]:
            await pg.goto(BASE + br + "/index.html", wait_until="networkidle")
            await pg.evaluate("OrderApp.clear()")
            for (iid, opts, q) in lines:
                await pg.evaluate("([b,i,o,q]) => OrderApp.loadMenu(b).then(() => OrderApp.addItem(b,i,o,q))", [br, iid, opts, q])
            await pg.evaluate("m => OrderApp._set(m)", meta)
            msg = await pg.evaluate("OrderApp.buildMessage()")
            sub, fee, tot = await pg.evaluate("[OrderApp.subtotal(), OrderApp.fee(), OrderApp.total()]")
            out.append({"case": title, "message": msg, "subtotal_cents": sub, "fee_cents": fee, "total_cents": tot})
            low = msg.lower()
            check("flavour" not in low and "flavor" not in low, f"[{title}] never asks for a drink flavour")
            for cid, cname in (("ck", "Coca-Cola (can)"), ("cz", "Coca-Cola Zero (can)"), ("sp", "Sprite (can)")):
                if any(l[0] == cid for l in lines):
                    check(re.search(r"^\d+ × " + re.escape(cname) + r" — ƒ", msg, re.M) is not None, f"[{title}] {cname} is its own line")
            check(fee == 500, f"[{title}] delivery fee is ƒ5")
            check(msg.count("Delivery ƒ") == 1 and "Pickup" not in msg, f"[{title}] fee line appears once, and nothing offers pickup")
            item_sum = sum(int(round(float(x) * 100)) for x in re.findall(r"^\d+ × .+ — ƒ(\d+\.\d\d)$", msg, re.M))
            check(item_sum == sub and tot == sub + fee, f"[{title}] line prices add up to the total")
            first = msg.split("\n")[0]
            check(re.match(r"^\*" + re.escape(names[br]) + r" order\* #\d{4}-[A-Z0-9]{2}$", first) is not None, f"[{title}] header names this restaurant: {first}")
            bad = others_in(msg, br) + talk(msg)
            check(not bad and "Pickup" not in msg, f"[{title}] ticket names no other restaurant or shared kitchen" + (f": {bad}" if bad else ""))
            if site.get("payWith"):
                check(re.search(r"^Pay: " + re.escape(meta["pay"]) + "$", msg, re.M) is not None, f"[{title}] ticket says how the customer pays")
            check("DW-" not in msg and "TB-" not in msg and "OS-" not in msg, f"[{title}] no internal codes")
        # each restaurant page: no kitchen talk anywhere, and its order sheet never offers another restaurant
        for bid in brands:
            await pg.goto(BASE + f"{bid}/index.html", wait_until="networkidle")
            await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); await pg.wait_for_timeout(1200)
            bad = talk(await pg.evaluate("document.body.innerText"))
            check(not bad, f"{bid} page says nothing about a shared kitchen" + (f": {bad}" if bad else ""))
            if not is_open.get(bid):
                continue
            await pg.evaluate("OrderApp.clear()")
            first = next(i for i in menus[bid]["items"] if i.get("kind") != "drink" and not i.get("soldOut"))
            await pg.evaluate("([b,i]) => OrderApp.addItem(b,i,{},1)", [bid, first["id"]])
            await pg.click(".bar__btn"); await pg.wait_for_timeout(400)
            sheet = await pg.evaluate("(document.querySelector('.oa-sheet__panel') || {}).innerText || ''")
            hrefs = await pg.evaluate("Array.from(document.querySelectorAll('.oa-sheet__panel a[href]')).map(a => a.getAttribute('href'))")
            away = [h for h in hrefs if not h.startswith(("#", "https://wa.me/"))]
            bad = others_in(sheet, bid) + talk(sheet)
            check(bool(sheet) and not bad and not away, f"{bid} order sheet offers and links no other restaurant" + (f": {bad + away}" if bad or away else ""))
            await pg.evaluate("OrderApp.clear()")
        # the home page: every restaurant listed, and every card opens the dish on its own restaurant's page
        await pg.goto(BASE + "index.html", wait_until="networkidle"); await pg.wait_for_timeout(500)
        listed = await pg.evaluate("Array.from(document.querySelectorAll('#oa-list .shop')).map(a => a.getAttribute('href'))")
        shown = [b for b in site["brands"] if b.get("status") != "hidden"]
        check(len(listed) == len(shown) and all(f"{b['id']}/" in h for b, h in zip(shown, listed)), f"home lists every restaurant ({len(listed)}/{len(shown)})")
        rail = await pg.evaluate("Array.from(document.querySelectorAll('#oa-rail a')).map(a => a.getAttribute('href'))")
        check(bool(rail) and all(re.search(r"^[a-z-]+/#d=\w+$", h) for h in rail), f"home dish cards open the dish on its restaurant's page ({len(rail)} cards)")
        check(await pg.evaluate("!document.querySelector('[data-quick], .bag, #oa-bar')"), "home has no shared bag: ordering happens on each restaurant's page")
        bad = talk(await pg.evaluate("document.body.innerText"))
        check(not bad, "home says nothing about a shared kitchen" + (f": {bad}" if bad else ""))
        if rail:
            await pg.goto(BASE + rail[0], wait_until="networkidle"); await pg.wait_for_timeout(400)
            check(await pg.evaluate("!!document.querySelector('.dish__name')"), f"tapping a home dish card opens it on {rail[0].split('/')[0]}'s page")
        # an order on one restaurant never shows up on another one
        await pg.goto(BASE + "dushi-wok/index.html", wait_until="networkidle")
        await pg.evaluate("OrderApp.addItem('dushi-wok','fr',{},1)")
        await pg.goto(BASE + "taco-brava/index.html", wait_until="networkidle")
        n = await pg.evaluate("OrderApp.count()")
        check(n == 0, f"an order on Dushi Wok doesn't carry over to Taco Brava (bag shows {n})")
        await pg.goto(BASE + "dushi-wok/index.html", wait_until="networkidle")
        check(await pg.evaluate("OrderApp.count()") == 1, "the Dushi Wok order is still there when the customer comes back")
        await pg.evaluate("OrderApp.clear()")
        # the chef app reads each ticket back: same lines, prices, totals and payment for the customer receipt
        await pg.goto(BASE + "ops/kitchen/index.html", wait_until="networkidle")
        for smp, (title, br, lines, meta) in zip(out, [x for x in SAMPLES if is_open.get(x[1])]):
            r = await pg.evaluate("t => window.__kitchen.receipt(window.__kitchen.parse(t))", smp["message"])
            ok = bool(r) and r["sub"] == smp["subtotal_cents"] and r["fee"] == smp["fee_cents"] and r["total"] == smp["total_cents"] \
                and sum(l["p"] for l in r["lines"]) == smp["subtotal_cents"] and r["pay"] == meta.get("pay", "")
            check(ok, f"[{title}] chef app receipt matches the order (lines, totals, payment)")
            ok = bool(r) and r.get("brands") == [names[br]] and r.get("biz") == site.get("name")
            check(ok, f"[{title}] the receipt is from {site.get('name')} for {names[br]} only" + ("" if ok else f": {r and (r.get('biz'), r.get('brands'))}"))
        # a shared dish link (restaurant/#d=<id>) opens that dish, for every restaurant's signature dish
        for bid in brands:
            sig = next((i for i in menus[bid]["items"] if i.get("style") == "signature"), None)
            if not sig:
                continue
            await pg.goto(BASE + f"{bid}/#d={sig['id']}", wait_until="networkidle")
            got = await pg.evaluate("(document.querySelector('.dish__name') || {}).textContent || ''")
            check(got == sig["name"], f"{bid}/#d={sig['id']} opens {sig['name']}" + ("" if got == sig["name"] else f": got {got!r}"))
        await pg.goto(BASE + "dushi-wok/index.html", wait_until="networkidle")
        # other languages: pages load cleanly, and the WhatsApp ticket stays in English for the kitchen
        en_msg = out[0]["message"]
        for code in ("pap", "nl", "es"):
            await pg.evaluate("c => localStorage.setItem('orderaruba.lang.v1', c)", code)
            for url in ["index.html"] + [f"{x}/index.html" for x in brands]:
                errs.clear()
                await pg.goto(BASE + url, wait_until="networkidle"); await pg.wait_for_timeout(300)
                check(not errs and await pg.evaluate("document.documentElement.lang") == code, f"[{code}] {url} loads in that language with no errors" + (f": {errs}" if errs else ""))
            await pg.goto(BASE + "dushi-wok/index.html", wait_until="networkidle")
            await pg.evaluate("OrderApp.clear()")
            title, br, lines, meta = SAMPLES[0]
            for (iid, opts, q) in lines:
                await pg.evaluate("([b,i,o,q]) => OrderApp.loadMenu(b).then(() => OrderApp.addItem(b,i,o,q))", [br, iid, opts, q])
            await pg.evaluate("m => OrderApp._set(m)", meta)
            msg = await pg.evaluate("OrderApp.buildMessage()")
            time_ok = re.search(r"^Time: (As soon as possible|(Tomorrow )?(Midnight|\d{1,2}(:\d\d)?\s(AM|PM)))$", msg, re.M) is not None
            norm = lambda t: re.sub(r"^Time: .*$", "Time:", re.sub(r"#\S+", "#", t), flags=re.M)
            check(time_ok and norm(msg) == norm(en_msg), f"[{code}] WhatsApp ticket is the same English text")
            await pg.evaluate("OrderApp.clear()")
        await pg.evaluate("localStorage.removeItem('orderaruba.lang.v1')")
        json.dump({"_about": "Real WhatsApp messages produced by shared/order-app.js. Regenerate with python3 qa/check_site.py.",
                   "samples": out}, open(os.path.join(ROOT, "qa/wa-samples.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        await b.close()
asyncio.run(main())
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
