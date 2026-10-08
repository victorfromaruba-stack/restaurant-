"""App icon: "OA" in a neon frame like the OPEN sign on the home page (replaced the sparkle star, which reads as an AI-product icon).
Needs the local server on :8462 for the Archivo font.   python3 build/icons/make_icon.py"""
import asyncio, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.async_api import async_playwright
BASE = "http://127.0.0.1:8462/"
HTML = """<!doctype html><html><head><style>
@font-face{font-family:Archivo;src:url(%sshared/fonts/archivo.woff2) format("woff2");font-weight:100 900;font-stretch:62%% 125%%}
html,body{margin:0;width:512px;height:512px;background:#0B1D3A;display:grid;place-items:center;overflow:hidden}
.sg{width:330px;height:228px;box-sizing:border-box;border:13px solid #FFC93C;border-radius:30px;display:grid;place-items:center;
 box-shadow:0 0 46px rgba(255,201,60,.38),inset 0 0 30px rgba(255,201,60,.16)}
b{font:900 196px/1 Archivo;font-stretch:62%%;letter-spacing:.04em;color:#FFC93C;margin-top:6px;
 text-shadow:0 0 12px rgba(255,201,60,.75),0 0 40px rgba(255,201,60,.4)}
</style></head><body><div class="sg"><b>OA</b></div></body></html>""" % BASE
async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        for size in (512, 192, 180):
            pg = await br.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=size / 512)
            await pg.goto(BASE + "index.html")
            await pg.set_content(HTML, wait_until="networkidle")
            await pg.evaluate("document.fonts.load('900 196px Archivo').then(() => document.fonts.ready)")
            await pg.screenshot(path=os.path.join(ROOT, "shared/icons", f"app-{size}.png"))
            await pg.close()
        await br.close()
asyncio.run(main())
