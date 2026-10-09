#!/usr/bin/env python3
"""Live phone flow for the Pidi driver app.

Run against GitHub Pages (the default):

    python3 driver/tests/flow.py

Or against a local server:

    PIDI_BASE=http://127.0.0.1:8765/driver/ python3 driver/tests/flow.py

Uses Playwright Chromium with the iPhone 13 and Pixel 7 device profiles.
Screenshots go to /opt/cursor/artifacts/driver-flow/ unless PIDI_SHOTS is set.
"""

import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RUN = json.loads((Path(__file__).resolve().parent / "test_run.json").read_text(encoding="utf-8"))
LIVE = "https://victorfromaruba-stack.github.io/restaurant-/driver"
SHOTS = Path(os.environ.get("PIDI_SHOTS", "/opt/cursor/artifacts/driver-flow"))
BASE = os.environ.get("PIDI_BASE", LIVE).rstrip("/") + "/"

DROP1 = RUN["drops"][0]
DROP2 = RUN["drops"][1]


def money(cents):
    sign = "-" if cents < 0 else ""
    n = abs(int(cents))
    return f"{sign}ƒ{n // 100}.{n % 100:02d}"


def encode_run(obj):
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return "1." + token


TOKEN = encode_run(RUN)
RUN_URL = BASE + "run.html#" + TOKEN
LIVE_LINK = LIVE + "/run.html#" + TOKEN

CASH = DROP1["total"]
CHANGE = DROP1["paysWith"] - DROP1["total"]
MAPS = (
    "https://www.google.com/maps/dir/?api=1&destination="
    + DROP1["lat"] + "," + DROP1["lng"] + "&travelmode=driving"
)
WAZE = "https://waze.com/ul?ll=" + DROP1["lat"] + "," + DROP1["lng"] + "&navigate=yes"
MAPS2 = (
    "https://www.google.com/maps/dir/?api=1&destination="
    + DROP2["lat"] + "," + DROP2["lng"] + "&travelmode=driving"
)
WAZE2 = "https://waze.com/ul?ll=" + DROP2["lat"] + "," + DROP2["lng"] + "&navigate=yes"


def check_link_file():
    path = ROOT / "driver" / "TEST_RUN.txt"
    first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    if first != LIVE_LINK:
        raise SystemExit("driver/TEST_RUN.txt is stale.\nfile: " + first + "\nnow:  " + LIVE_LINK)


