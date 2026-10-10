"""Pidi's icons and wordmark for the home page, made from the brand files in driver/brand/ (the driver app uses
the same "Pi" mark), so no customer page ever loads anything from /driver/:
  shared/icons/app-192.png, app-512.png   home screen icon (manifest.webmanifest): the blue rounded square
  shared/icons/app-maskable-512.png       the same mark full-bleed, for Android's own icon shapes
  shared/icons/app-180.png                iPhone home screen icon (apple-touch-icon)
  shared/icons/favicon.svg, favicon-32.png  browser tab
  shared/brand/wordmark.svg               the name in the top bar, trimmed to its ink so it lines up with the text
Restaurant pages keep their own icons and manifests (<restaurant>/manifest.webmanifest): someone who saves
Taco Brava to their home screen gets Taco Brava. No sparkles, no stars.
    python3 build/icons/make_icon.py"""
import asyncio, os, re, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "qa"))
from local_server import start
from playwright.async_api import async_playwright
BRAND = os.path.join(ROOT, "driver/brand")
ICONS = os.path.join(ROOT, "shared/icons")
BASE = start()


def svg(name):
    return open(os.path.join(BRAND, name), encoding="utf-8").read()


async def main():
    os.makedirs(os.path.join(ROOT, "shared/brand"), exist_ok=True)
    for src, dst in (("favicon.svg", "favicon.svg"), ("favicon-32.png", "favicon-32.png"), ("apple-touch-icon.png", "app-180.png")):
        shutil.copyfile(os.path.join(BRAND, src), os.path.join(ICONS, dst))
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": 512, "height": 512})
        await pg.goto(BASE + "404.html")
        # the blue rounded square (the favicon drawing) at home-screen sizes, on a transparent ground
        for size in (192, 512):
            await pg.set_viewport_size({"width": size, "height": size})
            await pg.set_content('<body style="margin:0;background:transparent">' +
                                 re.sub(r'width="[\d.]+" height="[\d.]+"', f'width="{size}" height="{size}"', svg("favicon.svg"), count=1) + "</body>")
            await pg.screenshot(path=os.path.join(ICONS, f"app-{size}.png"), omit_background=True)
        # maskable: blue to every edge, the mark inside Android's safe zone
        await pg.set_viewport_size({"width": 512, "height": 512})
        layers = "".join('<div style="position:absolute;inset:0">' + re.sub(r'width="[\d.]+" height="[\d.]+"', 'width="512" height="512"', svg(n), count=1) + "</div>"
                         for n in ("android-background.svg", "android-foreground.svg"))
        await pg.set_content('<body style="margin:0;position:relative;width:512px;height:512px">' + layers + "</body>")
        await pg.screenshot(path=os.path.join(ICONS, "app-maskable-512.png"))
        # the wordmark, its viewBox trimmed to the ink (the source has room around the letters)
        mark = svg("wordmark.svg")
        await pg.set_content('<body style="margin:0">' + mark + "</body>")
        x, y, w, h = await pg.evaluate("(() => { const b = document.querySelector('svg').getBBox(); return [b.x, b.y, b.width, b.height]; })()")
        box = " ".join("%g" % round(v, 2) for v in (x, y, w, h))
        mark = re.sub(r'width="[\d.]+" height="[\d.]+" viewBox="[^"]+"', 'width="%g" height="%g" viewBox="%s"' % (round(w, 2), round(h, 2), box), mark, count=1)
        open(os.path.join(ROOT, "shared/brand/wordmark.svg"), "w", encoding="utf-8").write(mark)
        await br.close()
    for f in sorted(os.listdir(ICONS)) + ["../brand/wordmark.svg"]:
        print(os.path.normpath(os.path.join("shared/icons", f)), os.path.getsize(os.path.join(ICONS, f)) // 1024, "KB")
asyncio.run(main())
