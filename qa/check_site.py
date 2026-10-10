"""Site check: python3 qa/check_site.py from the repo folder. It serves the repo itself for the run
(qa/local_server.py), so there is no server to start first. QA_BASE=<url> checks another server instead.
Checks every menu image exists, every page loads with no errors, and builds the WhatsApp sample
messages in qa/wa-samples.json from the real ordering code, testing the owner's rules.
Pidi (site.json "name") is a delivery app, like Uber Eats: the home page lists the restaurants, and
customers must believe each one is its own business. Nothing may say or hint that they share a kitchen
or an owner. Restaurants marked "mix" in site.json go in one order with one delivery fee (the app's perk).
Pidi's locked rules are checked in every public file and on every rendered page: the old name never
appears, no closing time is shown (only "Late night from 10 PM"), and no "partner", "sister", "own
restaurant", "our restaurants" or "charged". It never calls the real order database."""
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
        if key == "hero" and m.get(key) is False:   # "hero": false = no dish picture on the home page, just the sign
            continue
        check(os.path.exists(os.path.join(ROOT, m[key])), f"{b} {key} file exists ({m[key]})")
    if m.get("video"):
        for k in ("src", "poster"):
            check(os.path.exists(os.path.join(ROOT, m["video"][k])), f"{b} cover video {k} exists ({m['video'][k]})")
        src = os.path.join(ROOT, m["video"]["src"])
        check(not os.path.exists(src) or os.path.getsize(src) <= 1.5 * 1024 * 1024, f"{b} cover video is under 1.5 MB")
    # section names are only ever shown in the visitor's language (Victor, 9 Oct 2026: no small translations beside them)
    check(all(set(sec) <= {"id", "title"} for sec in m["sections"]), f"{b} sections carry only id and title (no second-language names)")
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
    # a dish whose picture doesn't match its words ("hidePhoto") shows no picture anywhere: not as the home page
    # picture ("hero"), not as the restaurant's cover, not on a link card
    hidden = {i["img"]: i["id"] for i in m["items"] if i.get("hidePhoto")}
    cov = m.get("cover")
    check(m["hero"] not in hidden and not (isinstance(cov, str) and cov in hidden.values()),
          f"{b} hero and cover are never a hidden picture" + (f": {m['hero'] if m['hero'] in hidden else cov}" if m["hero"] in hidden or cov in hidden.values() else ""))
    if m.get("mainSection"):
        check(m["mainSection"] in secs, f"{b} mainSection is a real section")
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
check(site["deliveryFee"] == 500, "Delivery fee is ƒ5.00 (the fallback for a restaurant without its own fee)")
# site.json, the way the order database reads it (build contract, brief Appendix C10)
check(site.get("name") == "Pidi", f"the app is called Pidi in site.json (got {site.get('name')!r})")
check(site.get("minFood") == 2400, "food minimum is ƒ24 on the whole order (minFood 2400)")
check(isinstance(site.get("etaMin"), int) and isinstance(site.get("etaMax"), int) and 0 < site["etaMin"] < site["etaMax"] and "eta" not in site,
      f"delivery time is two numbers, etaMin and etaMax, with no text version ({site.get('etaMin')}–{site.get('etaMax')})")
check(all(isinstance(b.get("fee"), int) and b["fee"] > 0 for b in site["brands"]), "every restaurant has its own delivery fee in cents")
check(all(b["fee"] == 500 for b in site["brands"] if b["id"] in ("dushi-wok", "taco-brava", "smash-shack", "nonnas-night-in", "oranje-snack")),
      "the five restaurants each have a ƒ5 fee")
def keys_in(v):
    if isinstance(v, dict):
        return set(v) | {k for x in v.values() for k in keys_in(x)}
    return {k for x in v for k in keys_in(x)} if isinstance(v, list) else set()
check(not any("partner" in k.lower() for k in keys_in(site)), "no partner flag in site.json (a fee is just a number)")
lang = subprocess.run([sys.executable, os.path.join(ROOT, "build/lang_keys.py"), "--check"], capture_output=True, text=True)
seo = subprocess.run([sys.executable, os.path.join(ROOT, "build/seo.py"), "--check"], capture_output=True, text=True)
check(seo.returncode == 0, "Google listing data matches site.json and the menus (else run: python3 build/seo.py)" + ("" if seo.returncode == 0 else ": " + seo.stdout.strip()))
check(lang.returncode == 0, "every screen phrase has a Papiamento, Dutch and Spanish translation" + ("" if lang.returncode == 0 else ":\n" + lang.stdout[-1500:]))