def shot(device, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    slug = "iphone13" if "iPhone" in device else "pixel7"
    name = name[:-4] if name.endswith(".png") else name
    return str(SHOTS / f"{slug}-{name}.png")


def fonts(page):
    page.evaluate("() => document.fonts.ready.then(() => true)")


def run_device(browser, playwright, device_name):
    results = []
    device = dict(playwright.devices[device_name])
    device.pop("default_browser_type", None)
    context = browser.new_context(**device)
    page = context.new_page()
    page.set_default_timeout(20000)
    ok = True

    def record(name, fn):
        nonlocal ok
        if not ok:
            results.append((name, "blocked", "earlier step failed"))
            return
        try:
            fn()
        except Exception as exc:
            ok = False
            msg = str(exc).split("\n")[0][:300]
            results.append((name, "fail", msg))
            try:
                page.screenshot(path=shot(device_name, "fail-" + name))
            except Exception:
                pass
            return
        results.append((name, "pass", ""))

    def open_run():
        page.goto(RUN_URL, wait_until="domcontentloaded")
        page.get_by_role("button", name="Start pickup").wait_for()
        fonts(page)
        page.screenshot(path=shot(device_name, "01-open.png"))
        body = page.locator("body").inner_text()
        if "Maria TEST" not in body or "Carlos TEST" not in body:
            raise AssertionError("opened run is missing the two TEST drops")
        if "TEST run" not in body:
            raise AssertionError("TEST banner missing")

    def pickup():
        page.get_by_role("button", name="Start pickup").click()
        page.get_by_role("button", name="Picked up").wait_for()
        fonts(page)
        text = page.locator("main").inner_text()
        if "Chicken fried rice" not in text or "Birria tacos" not in text:
            raise AssertionError("pickup is missing the bag items")
        page.screenshot(path=shot(device_name, "02-pickup.png"))
        page.get_by_role("button", name="Picked up").click()

    def drop1():
        page.locator("[data-money=collect]").wait_for()
        fonts(page)
        expect(page.locator("[data-money=collect]")).to_have_text(money(CASH))
        expect(page.locator("[data-money=pays]")).to_have_text(money(DROP1["paysWith"]))
        expect(page.locator("[data-money=change]")).to_have_text(money(CHANGE))
        expect(page.locator("[data-nav=google]")).to_have_attribute("href", MAPS)
        expect(page.locator("[data-nav=waze]")).to_have_attribute("href", WAZE)
        expect(page.locator("[data-act=call]")).to_have_attribute("href", "tel:+" + DROP1["phone"])
        wa = page.locator("[data-act=whatsapp]").get_attribute("href")
        if not wa.startswith("https://wa.me/" + DROP1["phone"]):
            raise AssertionError("WhatsApp href " + str(wa))
        text = parse_qs(urlparse(wa).query).get("text", [""])[0]
        if "Maria TEST" not in text or "Dushi Wok" not in text:
            raise AssertionError("WhatsApp text " + text)
        page.screenshot(path=shot(device_name, "03-drop1-cash.png"))
        page.get_by_role("button", name="Delivered").click()

    def drop2():
        page.get_by_role("heading", name="Carlos TEST").wait_for()
        fonts(page)
        expect(page.get_by_text("Awaiting transfer", exact=True)).to_be_visible()
        expect(page.locator("[data-money=transfer]")).to_have_text("Don't collect cash")
        if page.locator("[data-money=collect]").count() != 0:
            raise AssertionError("transfer drop shows cash to collect")
        expect(page.locator("[data-nav=google]")).to_have_attribute("href", MAPS2)
        expect(page.locator("[data-nav=waze]")).to_have_attribute("href", WAZE2)
        expect(page.locator("[data-act=call]")).to_have_attribute("href", "tel:+" + DROP2["phone"])
        wa = page.locator("[data-act=whatsapp]").get_attribute("href")
        if not wa.startswith("https://wa.me/" + DROP2["phone"]):
            raise AssertionError("WhatsApp href " + str(wa))
        page.screenshot(path=shot(device_name, "04-drop2-transfer.png"))
        page.get_by_role("button", name="Delivered").click()

    def cash():
        page.get_by_role("link", name="Count the cash").click()
        page.locator("[data-total=collected]").wait_for()
        expect(page.locator("[data-total=collected]")).to_have_text(money(CASH))
        if "Carlos TEST" not in page.locator("main").inner_text():
            raise AssertionError("transfer order missing from the count")
        if page.locator("main").inner_text().count(money(DROP2["total"])) and money(DROP2["total"]) == money(CASH):
            pass
        page.locator("[data-field=counted]").fill(f"{CASH / 100:.2f}")
        page.get_by_role("button", name="Compare").click()
        expect(page.locator("[data-result=match]")).to_be_visible()
        expect(page.locator("[data-total=counted]")).to_have_text(money(CASH))
        fonts(page)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.screenshot(path=shot(device_name, "05-cash-count.png"))

    def install_and_pwa():
        manifest = page.evaluate(
            """async () => {
              const link = document.querySelector('link[rel="manifest"]');
              const href = new URL(link.getAttribute('href'), location.href).href;
              const res = await fetch(href);
              const j = await res.json();
              return {
                status: res.status,
                href,
                name: j.name,
                short_name: j.short_name,
                display: j.display,
                icons: j.icons || [],
                scope: new URL(j.scope, href).href,
                start: new URL(j.start_url, href).href
              };
            }"""
        )
        if manifest["status"] != 200:
            raise AssertionError("manifest status " + str(manifest["status"]))
        if not manifest["name"] or "Pidi" not in manifest["name"]:
            raise AssertionError("manifest name " + str(manifest["name"]))
        if manifest["display"] != "standalone":
            raise AssertionError("display " + str(manifest["display"]))
        if len(manifest["icons"]) < 1 or not manifest["icons"][0].get("src"):
            raise AssertionError("manifest has no icons")
        for label, url in (("scope", manifest["scope"]), ("start_url", manifest["start"])):
            path = urlparse(url).path
            if "/driver/" not in path and not path.rstrip("/").endswith("/driver"):
                raise AssertionError(label + " is not under /driver/: " + url)
            if path.rstrip("/").endswith("/restaurant-"):
                raise AssertionError(label + " covers the whole site: " + url)
        scope = page.evaluate(
            """() => navigator.serviceWorker.ready.then(reg => reg.scope)"""
        )
        path = urlparse(scope).path
        if not path.rstrip("/").endswith("/driver"):
            raise AssertionError("service worker scope is " + scope)
        if "/driver/" not in scope:
            raise AssertionError("service worker scope is " + scope)
        page.goto(BASE + "install/", wait_until="domcontentloaded")
        page.get_by_role("heading", name="Add Pidi").wait_for()
        fonts(page)
        page.screenshot(path=shot(device_name, "06-install.png"))

    record("01-open", open_run)
    record("02-pickup", pickup)
    record("03-drop1-cash", drop1)
    record("04-drop2-transfer", drop2)
    record("05-cash-count", cash)
    record("06-install", install_and_pwa)
    context.close()
    return results


def main():
    if len(TOKEN) < 20:
        raise SystemExit("encoded run is empty")
    if len(LIVE_LINK) > 1800:
        raise SystemExit("test link is too long: " + str(len(LIVE_LINK)))
    check_link_file()
    print("RUN " + RUN_URL)
    print("CASH " + money(CASH) + " CHANGE " + money(CHANGE) + " TRANSFER " + money(DROP2["total"]))
    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for name in ("iPhone 13", "Pixel 7"):
                rows = run_device(browser, p, name)
                for step, status, detail in rows:
                    all_rows.append((name, step, status, detail))
        finally:
            browser.close()

    print("\n| Device | Step | Result | Detail |")
    print("| --- | --- | --- | --- |")
    failed = False
    for device, step, status, detail in all_rows:
        if status != "pass":
            failed = True
        safe = detail.replace("|", "/")
        print(f"| {device} | {step} | {status} | {safe} |")
    print("\nScreenshots: " + str(SHOTS))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
