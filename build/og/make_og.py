"""Link preview cards (shared/og/*.jpg, 1200x630) from the live menus and pictures: one per restaurant
(its signature dish, so the picture matches the tagline) and one for the app's home page (site.json "name",
with the Pidi wordmark from shared/brand/). Never anything about a shared kitchen, and never a closing time:
only when it opens ("Late night from 10 PM").
Run from the repo folder: python3 build/og/make_og.py (it serves the repo itself, see qa/local_server.py).
Uses each menu.json's logo, sign colours, tagline and hero, and the hours and areas in shared/site.json."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start
BASE = start()
site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
ids = [b["id"] for b in site["brands"] if b.get("status") != "hidden"]
menus = {b: json.load(open(os.path.join(ROOT, b, "menu.json"), encoding="utf-8")) for b in ids}

def t12(hhmm):
    h, m = map(int, hhmm.split(":")); ap = "PM" if h >= 12 else "AM"; h = h % 12 or 12
    return f"{h}{':%02d' % m if m else ''} {ap}"
NAME = site["name"]
OPENS = t12(site["hours"]["mon"][0])
HOURS = f"Late night from {OPENS}"
AREAS = f'{site["areas"][0]} to {site["areas"][-1]}' if len(site["areas"]) > 1 else "".join(site["areas"])

def lum(hex_):
    h = hex_.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255

HEAD = f"""<!doctype html><html><head><meta charset="utf-8"><base href="{BASE}">
<link rel="stylesheet" href="shared/order.css"><style>
html,body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#15130F}}
.c{{position:relative;display:flex;width:1200px;height:630px}}
.ph{{flex:none;width:660px;height:630px;object-fit:cover}}
.side{{flex:1;display:flex;flex-direction:column;padding:52px 46px 40px;box-shadow:inset 0 0 0 14px var(--g),inset 0 0 0 18px var(--line)}}
.wm{{display:block;width:auto;height:auto;max-width:100%;max-height:150px;object-fit:contain;object-position:left center;margin-top:18px}}
.tg{{margin:30px 0 0;font:600 34px/1.25 var(--font);text-wrap:balance}}
.solo{{padding:76px 96px 56px}}.solo .wm{{max-height:200px;margin-top:10px}}.solo .tg{{font-size:46px;margin-top:40px;max-width:900px}}
.ft{{margin-top:auto;display:flex;justify-content:space-between;font:600 21px/1 var(--font);opacity:.85}}
.hm{{display:grid;grid-template-columns:560px 1fr;width:1200px;height:630px;color:#F4EEE3}}
.hl{{display:flex;flex-direction:column;padding:48px 44px 44px 52px}}
.lg{{display:flex;align-items:center;gap:14px;font:800 30px/1 var(--font);letter-spacing:-.01em}}
.lg img{{display:block;width:auto;height:50px}}
.h1{{margin:56px 0 0;font:700 92px/1 var(--font);letter-spacing:-.02em}}
.sub{{margin:22px 0 0;font:500 29px/1.3 var(--font);color:#ADA698}}.sub b{{color:#F4EEE3}}
.sg{{margin-top:auto;align-self:flex-start;display:flex;align-items:center;gap:14px;padding:10px 16px;border:3px solid #FFC93C;border-radius:12px;color:#FFC93C;text-transform:uppercase;box-shadow:0 0 26px rgba(255,201,60,.3)}}
.sg b{{font:900 40px/.9 var(--font);font-stretch:62%;letter-spacing:.05em;text-shadow:0 0 8px rgba(255,201,60,.8)}}.sg span{{font:800 16px/1.15 var(--font);font-stretch:75%;letter-spacing:.08em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:10px;padding:10px 10px 10px 0}}
.grid img{{width:100%;height:100%;object-fit:cover;border-radius:6px}}
</style></head><body>"""

def brand_html(b):
    """The restaurant's own sign (its wordmark on its own ground, framed) beside its house dish, since the tagline
    is about that dish. A dish whose picture is hidden on the site ("hidePhoto": it doesn't match its words) isn't
    on the card either, and no other dish stands in for it: then the card is the sign alone."""
    m = menus[b]; sign = m.get("sign") or {}
    ground = sign.get("ground", m["color"]); line = sign.get("line", "transparent")
    fg = "#15130F" if lum(ground) > 0.5 else "#F4EEE3"
    sig = next((i for i in m["items"] if i.get("style") == "signature"), None)   # the tagline is about this dish
    pic = sig["img"] if sig and not sig.get("hidePhoto") else ""
    photo = f'<img class="ph" src="{pic}">' if pic else ""
    return HEAD + f"""<div class="c">{photo}<div class="side{'' if pic else ' solo'}" style="--g:{ground};--line:{line};background:{ground};color:{fg}">
<img class="wm" src="{m['logo']}" alt=""><p class="tg">{m['tagline']}</p>
<div class="ft"><span>{NAME}</span><span>{HOURS}</span></div></div></div></body></html>"""

def home_html():
    hidden = {i["img"] for m in menus.values() for i in m["items"] if i.get("hidePhoto")}
    # "hero": false = that restaurant has no true picture of the dish its line is about yet: no panel for it
    pics = [menus[b]["hero"] for b in ids if menus[b].get("hero") and menus[b]["hero"] not in hidden][:4]
    return HEAD + f"""<div class="hm"><div class="hl"><div class="lg"><img src="shared/brand/wordmark.svg" alt="{NAME}"></div>
<div class="h1">Bon nochi.</div><p class="sub">Late-night food, delivered.<br><b>{AREAS}.</b></p>
<div class="sg"><b>Open</b><span>Late night<br>from {OPENS}</span></div></div>
<div class="grid">{''.join(f'<img src="{p}">' for p in pics)}</div></div></body></html>"""

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto(BASE + "404.html")   # same origin as the fonts, or the browser blocks them
        for name, html in [("home", home_html())] + [(b, brand_html(b)) for b in ids]:
            await pg.set_content(html, wait_until="networkidle")
            await pg.evaluate("document.fonts.load('900 92px Archivo').then(() => document.fonts.ready)")
            out = os.path.join(ROOT, "shared/og", name + ".jpg")
            await pg.screenshot(path=out, type="jpeg", quality=84)
            print(out, os.path.getsize(out) // 1024, "KB")
        await br.close()
asyncio.run(main())
