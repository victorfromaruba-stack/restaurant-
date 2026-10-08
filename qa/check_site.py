"""Site check: run with the local server on :8462.
  cd brand-hub && python3 -m http.server 8462 --bind 127.0.0.1 &   then   python3 qa/check_site.py
Checks every menu image exists, every page loads with no errors, and builds the WhatsApp sample
messages in qa/wa-samples.json from the real ordering code, testing the owner's rules."""
import asyncio, json, os, re, subprocess, sys
from playwright.async_api import async_playwright
from PIL import Image, ImageChops, ImageStat
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8462/")
fails = []
def square_sample(path):
    im = Image.open(path).convert("L"); s = min(im.size); l, t = (im.width - s) // 2, (im.height - s) // 2
    return im.crop((l, t, l + s, t + s)).resize((24, 24), Image.LANCZOS)
def thumb_ok(img):
    d, f = os.path.split(os.path.join(ROOT, img)); th = os.path.join(d, "thumbs", os.path.splitext(f)[0] + ".webp")
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
tb = {i["id"]: i for i in menus["taco-brava"]["items"]}
check(tb["bt"]["price"] == 2700, "Birria tacos stay at ƒ27.00")
check(site["deliveryFee"] == 500, "Delivery fee is ƒ5.00")
lang = subprocess.run([sys.executable, os.path.join(ROOT, "build/lang_keys.py"), "--check"], capture_output=True, text=True)
seo = subprocess.run([sys.executable, os.path.join(ROOT, "build/seo.py"), "--check"], capture_output=True, text=True)
check(seo.returncode == 0, "Google listing data matches site.json and the menus (else run: python3 build/seo.py)" + ("" if seo.returncode == 0 else ": " + seo.stdout.strip()))
check(lang.returncode == 0, "every screen phrase has a Papiamento, Dutch and Spanish translation" + ("" if lang.returncode == 0 else ":\n" + lang.stdout[-1500:]))