# (case, page it runs on, lines as (restaurant, dish, options, qty), checkout details)
SAMPLES = [
  ("Dushi Wok, modifiers and a can", "dushi-wok", [("dushi-wok", "fr", {"leave": ["onion", "egg"]}, 2), ("dushi-wok", "ss", {"sauce": "on-the-side"}, 1), ("dushi-wok", "ck", {}, 1)],
   {"area": "Noord", "addr": "Palm Beach 12, blue gate", "name": "Ana", "note": "no peanuts please", "pay": "Cash"}),
  ("three restaurants in one order, all three cans", "taco-brava", [("dushi-wok", "ft", {}, 1), ("taco-brava", "bt", {}, 1), ("oranje-snack", "bb", {"dip": "mustard"}, 2),
     ("taco-brava", "ck", {}, 1), ("taco-brava", "cz", {}, 1), ("taco-brava", "sp", {}, 2)],
   {"area": "Oranjestad", "addr": "Caya G.F. Betico Croes 10", "name": "Ben", "note": "", "pay": "Bank transfer"}),
  ("burgers + Italian in one order", "smash-shack", [("smash-shack", "sc", {"leave": ["onion", "pickles"]}, 1), ("smash-shack", "fs", {}, 2), ("nonnas-night-in", "pa", {"heat": "extra-spicy"}, 1)],
   {"area": "Santa Cruz", "addr": "Near the church, green house", "name": "Carla", "note": "extra napkins", "pay": "Cash"}),
  ("Oranje Snack on its own, dip choice", "oranje-snack", [("oranje-snack", "bb", {"dip": "mustard"}, 2)],
   {"area": "Eagle Beach", "addr": "Hotel lobby, room 214", "name": "Eva", "note": "", "pay": "Bank transfer"}),
]
names = {b: menus[b]["name"] for b in brands}
is_open = {b["id"]: b.get("status", "open") == "open" for b in site["brands"]}
mix = [b["id"] for b in site["brands"] if b.get("mix")]
def runs(sample):   # every restaurant in it open, and all of them allowed in one order
    bs = {l[0] for l in sample[2]}
    return all(is_open.get(b) for b in bs) and (len(bs) == 1 or bs <= set(mix))
# words that say or hint the restaurants share a kitchen or an owner (Order Aruba itself is fine: it's the app)
KITCHEN_TALK = ("one kitchen", "shared kitchen", "same kitchen", "from our kitchen", "our other restaurant", "sister restaurant",
                "all five", "kitchen order")
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
# Comments in public files are public too (View Source): none may talk about a kitchen behind the restaurants, a
# ghost kitchen, or what customers should "believe". Found 9 Oct 2026 in order-app.js and sw.js.
COMMENT_TALK = re.compile(r"kitchen|ghost|believe", re.I)
def comments(path, text):
    if path.endswith(".json"):
        return [text]   # no comments in JSON: its "_help" notes are read the same way
    found = re.findall(r"/\*.*?\*/", text, re.S) + re.findall(r"<!--.*?-->", text, re.S)
    if path.endswith((".js", ".html")):
        found += re.findall(r"(?<![:\\\w\"'])//[^\n]*", text)
    return found
pub_code = pub + ["manifest.webmanifest"] + [f"{b}/style.css" for b in brands] + [f"{b}/manifest.webmanifest" for b in brands]
for f in pub_code:
    fp = os.path.join(ROOT, f)
    if not os.path.exists(fp):
        continue
    bad = sorted({w.lower() for c in comments(f, open(fp, encoding="utf-8").read()) for w in COMMENT_TALK.findall(c)})
    check(not bad, f"{f}: no comment or note talks about a kitchen behind it" + (f": {bad}" if bad else ""))
