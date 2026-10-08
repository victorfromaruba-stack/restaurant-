"""Link preview cards (shared/og/*.jpg, 1200x630) from the live menus and pictures.
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
FEE = "ƒ%g" % (site["deliveryFee"] / 100)

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
.ft span:first-child::before{{content:"\\2726  "}}
.hm{{display:grid;grid-template-columns:560px 1fr;width:1200px;height:630px}}
.hl{{display:flex;flex-direction:column;padding:48px 44px 44px 52px;color:#FFF4DF}}
.lg{{font:900 24px/1 var(--font);font-stretch:70%;text-transform:uppercase;color:#FFF4DF}}.lg b{{color:#FFC93C}}
.h1{{margin:44px 0 0;font:900 150px/.84 var(--font);font-stretch:62%;text-transform:uppercase}}
.sub{{margin:26px 0 0;font:500 29px/1.3 var(--font);color:#A9B6CC}}.sub b{{color:#FFF4DF}}
.sg{{margin-top:auto;align-self:flex-start;display:flex;align-items:center;gap:14px;padding:10px 16px;border:3px solid #FFC93C;border-radius:12px;color:#FFC93C;text-transform:uppercase;box-shadow:0 0 26px rgba(255,201,60,.3)}}
.sg b{{font:900 40px/.9 var(--font);font-stretch:62%;letter-spacing:.05em;text-shadow:0 0 8px rgba(255,201,60,.8)}}.sg span{{font:800 16px/1.15 var(--font);font-stretch:75%;letter-spacing:.08em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:10px;padding:10px 10px 10px 0}}
.grid img{{width:100%;height:100%;object-fit:cover;border-radius:14px}}
</style></head><body>"""

def brand_html(b):
    m = menus[b]; col = m["color"]; fg = ink(col)
    return HEAD + f"""<div class="c"><img class="ph" src="{m['hero']}"><div class="side" style="background:{col};color:{fg}">
<img class="mk" src="{m['mark']}"><h1 class="nm">{m['name']}</h1><p class="tg">{m['tagline']}</p>
<div class="ft"><span>Order Aruba</span><span>{HOURS}</span></div></div></div></body></html>"""

def home_html():
    pics = [menus[b]["hero"] for b in ids[:4]]
    return HEAD + f"""<div class="hm"><div class="hl"><div class="lg">Order Aruba</div>
<div class="h1">Bon<br>nochi.</div><p class="sub">Mix dishes from all five restaurants.<br><b>You pay {FEE} delivery once.</b></p>
<div class="sg"><b>Open</b><span>{t12(o)}<br>to {t12(c)}</span></div></div>
<div class="grid">{''.join(f'<img src="{p}">' for p in pics)}</div></div></body></html>"""

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto(BASE + "index.html")   # same origin as the fonts, or the browser blocks them
        for name, html in [("home", home_html())] + [(b, brand_html(b)) for b in ids]:
            await pg.set_content(html, wait_until="networkidle")
            await pg.evaluate("document.fonts.load('900 92px Archivo').then(() => document.fonts.ready)")
            out = os.path.join(ROOT, "shared/og", name + ".jpg")
            await pg.screenshot(path=out, type="jpeg", quality=84)
            print(out, os.path.getsize(out) // 1024, "KB")
        await br.close()
asyncio.run(main())
