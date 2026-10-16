"""App icon: the app's name (site.json "name", now PIDI) in a neon frame like the OPEN sign on the home page.
No sparkle star anywhere (it reads as an AI-product icon), and not the blue "Pi" tile from the Pidi drafts: that was
the darker look Victor turned down on 15 Oct 2026, and its blue and peach clash with the night blue and the sign.
Serves the repo itself for the Archivo font (qa/local_server.py).   python3 build/icons/make_icon.py
  shared/icons/app-192.png, app-512.png   home screen icon (manifest.webmanifest, the home page's tab icon)
  shared/icons/app-maskable-512.png       the same sign smaller, inside Android's round safe zone
  shared/icons/app-180.png                iPhone home screen icon (apple-touch-icon)
Restaurant pages keep their own icons and manifests (<restaurant>/manifest.webmanifest)."""
import asyncio, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start
from playwright.async_api import async_playwright
BASE = start()
NAME = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))["name"].upper()


def page(scale):
    # scale: how much of the square the sign may take (1 = the home screen icon, smaller for Android's round masks)
    return """<!doctype html><html><head><style>
@font-face{font-family:Archivo;src:url(%sshared/fonts/archivo.woff2) format("woff2");font-weight:100 900;font-stretch:62%% 125%%}
html,body{margin:0;width:512px;height:512px;background:#15130F;display:grid;place-items:center;overflow:hidden}
.sg{transform:scale(%s);box-sizing:border-box;padding:4px 30px 0;height:228px;border:13px solid #FFC93C;border-radius:30px;display:grid;place-items:center;
 box-shadow:0 0 46px rgba(255,201,60,.38),inset 0 0 30px rgba(255,201,60,.16)}
b{font:900 172px/1 Archivo;font-stretch:62%%;letter-spacing:.03em;color:#FFC93C;margin-top:6px;white-space:nowrap;
 text-shadow:0 0 12px rgba(255,201,60,.75),0 0 40px rgba(255,201,60,.4)}
</style></head><body><div class="sg"><b>%s</b></div></body></html>""" % (BASE, scale, NAME)


async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        for size, scale, name in ((512, 1, "app-512"), (192, 1, "app-192"), (180, 1, "app-180"), (512, .8, "app-maskable-512")):
            pg = await br.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=size / 512)
            await pg.goto(BASE + "index.html")
            await pg.set_content(page(scale), wait_until="networkidle")
            await pg.evaluate("document.fonts.load('900 172px Archivo').then(() => document.fonts.ready)")
            w = await pg.evaluate("document.querySelector('.sg').getBoundingClientRect().width")
            if w > 470:
                sys.exit(f"the sign is {w:.0f}px wide: too wide for the icon, make the letters smaller")
            await pg.screenshot(path=os.path.join(ROOT, "shared/icons", name + ".png"))
            await pg.close()
        await br.close()
    for f in sorted(os.listdir(os.path.join(ROOT, "shared/icons"))):
        print("shared/icons/" + f, os.path.getsize(os.path.join(ROOT, "shared/icons", f)) // 1024, "KB")
asyncio.run(main())