for b in brands:
    html = open(os.path.join(ROOT, b, "index.html"), encoding="utf-8").read()
    others = [x for x in brands if x != b and (x + "/" in html or names[x] in html)]
    check(not others and "parentOrganization" not in html, f"{b}/index.html (title, Google data) stands on its own" + (f": mentions {others}" if others else ""))
check(not os.path.exists(os.path.join(ROOT, "cart.html")), "no shared cart page: each restaurant is its own order")

# ---- Pidi's locked rules in every public file (brief "Locked rules" 1-3, 10 Oct 2026)
# Public: whatever GitHub Pages serves that a phone loads. Skipped: notes and tools that no customer page loads (.claude/,
# CLAUDE.md and the other Markdown notes, ops/ the chef app, driver/ the driver app, build/ and qa/ scripts).
SKIP_DIRS = {".git", ".github", ".claude", "ops", "driver", "build", "qa", "node_modules"}
def public_files(exts):
    found = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not (d == ROOT and x.startswith(".")))
        found += [os.path.relpath(os.path.join(d, f), ROOT) for f in sorted(files) if f.endswith(exts)]
    return found
OLD_NAME = re.compile(r"order\s*aruba|orderaruba", re.I)
# the old storage and cache names, read once so a phone's saved order moves to the new names (nobody loses a cart)
LEGACY = {"shared/order-app.js": ('"orderaruba.cart.v2"', '"orderaruba.last.v1"', '"orderaruba.lang.v1"'), "sw.js": ('"orderaruba-"',)}
CLOSING = re.compile(r"\b2(:00)?\s?AM\b|\b02:00\b|\buntil 2\b|\btill 2\b|\btot 2\b|\bhasta las 2\b", re.I)
BANNED = re.compile(r"\bpartner|\bown restaurant|\bour restaurants\b|\bsister|\bcharged\b", re.I)
def closing(text):
    return sorted({m.group(0) for m in CLOSING.finditer(text)})
def banned(text):
    return sorted({m.group(0).lower() for m in BANNED.finditer(text)})
def read(f):
    return open(os.path.join(ROOT, f), encoding="utf-8").read()
# 1. the old name, anywhere a phone can load it (pages, code, styles, menus, language files, manifests, Google data)
for f in public_files((".html", ".js", ".css", ".json", ".webmanifest", ".xml", ".txt", ".svg")):
    t = read(f)
    for legacy in LEGACY.get(f, ()):
        t = t.replace(legacy, "")
    hits = sorted({m.group(0) for m in OLD_NAME.finditer(t)})
    check(not hits, f"{f} never says the old name" + (f": {hits}" if hits else ""))
# 2. no "partner", "own restaurant", "our restaurants", "sister" or "charged" in a customer file (comments are public too)
for f in public_files((".html", ".js", ".css", ".json", ".webmanifest")):
    bad = banned(read(f))
    check(not bad, f"{f} has no partner/sister/own-restaurant/charged wording" + (f": {bad}" if bad else ""))
# 3. no closing time in screen text: every phrase the code shows (build/lang_keys.py), the language files, the menus,
#    site.json's words (its hours and lastOrder are logic, not text), the pages (titles, descriptions, Google data), manifests
sys.path.insert(0, os.path.join(ROOT, "build"))
import lang_keys
texts = [("order-app.js / pages: " + k, k) for k in lang_keys.keys()]
for code in ("pap", "nl", "es"):
    texts += [(f"shared/lang/{code}.json: {k}", v) for k, v in json.load(open(os.path.join(ROOT, "shared/lang", code + ".json"), encoding="utf-8")).items()]
def strings(v, where, skip=()):
    if isinstance(v, str):
        return [(where, v)]
    if isinstance(v, dict):
        return [x for k, y in v.items() if k not in skip for x in strings(y, where, skip)]
    return [x for y in v for x in strings(y, where, skip)] if isinstance(v, list) else []
texts += strings(site, "shared/site.json", skip=("hours", "lastOrder"))
texts += [x for b in brands for x in strings(menus[b], f"{b}/menu.json")]
texts += [(f, read(f)) for f in public_files((".html", ".webmanifest"))]
for where, t in texts:
    hit = closing(t)
    check(not hit, f"no closing time in {where[:70]}" + (f": {hit}" if hit else ""))

