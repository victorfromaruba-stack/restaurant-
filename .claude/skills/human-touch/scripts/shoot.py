#!/usr/bin/env python3
"""Phone screenshots of the customer site, the way a hungry customer sees it at 11 PM.

    python3 .claude/skills/human-touch/scripts/shoot.py                   # -> /tmp/order-aruba-shots/
    python3 .claude/skills/human-touch/scripts/shoot.py --out before/     # keep a set to compare with later
    python3 .claude/skills/human-touch/scripts/shoot.py --closed          # 2 PM: closed, pre-orders
    python3 .claude/skills/human-touch/scripts/shoot.py --width 320       # the smallest phones

Starts its own local server if nothing answers on --base. Clock is pinned to an open
night (11:10 PM Aruba) unless --closed. Scrolls every page so lazy pictures load before
the full-page shot (an unscrolled full-page shot shows empty boxes that aren't real).

Writes <page>-top.png (first screen) and <page>-full.png, plus a dish sheet and a cart
with two dishes in it. Prints what it can measure: broken pictures, sideways scroll, the
same picture twice on the first screen. Then look at every -top.png yourself.
"""
import argparse
import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[4]
OPEN, CLOSED = "2026-10-09T03:10:00Z", "2026-10-08T18:00:00Z"   # 11:10 PM and 2:00 PM in Aruba (UTC-4)

CLOCK = """(() => { const T = new Date('%s').getTime(), D = Date, s = D.now();
  class F extends D { constructor(...a) { super(...(a.length ? a : [T + (D.now() - s)])); } static now() { return T + (D.now() - s); } }
  window.Date = F; })()"""

MEASURE = """() => {
  const vh = innerHeight, imgs = [...document.images].filter(i => i.offsetParent !== null);
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'));
  const first = imgs.filter(i => { const r = i.getBoundingClientRect(); return r.top < vh && r.bottom > 0 && r.width > 60; })
                    .map(i => (i.currentSrc || i.src).split('/').pop());
  const dup = first.filter((s, n) => first.indexOf(s) !== n);
  return { broken, dup: [...new Set(dup)], sideways: document.documentElement.scrollWidth > innerWidth + 1 };
}"""


def free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


async def scroll_through(page):
    h = await page.evaluate("document.documentElement.scrollHeight")
    for y in range(0, h, 500):
        await page.evaluate(f"scrollTo(0, {y})")
        await page.wait_for_timeout(120)
    await page.evaluate("scrollTo(0, 0)")
    await page.wait_for_timeout(500)


async def main(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    server = None
    port = int(a.base.rstrip("/").rsplit(":", 1)[-1].split("/")[0])
    if free(port):
        server = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    site = json.loads((ROOT / "shared/site.json").read_text(encoding="utf-8"))
    pages = [("home", "")] + [(b["id"], b["id"] + "/") for b in site["brands"] if b.get("status") != "hidden"]
    notes = []
    try:
        async with async_playwright() as p:
            br = await p.chromium.launch()
            ctx = await br.new_context(viewport={"width": a.width, "height": 844 if a.width > 360 else 640},
                                       device_scale_factor=2, service_workers="block", locale=a.lang)
            await ctx.add_init_script(CLOCK % (CLOSED if a.closed else OPEN))
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for name, url in pages:
                await page.goto(a.base + url)
                await page.wait_for_timeout(900)
                m = await page.evaluate(MEASURE)
                await page.screenshot(path=str(out / f"{name}-top.png"))
                await scroll_through(page)
                await page.screenshot(path=str(out / f"{name}-full.png"), full_page=True)
                m2 = await page.evaluate(MEASURE)
                if m2["broken"]:
                    notes.append(f"{name}: broken pictures {m2['broken']}")
                if m["dup"]:
                    notes.append(f"{name}: the same picture twice on the first screen: {m['dup']}")
                if m2["sideways"]:
                    notes.append(f"{name}: the page scrolls sideways at {a.width}px")
            # one dish sheet and a cart with something in it
            brand = pages[1][1] if len(pages) > 1 else ""
            await page.goto(a.base + brand)
            await page.wait_for_timeout(800)
            rows = page.locator(".row")
            if await rows.count():
                await rows.first.click()
                await page.wait_for_timeout(700)
                await page.screenshot(path=str(out / "dish-sheet.png"))
                add = page.locator(".dish button", has_text="Add").last
                if await add.count():
                    await add.click()
                    await page.wait_for_timeout(400)
            await page.goto(a.base + "cart.html")
            await page.wait_for_timeout(900)
            await page.screenshot(path=str(out / "cart-top.png"))
            await page.screenshot(path=str(out / "cart-full.png"), full_page=True)
            if errors:
                notes.append(f"script errors: {errors[:3]}")
            await br.close()
    finally:
        if server:
            server.terminate()
    print(f"Screenshots in {out}/ ({'closed, 2 PM' if a.closed else 'open, 11:10 PM'}, {a.width}px wide, {a.lang})")
    for n in notes:
        print("  " + n)
    if not notes:
        print("  nothing measurable wrong. Now look at every -top.png as a customer would.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8462/")
    ap.add_argument("--out", default="/tmp/order-aruba-shots")
    ap.add_argument("--closed", action="store_true")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--lang", default="en-US", help="phone language, e.g. nl-NL, es-ES, pap-AW")
    asyncio.run(main(ap.parse_args()))
