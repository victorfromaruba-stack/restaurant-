"""Link preview cards (shared/og/<restaurant>.jpg, 1200x630) from the live menus and pictures.
Each card is one restaurant on its own: no shared name, nothing about the other restaurants.
Run from the repo folder: python3 build/og/make_og.py (it serves the repo itself, see qa/local_server.py).
Uses each menu.json's name, tagline, color, mark and hero, and the hours in shared/site.json."""
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
o, c = site["hours"]["mon"]
HOURS = f"{t12(o)}–{t12(c)}"

def ink(hex_):
    h = hex_.lstrip("#"); r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#0B1D3A" if (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 else "#FFFFFF"

HEAD = f"""<!doctype html><html><head><meta charset="utf-8"><base href="{BASE}">
<link rel="stylesheet" href="shared/order.css"><style>
html,body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#0B1D3A}}
.c{{position:relative;display:flex;width:1200px;height:630px}}
.ph{{flex:none;width:690px;height:630px;object-fit:cover}}
.side{{flex:1;display:flex;flex-direction:column;padding:44px 40px 36px}}
.mk{{width:96px;height:96px;border-radius:22px;object-fit:cover;box-shadow:0 8px 22px rgba(0,0,0,.22)}}
.nm{{margin:30px 0 0;font:900 92px/.88 var(--font);font-stretch:62%;text-transform:uppercase}}
.tg{{margin:16px 0 0;font:500 25px/1.3 var(--font)}}
.ft{{margin-top:auto;display:flex;justify-content:space-between;font:800 19px/1 var(--font);text-transform:uppercase;letter-spacing:.03em}}
</style></head><body>"""

def brand_html(b):
    m = menus[b]; col = m["color"]; fg = ink(col)
    return HEAD + f"""<div class="c"><img class="ph" src="{m['hero']}"><div class="side" style="background:{col};color:{fg}">
<img class="mk" src="{m['mark']}"><h1 class="nm">{m['name']}</h1><p class="tg">{m['tagline']}</p>
<div class="ft"><span>Delivery in Aruba</span><span>{HOURS}</span></div></div></div></body></html>"""

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto(BASE + "404.html")   # same origin as the fonts, or the browser blocks them
        for name, html in [(b, brand_html(b)) for b in ids]:
            await pg.set_content(html, wait_until="networkidle")
            await pg.evaluate("document.fonts.load('900 92px Archivo').then(() => document.fonts.ready)")
            out = os.path.join(ROOT, "shared/og", name + ".jpg")
            await pg.screenshot(path=out, type="jpeg", quality=84)
            print(out, os.path.getsize(out) // 1024, "KB")
        await br.close()
asyncio.run(main())