db_calls = []
async def no_database(ctx):
    """QA never reaches the real order database: every /rest/v1/ request is answered here (contexts block service
    workers, so page.route sees every request) and noted, and no real order can ever be created."""
    async def fake(route):
        db_calls.append(route.request.url.split("/rest/v1/")[-1])
        await route.fulfill(status=200, content_type="application/json", body="null")
    await ctx.route("**/rest/v1/**", fake)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
        await no_database(ctx)
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
            if not url.startswith("ops/"):
                txt = await pg.evaluate("document.body.innerText + ' ' + document.title")
                bad = closing(txt) + banned(txt) + sorted({m.group(0) for m in OLD_NAME.finditer(txt)})
                check(not bad, f"{url} on screen: no closing time, no old name, no partner/sister wording" + (f": {bad}" if bad else ""))
        out = []
        for title, br, lines, meta in [x for x in SAMPLES if runs(x)]:
            await pg.goto(BASE + br + "/index.html", wait_until="networkidle")
            await pg.evaluate("OrderApp.clear()")
            for (lb, iid, opts, q) in lines:
                await pg.evaluate("([b,i,o,q]) => OrderApp.loadMenu(b).then(() => OrderApp.addItem(b,i,o,q))", [lb, iid, opts, q])
            await pg.evaluate("m => OrderApp._set(m)", meta)
            msg = await pg.evaluate("OrderApp.buildMessage()")
            sub, fee, tot = await pg.evaluate("[OrderApp.subtotal(), OrderApp.fee(), OrderApp.total()]")
            inside = [b for b in brands if any(l[0] == b and l[1] not in ("ck", "cz", "sp") for l in lines)] or [lines[0][0]]
            out.append({"case": title, "message": msg, "subtotal_cents": sub, "fee_cents": fee, "total_cents": tot})
            low = msg.lower()
            check("flavour" not in low and "flavor" not in low, f"[{title}] never asks for a drink flavour")
            for cid, cname in (("ck", "Coca-Cola (can)"), ("cz", "Coca-Cola Zero (can)"), ("sp", "Sprite (can)")):
                if any(l[1] == cid for l in lines):
                    check(re.search(r"^\d+ × " + re.escape(cname) + r" — ƒ", msg, re.M) is not None, f"[{title}] {cname} is its own line")
            check(fee == 500, f"[{title}] delivery fee is ƒ5, once" + (f" for {len(inside)} restaurants" if len(inside) > 1 else ""))
            check(msg.count("Delivery ƒ") == 1 and "Pickup" not in msg, f"[{title}] fee line appears once, and nothing offers pickup")
            item_sum = sum(int(round(float(x) * 100)) for x in re.findall(r"^\d+ × .+ — ƒ(\d+\.\d\d)$", msg, re.M))
            check(item_sum == sub and tot == sub + fee, f"[{title}] line prices add up to the total")
            first = msg.split("\n")[0]
            want = (r"^\*Order\* #\d{4}-[A-Z0-9]{2} · %d restaurants$" % len(inside)) if len(inside) > 1 else (r"^\*" + re.escape(names[inside[0]]) + r" order\* #\d{4}-[A-Z0-9]{2}$")
            check(re.match(want, first) is not None, f"[{title}] header: {first}")
            check(all(("*" + names[b] + "*") in msg for b in inside) if len(inside) > 1 else True, f"[{title}] each restaurant has its own section on the ticket")
            bad = [n for b, n in names.items() if b not in inside and n in msg] + talk(msg)
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
            bad = [n for b, n in names.items() if b != bid and b not in mix and n in sheet] + (others_in(sheet, bid) if bid not in mix else []) + talk(sheet)
            check(bool(sheet) and not bad and not away, f"{bid} order sheet offers only what can share its order, and no kitchen talk" + (f": {bad + away}" if bad or away else ""))
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
        # the mix restaurants share one order: started on one, it's the same order on the next (two that are open now)
        pair = [b for b in mix if is_open.get(b)][:2]
        check(len(pair) == 2, f"two mix restaurants are open to test one order across them ({pair})")
        if len(pair) == 2:
            one, two = ([next(i["id"] for i in menus[x]["items"] if i.get("kind") != "drink" and not i.get("soldOut")) for x in pair])
            await pg.goto(BASE + pair[0] + "/index.html", wait_until="networkidle")
            await pg.evaluate("OrderApp.clear()"); await pg.evaluate("([b,i]) => OrderApp.addItem(b,i,{},1)", [pair[0], one])
            await pg.goto(BASE + pair[1] + "/index.html", wait_until="networkidle")
            await pg.evaluate("([b,i]) => OrderApp.loadMenu(b).then(() => OrderApp.addItem(b,i,{},1))", [pair[1], two])
            n, f = await pg.evaluate("[OrderApp.count(), OrderApp.fee()]")
            want = max(next(x["fee"] for x in site["brands"] if x["id"] == b) for b in pair)
            check(n == 2 and f == want, f"{names[pair[0]]} + {names[pair[1]]} end up in one order with one delivery fee, the higher of theirs (items {n}, fee {f}, want {want})")
            await pg.evaluate("OrderApp.clear()")
        # an order kept from earlier gets today's menu on the restaurant's own page: a dish sold out since then is
        # flagged and blocks Send, a new price is used (found 9 Oct 2026: only other restaurants' pages refreshed it)
        # (it runs on a copy of site.json with every restaurant open, so it doesn't depend on who is open tonight)
        if "dushi-wok" in brands and "taco-brava" in brands:
            ctx2 = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
            await no_database(ctx2)
            p2 = await ctx2.new_page()
            await p2.route("https://wa.me/**", lambda r: r.abort())
            all_open = json.loads(json.dumps(site))
            for x in all_open["brands"]: x["status"] = "open"
            await p2.route("**/shared/site.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(all_open)))
            await p2.goto(BASE + "dushi-wok/index.html", wait_until="networkidle")
            await p2.evaluate("OrderApp.clear()")
            await p2.evaluate("OrderApp.addItem('dushi-wok','lm',{},1); OrderApp.addItem('dushi-wok','pk',{},1); OrderApp._set({area:'Noord', addr:'Palm Beach 12', name:'Ana', pay:'Cash'})")
            dw = json.loads(json.dumps(menus["dushi-wok"]))
            for it in dw["items"]:
                if it["id"] == "lm": it["soldOut"] = True
                if it["id"] == "pk": it["price"] = 9999
            await p2.route("**/dushi-wok/menu.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(dw)))
            await p2.reload(wait_until="networkidle")
            lines = await p2.evaluate("OrderApp.state().lines.map(l => [l.id, l.p, !!l.soldOut])")
            check(["lm", 1650, True] in lines and ["pk", 9999, False] in lines, f"an order kept from earlier gets today's sold-out marks and prices on the same restaurant's page ({lines})")
            await p2.click(".bar__btn"); await p2.wait_for_timeout(400)
            warn = await p2.evaluate("(document.querySelector('.oa-sheet__panel') || {}).innerText || ''")
            ft = await p2.evaluate("!!document.querySelector('.line__d--warn')")
            check(ft and "Sold out today" in warn, "the order sheet says the sold-out dish must go")
            await p2.click(".oa-sheet [data-send]"); await p2.wait_for_timeout(700)
            sent = await p2.evaluate("OrderApp.state().sentAt")
            check(not sent, "Send is blocked while a sold-out dish is in the order")
            # the family deal holds lo mein: sold out with it, in the menu and when adding
            row_out = await p2.evaluate("!!document.querySelector('[data-b=\"dushi-wok\"][data-id=\"ft\"].is-out') && !document.querySelector('[data-b=\"dushi-wok\"][data-id=\"ft\"] .plus')")
            added = await p2.evaluate("!!OrderApp.addItem('dushi-wok','ft',{},1)")
            check(row_out and not added, "a family deal is sold out when a dish inside it is")
            await p2.evaluate("OrderApp.clear()")
            # "Order again" after an order from two restaurants shows both, on either restaurant's page
            await p2.unroute("**/dushi-wok/menu.json*")
            await p2.evaluate("localStorage.setItem('pidi.last.v1', JSON.stringify({at: Date.now(), lines: [{b:'dushi-wok', id:'fr', q:1, o:{}}, {b:'taco-brava', id:'bt', q:1, o:{}}]}))")
            for page in ("dushi-wok", "taco-brava"):
                await p2.goto(BASE + page + "/index.html", wait_until="networkidle"); await p2.wait_for_timeout(500)
                again = (await p2.evaluate("(document.querySelector('#oa-again:not([hidden])') || {}).innerText || ''")).replace("\xa0", " ")
                check("Chicken fried rice" in again and "Birria tacos" in again, f"Order again on {page} has the dishes from both restaurants" + ("" if "Birria" in again and "fried rice" in again else f": {again!r}"))
            await p2.evaluate("localStorage.removeItem('pidi.last.v1')")
            await ctx2.close()
        # the app was renamed on 10 Oct 2026: a phone with an order, an "Order again" or a language saved under the old
        # names keeps them (moved once to the new names, the old ones removed); a newer order is never overwritten
        ctx3 = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
        await no_database(ctx3)
        p3 = await ctx3.new_page()
        open_one = next((x for x in mix if is_open.get(x)), None)
        if open_one:
            dish = next(i for i in menus[open_one]["items"] if i.get("kind") != "drink" and not i.get("soldOut"))
            await p3.goto(BASE + open_one + "/index.html", wait_until="networkidle")
            await p3.evaluate("([b,i]) => { OrderApp.clear(); OrderApp.addItem(b,i,{},2); }", [open_one, dish["id"]])
            await p3.evaluate("""([b,i]) => { const cart = localStorage.getItem('pidi.cart.v1'); localStorage.clear();
                localStorage.setItem('orderaruba.cart.v2', cart); localStorage.setItem('orderaruba.lang.v1', 'nl');
                localStorage.setItem('orderaruba.last.v1', JSON.stringify({at: Date.now(), lines: [{b, id: i, q: 1, o: {}}]}));
                localStorage.setItem('last.' + b + '.v1', '{"at":1,"lines":[]}'); }""", [open_one, dish["id"]])
            await p3.reload(wait_until="networkidle"); await p3.wait_for_timeout(400)
            n, lang, left = await p3.evaluate("""() => [OrderApp.count(), document.documentElement.lang,
                Object.keys(localStorage).filter(k => /^orderaruba|^(order|last)\\./.test(k))]""")
            moved = await p3.evaluate("['pidi.cart.v1', 'pidi.lang.v1', 'pidi.last.v1', 'pidi.last.' + %s + '.v1'].map(k => localStorage.getItem(k) !== null)" % json.dumps(open_one))
            again = await p3.evaluate("(JSON.parse(localStorage.getItem('pidi.last.v1') || '{}').lines || []).map(l => l.id)")
            check(n == 2 and lang == "nl" and all(moved) and not left and again == [dish["id"]],
                  f"an order, Order again and the language saved under the old names move to the new ones (items {n}, lang {lang}, moved {moved}, old keys left {left})")
            await p3.evaluate("() => { localStorage.setItem('orderaruba.cart.v2', JSON.stringify({v: 2, lines: []})); }")
            await p3.reload(wait_until="networkidle")
            n2, old = await p3.evaluate("[OrderApp.count(), localStorage.getItem('orderaruba.cart.v2')]")
            check(n2 == 2 and old is None, f"an old saved order never overwrites a newer one (items {n2})")
            await p3.evaluate("OrderApp.clear()"); await p3.reload(wait_until="networkidle"); await p3.wait_for_timeout(400)
            shown = (await p3.evaluate("(document.querySelector('#oa-again:not([hidden])') || {}).innerText || ''")).replace("\xa0", " ")
            check(dish["name"] in shown, f"Order again saved under the old name shows on {open_one}" + ("" if dish["name"] in shown else f": {shown!r}"))
            await p3.evaluate("localStorage.clear()")
        await ctx3.close()
        # the chef app reads each ticket back: same lines, prices, totals and payment for the customer receipt
        await pg.goto(BASE + "ops/kitchen/index.html", wait_until="networkidle")
        for smp, (title, br, lines, meta) in zip(out, [x for x in SAMPLES if runs(x)]):
            r = await pg.evaluate("t => window.__kitchen.receipt(window.__kitchen.parse(t))", smp["message"])
            ok = bool(r) and r["sub"] == smp["subtotal_cents"] and r["fee"] == smp["fee_cents"] and r["total"] == smp["total_cents"] \
                and sum(l["p"] for l in r["lines"]) == smp["subtotal_cents"] and r["pay"] == meta.get("pay", "")
            check(ok, f"[{title}] chef app receipt matches the order (lines, totals, payment)")
            inside = [names[b] for b in brands if any(l[0] == b and l[1] not in ("ck", "cz", "sp") for l in lines)] or [names[lines[0][0]]]
            ok = bool(r) and r.get("brands") == inside and r.get("biz") == site.get("name")
            check(ok, f"[{title}] the receipt is from {site.get('name')} for {', '.join(inside)}" + ("" if ok else f": {r and (r.get('biz'), r.get('brands'))}"))
        # a shared dish link (restaurant/#d=<id>) opens that dish, for every restaurant's signature dish
        for bid in brands:
            sig = next((i for i in menus[bid]["items"] if i.get("style") == "signature"), None)
            if not sig:
                continue
            await pg.goto(BASE + f"{bid}/#d={sig['id']}", wait_until="networkidle")
            # (a count like "(3)" is kept on its word's line with a no-break space)
            got = (await pg.evaluate("(document.querySelector('.dish__name') || {}).textContent || ''")).replace("\xa0", " ")
            check(got == sig["name"], f"{bid}/#d={sig['id']} opens {sig['name']}" + ("" if got == sig["name"] else f": got {got!r}"))
        # other languages: pages load cleanly, and the WhatsApp ticket stays in English for the kitchen
        en_msg = out[0]["message"]
        first_run = [x for x in SAMPLES if runs(x)][0]
        await pg.goto(BASE + first_run[1] + "/index.html", wait_until="networkidle")
        for code in ("pap", "nl", "es"):
            await pg.evaluate("c => localStorage.setItem('pidi.lang.v1', c)", code)
            for url in ["index.html"] + [f"{x}/index.html" for x in brands]:
                errs.clear()
                await pg.goto(BASE + url, wait_until="networkidle"); await pg.wait_for_timeout(300)
                check(not errs and await pg.evaluate("document.documentElement.lang") == code, f"[{code}] {url} loads in that language with no errors" + (f": {errs}" if errs else ""))
                txt = await pg.evaluate("document.body.innerText + ' ' + document.title")
                bad = closing(txt) + banned(txt) + sorted({m.group(0) for m in OLD_NAME.finditer(txt)})
                check(not bad, f"[{code}] {url} on screen: no closing time, no old name, no partner/sister wording" + (f": {bad}" if bad else ""))
            title, br, lines, meta = first_run
            await pg.goto(BASE + br + "/index.html", wait_until="networkidle")
            await pg.evaluate("OrderApp.clear()")
            for (lb, iid, opts, q) in lines:
                await pg.evaluate("([b,i,o,q]) => OrderApp.loadMenu(b).then(() => OrderApp.addItem(b,i,o,q))", [lb, iid, opts, q])
            await pg.evaluate("m => OrderApp._set(m)", meta)
            msg = await pg.evaluate("OrderApp.buildMessage()")
            time_ok = re.search(r"^Time: (As soon as possible|(Tomorrow )?(Midnight|\d{1,2}(:\d\d)?\s(AM|PM)))$", msg, re.M) is not None
            norm = lambda t: re.sub(r"^Time: .*$", "Time:", re.sub(r"#\S+", "#", t), flags=re.M)
            check(time_ok and norm(msg) == norm(en_msg), f"[{code}] WhatsApp ticket is the same English text")
            await pg.evaluate("OrderApp.clear()")
        await pg.evaluate("localStorage.removeItem('pidi.lang.v1')")
        json.dump({"_about": "Real WhatsApp messages produced by shared/order-app.js. Regenerate with python3 qa/check_site.py.",
                   "samples": out}, open(os.path.join(ROOT, "qa/wa-samples.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        await b.close()
asyncio.run(main())
print(f"(order database: {len(db_calls)} request(s) answered by QA's fake, none reached the real one: {sorted(set(db_calls))})")
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
