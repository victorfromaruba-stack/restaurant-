#!/usr/bin/env python3
"""Screenshots of a page the way people actually see it: on a phone first.

    python3 shoot.py site/                          # a local folder: served for the run, index.html at 390px and 1280px
    python3 shoot.py site/ --pages index.html,menu/ # several pages
    python3 shoot.py https://example.com            # a live page
    python3 shoot.py site/ --out /tmp/before        # keep a set to compare with an "after" set
    python3 shoot.py site/ --widths 320,390 --dark  # small phones, dark mode

Scrolls each page to the bottom first so lazy pictures load (an unscrolled full-page shot
shows empty boxes that aren't real). Writes <page>-<width>-top.png (the first screen, the
only one most people see) and <page>-<width>-full.png, then prints what it can measure:
broken pictures, sideways scrolling, the same picture twice on the first screen.
Needs Python Playwright (pip install playwright, then a Chromium it can find).
"""
import argparse
import asyncio
import functools
import http.server
import re
import threading
from pathlib import Path

MEASURE = """() => {
  const vh = innerHeight, imgs = [...document.images].filter(i => i.offsetParent !== null);
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'));
  const first = imgs.filter(i => { const r = i.getBoundingClientRect(); return r.top < vh && r.bottom > 0 && r.width > 60; })
                    .map(i => (i.currentSrc || i.src).split('/').pop().split('?')[0]);
  const dup = first.filter((s, n) => first.indexOf(s) !== n);
  return { broken, dup: [...new Set(dup)], sideways: document.documentElement.scrollWidth > innerWidth + 1 };
}"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(folder):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(folder)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}/"


async def scroll_through(page):
    h = await page.evaluate("document.documentElement.scrollHeight")
    for y in range(0, min(h, 30000), 500):
        await page.evaluate(f"scrollTo(0, {y})")
        await page.wait_for_timeout(100)
    await page.evaluate("scrollTo(0, 0)")
    await page.wait_for_timeout(400)


async def main(a):
    from playwright.async_api import async_playwright
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    base = a.target if re.match(r"https?://", a.target) else serve(Path(a.target).resolve())
    if not base.endswith("/") and not re.search(r"\.\w+$", base):
        base += "/"
    pages = [p.strip() for p in a.pages.split(",")] if a.pages else [""]
    notes = []
    async with async_playwright() as p:
        br = await p.chromium.launch()
        for w in [int(x) for x in a.widths.split(",")]:
            ctx = await br.new_context(viewport={"width": w, "height": 844 if w < 700 else 900}, device_scale_factor=2,
                                       color_scheme="dark" if a.dark else "light")
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for pg in pages:
                name = (re.sub(r"[^\w]+", "-", pg).strip("-") or "home")[:40]
                await page.goto(base + pg if pg else base, wait_until="load")
                await page.wait_for_timeout(700)
                m = await page.evaluate(MEASURE)
                await page.screenshot(path=str(out / f"{name}-{w}-top.png"))
                await scroll_through(page)
                await page.screenshot(path=str(out / f"{name}-{w}-full.png"), full_page=True)
                m2 = await page.evaluate(MEASURE)
                if m2["broken"]:
                    notes.append(f"{name} at {w}px: broken pictures {m2['broken'][:5]}")
                if m["dup"]:
                    notes.append(f"{name} at {w}px: the same picture twice on the first screen: {m['dup']}")
                if m2["sideways"]:
                    notes.append(f"{name} at {w}px: the page scrolls sideways")
            if errors:
                notes.append(f"script errors at {w}px: {errors[:3]}")
            await ctx.close()
        await br.close()
    print(f"Screenshots in {out}/")
    for n in notes:
        print("  " + n)
    if not notes:
        print("  nothing measurable wrong. Now look at every -top.png as the person it's for would.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="a local folder or a URL")
    ap.add_argument("--pages", default="", help="comma-separated paths under the target, e.g. index.html,menu/")
    ap.add_argument("--widths", default="390,1280")
    ap.add_argument("--out", default="/tmp/slop-shots")
    ap.add_argument("--dark", action="store_true")
    asyncio.run(main(ap.parse_args()))
