"""The part 2 swap: puts the kitchen and driver previews live. Run it ONLY after Victor's real test passed.

    python3 build/swap_part2.py          writes the live files from ops/kitchen-next/ and driver-next/
    then: python3 qa/check_all.py --local, look at the screens, commit ("Pidi part 2: kitchen and driver live")

What it does (every step is a plain file copy plus the few words that differ between the two places):
- ops/kitchen/: kitchen.css, live.js, index.html and manifest from the preview; sw.js from the preview with the
  live cache names back (kitchen-v<n+1>, deletes only kitchen- caches, keeps /ops/kitchen/). kitchen.js,
  menu-editor.js, books.js must still be the same as the preview's copies (else it stops: live changed meanwhile).
  kitchen-data.json is never touched (the private builder writes it).
- driver/v2/: the three pages, driver.css and js/ from the preview, with the paths one folder deeper; the two fonts
  copied into driver/fonts/ so the driver app's own worker keeps them offline; client.js registers /driver/sw.js
  again; driver/sw.js gets a new cache name, the new files, and also keeps the database library for offline use.
The previews stay where they are; delete them in a later commit once the live screens have run a night."""
import os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def path(*p): return os.path.join(ROOT, *p)
def read(p): return open(path(p), encoding="utf-8").read()
def write(p, s):
    with open(path(p), "w", encoding="utf-8") as f: f.write(s)
def must(s, old, new, what):
    if s.count(old) != 1:
        sys.exit(f"stopped: {what} not found exactly once ({old[:60]!r})")
    return s.replace(old, new)

# ------------------------------------------------------------------ kitchen
K, KN = "ops/kitchen/", "ops/kitchen-next/"
for f in ["kitchen.js", "menu-editor.js", "books.js"]:
    if read(K + f) != read(KN + f):
        sys.exit(f"stopped: {K}{f} changed since the preview was made; bring the change into {KN}{f} first")
for f in ["kitchen.css", "live.js"]:
    shutil.copyfile(path(KN + f), path(K + f))
write(K + "index.html", must(read(KN + "index.html"), "<title>Kitchen (preview)</title>", "<title>Kitchen</title>", "the preview title"))
write(K + "manifest.webmanifest", must(read(KN + "manifest.webmanifest"), '"name": "Kitchen preview"', '"name": "Kitchen"', "the preview name"))
live_n = int(re.search(r"var CACHE = 'kitchen-v(\d+)'", read(K + "sw.js")).group(1))
sw = read(KN + "sw.js")
sw = re.sub(r"\n   PREVIEW \(ops/kitchen-next/.*?keep\(\)\. \*/", " */", sw, flags=re.S)
sw = re.sub(r"var CACHE = 'next-kitchen-v\d+';", f"var CACHE = 'kitchen-v{live_n + 1}';", sw)
sw = must(sw, "var MINE = 'next-kitchen-';", "var MINE = 'kitchen-';", "the preview cache family")
sw = must(sw, "p.indexOf('/ops/kitchen-next/') >= 0", "p.indexOf('/ops/kitchen/') >= 0", "the preview folder in keep()")
write(K + "sw.js", sw)

# ------------------------------------------------------------------ driver
D, DN = "driver/v2/", "driver-next/"
os.makedirs(path("driver/fonts"), exist_ok=True)
for f in ["bigshoulders.woff2", "hanken.woff2"]:
    shutil.copyfile(path("shared/fonts", f), path("driver/fonts", f))
def deeper(s):
    s = s.replace("../driver/brand/", "../brand/").replace("../shared/fonts/", "../fonts/")
    s = s.replace('href="manifest.webmanifest"', 'href="../manifest.webmanifest"')
    return re.sub(r"<title>(.*?) \(preview\)</title>", r"<title>\1</title>", s)
for f in ["index.html", "run.html", "help.html"]:
    write(D + f, deeper(read(DN + f)))
write(D + "driver.css", read(DN + "driver.css").replace("url(../shared/fonts/", "url(../fonts/").replace("part 2 preview (driver-next/, 19 Nov 2026)", "part 2 (19 Nov 2026)"))
os.makedirs(path(D + "js"), exist_ok=True)
for f in ["home.js", "run.js"]:
    shutil.copyfile(path(DN + "js", f), path(D + "js", f))
c = read(DN + "js/client.js")
c = re.sub(r"\n   PART 2 PREVIEW \(driver-next/.*?the plain-words helpers below\. \*/", "\n   Part 2 (19 Nov 2026): no-signal handling (the screen and the run stay, taps wait on the phone) and the\n   plain-words helpers below. */", c, flags=re.S)
c = re.sub(r"/\* PREVIEW WORKER: .*?at the swap\. \*/", "/* The driver app's offline cache (/driver/sw.js) covers /driver/, v2 included. */", c, flags=re.S)
c = must(c, 'navigator.serviceWorker.register(new URL("../sw.js", import.meta.url), { scope: new URL("../", import.meta.url).pathname })',
         'navigator.serviceWorker.register(new URL("../../sw.js", import.meta.url), { scope: new URL("../../", import.meta.url).pathname })', "the preview worker")
write(D + "js/client.js", c)
sw = read("driver/sw.js")
n = int(re.search(r'var CACHE = "pidi-driver-v(\d+)";', sw).group(1))
sw = re.sub(r'var CACHE = "pidi-driver-v\d+";', f'var CACHE = "pidi-driver-v{n + 1}";', sw)
sw = must(sw, '  "v2/v2.css",\n', '  "v2/v2.css",\n  "v2/driver.css",\n  "fonts/bigshoulders.woff2",\n  "fonts/hanken.woff2",\n', "the v2 file list")
sw = must(sw, '  return url.origin === self.location.origin && url.pathname.indexOf("/driver/") !== -1;',
          '  // part 2: the database library from the CDN too, so the app opens without signal once it has been opened\n'
          '  return (url.origin === self.location.origin && url.pathname.indexOf("/driver/") !== -1) || url.hostname === "cdn.jsdelivr.net";', "underDriver()")
write("driver/sw.js", sw)
m = read("driver/manifest.webmanifest").replace('"background_color": "#12143A"', '"background_color": "#100E0C"').replace('"theme_color": "#12143A"', '"theme_color": "#100E0C"')
write("driver/manifest.webmanifest", m)
print(f"swapped: ops/kitchen/ (cache kitchen-v{live_n + 1}) and driver/v2/ (cache pidi-driver-v{n + 1}). Now run qa/check_all.py --local.")