SAMPLES = [
  ("single brand, delivery, modifiers", [("dushi-wok", "fr", {"leave": ["onion", "egg"]}, 2), ("dushi-wok", "ss", {"sauce": "on-the-side"}, 1), ("dushi-wok", "ck", {}, 1)],
   {"mode": "delivery", "area": "Noord", "addr": "Palm Beach 12, blue gate", "name": "Ana", "note": "no peanuts please"}),
  ("three restaurants, delivery, all three cans", [("dushi-wok", "ft", {}, 1), ("taco-brava", "bt", {}, 1), ("oranje-snack", "bb", {"dip": "mustard"}, 2),
     ("taco-brava", "ck", {}, 1), ("taco-brava", "cz", {}, 1), ("taco-brava", "sp", {}, 2)],
   {"mode": "delivery", "area": "Oranjestad", "addr": "Caya G.F. Betico Croes 10", "name": "Ben", "note": ""}),
  ("pickup, burgers + Italian", [("smash-shack", "sc", {"leave": ["onion", "pickles"]}, 1), ("smash-shack", "fs", {}, 2), ("nonnas-night-in", "pa", {"heat": "extra-spicy"}, 1)],
   {"mode": "pickup", "area": "", "addr": "", "name": "Carla", "note": "extra napkins"}),
]

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
        for url in ["index.html", "cart.html", "ops/kitchen/index.html"] + [f"{x}/index.html" for x in brands]:
            errs.clear()
            await pg.goto(BASE + url, wait_until="networkidle")
            h = await pg.evaluate("document.body.scrollHeight")
            for y in range(0, h, 700):
                await pg.evaluate(f"window.scrollTo(0,{y})"); await pg.wait_for_timeout(40)
            await pg.wait_for_timeout(300)
            broken = await pg.evaluate("Array.from(document.images).filter(i => i.complete && i.naturalWidth === 0).map(i => i.src)")
            check(not errs and not broken, f"{url} loads with no errors or broken images" + (f": {errs + broken}" if errs or broken else ""))
        out = []
        await pg.goto(BASE + "index.html", wait_until="networkidle")
        for title, lines, meta in SAMPLES:
            await pg.evaluate("OrderAruba.clear()")
            for (br, iid, opts, q) in lines:
                await pg.evaluate("([b,i,o,q]) => OrderAruba.loadMenu(b).then(() => OrderAruba.addItem(b,i,o,q))", [br, iid, opts, q])
            await pg.evaluate("m => OrderAruba._set(m)", meta)
            msg = await pg.evaluate("OrderAruba.buildMessage()")
            sub, fee, tot = await pg.evaluate("[OrderAruba.subtotal(), OrderAruba.fee(), OrderAruba.total()]")
            out.append({"case": title, "message": msg, "subtotal_cents": sub, "fee_cents": fee, "total_cents": tot})
            low = msg.lower()
            check("flavour" not in low and "flavor" not in low, f"[{title}] never asks for a drink flavour")
            for cid, cname in (("ck", "Coca-Cola (can)"), ("cz", "Coca-Cola Zero (can)"), ("sp", "Sprite (can)")):
                if any(l[1] == cid for l in lines):
                    check(re.search(r"^\d+ × " + re.escape(cname) + r" — ƒ", msg, re.M) is not None, f"[{title}] {cname} is its own line")
            check(fee == (500 if meta["mode"] == "delivery" else 0), f"[{title}] delivery fee is {'ƒ5 once' if meta['mode']=='delivery' else 'free for pickup'}")
            check(msg.count("Delivery ƒ") == (1 if meta["mode"] == "delivery" else 0), f"[{title}] fee line appears once")
            item_sum = sum(int(round(float(x) * 100)) for x in re.findall(r"^\d+ × .+ — ƒ(\d+\.\d\d)$", msg, re.M))
            check(item_sum == sub and tot == sub + fee, f"[{title}] line prices add up to the total")
            first = msg.split("\n")[0]
            nb = len({l[0] for l in lines})
            check(first.startswith("*Kitchen order*") if nb > 1 else first.endswith(re.sub(r"^.*?(#\d+)$", r"\1", first)) and "order*" in first, f"[{title}] header names the restaurant / kitchen order")
            check("DW-" not in msg and "TB-" not in msg and "OS-" not in msg, f"[{title}] no internal codes")
        await pg.evaluate("OrderAruba.clear()")
        # other languages: pages load cleanly, and the WhatsApp ticket stays in English for the kitchen
        en_msg = out[0]["message"]
        for code in ("pap", "nl", "es"):
            await pg.evaluate("c => localStorage.setItem('orderaruba.lang.v1', c)", code)
            for url in ["index.html", "dushi-wok/index.html", "cart.html"]:
                errs.clear()
                await pg.goto(BASE + url, wait_until="networkidle"); await pg.wait_for_timeout(300)
                check(not errs and await pg.evaluate("document.documentElement.lang") == code, f"[{code}] {url} loads in that language with no errors" + (f": {errs}" if errs else ""))
            await pg.evaluate("OrderAruba.clear()")
            title, lines, meta = SAMPLES[0]
            for (br, iid, opts, q) in lines:
                await pg.evaluate("([b,i,o,q]) => OrderAruba.loadMenu(b).then(() => OrderAruba.addItem(b,i,o,q))", [br, iid, opts, q])
            await pg.evaluate("m => OrderAruba._set(m)", meta)
            msg = await pg.evaluate("OrderAruba.buildMessage()")
            time_ok = re.search(r"^Time: (As soon as possible|(Tomorrow )?(Midnight|\d{1,2}(:\d\d)?\s(AM|PM)))$", msg, re.M) is not None
            norm = lambda t: re.sub(r"^Time: .*$", "Time:", re.sub(r"#\S+", "#", t), flags=re.M)
            check(time_ok and norm(msg) == norm(en_msg), f"[{code}] WhatsApp ticket is the same English text")
            await pg.evaluate("OrderAruba.clear()")
        await pg.evaluate("localStorage.removeItem('orderaruba.lang.v1')")
        json.dump({"_about": "Real WhatsApp messages produced by shared/order-app.js. Regenerate with python3 qa/check_site.py.",
                   "samples": out}, open(os.path.join(ROOT, "qa/wa-samples.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        await b.close()
asyncio.run(main())
print(f"\n{len(fails)} problem(s)")
sys.exit(1 if fails else 0)
