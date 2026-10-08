#!/usr/bin/env python3
"""Count the tells that make a page, an app screen or a piece of writing look machine-made.

    python3 slop_check.py site/                     # every html/css/js/jsx/tsx/vue/svelte/md/txt/json file under it
    python3 slop_check.py index.html styles.css     # just these
    python3 slop_check.py --url https://example.com # a live page (its HTML and inline CSS)
    python3 slop_check.py --text "Some copy to check"
    python3 slop_check.py site/ --allow facts.txt   # phrases the owner confirmed are true (one per line)
    python3 slop_check.py site/ --show              # also print every line of visible text it read
    python3 slop_check.py site/ --json              # machine-readable

  FAIL  a tell nobody should ship: generator words, em dashes, invented proof, fake urgency,
        emoji as icons, gradient text, the same picture twice on one page. Exit code 1.
  WARN  worth a look: rhythms (staccato triads, "not just X but Y"), Title Case, template
        section names, default fonts, pills and glows, uncontracted prose. Exit code 0.

It counts what can be counted. Whether a photo looks generated, or a page looks like every
other template, needs eyes: take screenshots (shoot.py) and look.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------- copy
BANNED = {   # word or phrase -> why it reads generated, and what to do instead
    "—": "em dash: people don't type them in a chat or on a sign. Use a full stop, a comma or two sentences",
    "delve": "nobody says it out loud", "tapestry": "generator metaphor", "testament to": "generator phrase",
    "realm": "generator word", "embark": "generator word", "navigate the": "generator phrase",
    "in today's": "filler opener", "fast-paced": "filler", "ever-evolving": "filler", "landscape": "filler unless it's scenery",
    "look no further": "generator opener", "whether you're": "generator opener", "elevate": "agency word: say what changes",
    "seamless": "nobody says it out loud: say what just works", "leverage": "say what you do with it", "unlock": "agency word",
    "empower": "agency word", "unleash": "agency word", "supercharge": "agency word", "revolutioniz": "agency word",
    "game-changer": "agency word", "game changer": "agency word", "next-level": "agency word", "next level": "agency word",
    "cutting-edge": "agency word", "state-of-the-art": "agency word", "best-in-class": "unprovable", "world-class": "unprovable",
    "robust": "vague: say what holds up, under what", "synergy": "agency word", "holistic": "agency word",
    "curated": "say who picked it and how", "bespoke": "say custom, or say what it is", "meticulous": "show the care, don't claim it",
    "effortless": "show it, don't claim it", "crafted": "say who made it", "handcrafted": "say who made it",
    "passionate": "everyone says it: show the work instead", "passion for": "everyone says it",
    "nestled": "travel-brochure word", "vibrant": "brochure word", "bustling": "brochure word", "hidden gem": "brochure phrase",
    "symphony": "generator metaphor", "mouthwatering": "name the ingredient", "mouth-watering": "name the ingredient",
    "delectable": "name the ingredient", "scrumptious": "name the ingredient", "tantaliz": "name the ingredient",
    "indulge": "say what they get", "savor": "say what they get", "savour": "say what they get", "culinary": "nobody orders 'culinary'",
    "gourmet": "say what's in it", "artisan": "only with a name and a reason", "perfection": "say what was done",
    "treat yourself": "generator phrase", "like never before": "generator phrase", "lorem ipsum": "placeholder text",
    "john doe": "placeholder person", "jane doe": "placeholder person", "acme": "placeholder company",
}
PROOF = [   # claims nobody measured: fine only once confirmed (put the exact phrase in --allow)
    (r"\baward[- ]winning\b|\bawards?\b", "award claim"), (r"#\s?1\b|\bnumber one\b|\bthe best (in|on)\b", "'#1' / 'the best in'"),
    (r"\b[45](\.\d)?[- ]star|★|⭐", "star rating"), (r"\btrusted by\b|\bloved by\b|\bjoin (over |more than )?[\d,]+", "popularity claim"),
    (r"(?<!max )(?<!maximum )(?<!up to )(?<!for )(?<!seats )(?<!room for )(?<!fits )\b\d[\d,.]*\+\s?(happy |satisfied )?(customers|clients|users|guests)\b|\b\d[\d,.]*\s(happy|satisfied) (customers|clients|users|guests)\b|\b\d{1,3}(,\d{3})+ (customers|clients|users|guests)\b", "customer count"),
    (r"\bsince (19|20)\d\d\b", "founding year"), (r"\b100% (satisfaction|guarantee|organic|natural)", "100% claim"),
    (r"\b(family|secret|grandma'?s) recipe", "recipe story"), (r"\blocally sourced\b|\bfarm[- ]to[- ]table\b", "sourcing claim"),
]
URGENCY = r"\bonly \d+ (left|spots?|seats?)\b|\b\d+ (people|others) (are )?(viewing|looking|booked)\b|\bhurry\b|\boffer ends\b|\blimited time\b"
WATCH = [   # (pattern, how many are fine per file, why)
    (r"\bnot just\b|\bmore than just\b|\bit'?s not (just )?(a|an|about)\b[^.]{0,40}\bit'?s\b", 0, "'not just X, it's Y' rhythm"),
    (r"^(ready|looking|want|tired) [^?]{0,60}\?", 0, "rhetorical-question opener"),
    (r"\b(discover|explore|experience|unlock|elevate|transform) (the|your|our)\b", 0, "brochure verb + 'the/your'"),
    (r"\bsimply\b|\beffortlessly\b|\bwith ease\b", 1, "'simply / effortlessly': show it"),
    (r"\bauthentic\b", 0, "'authentic': prove it with a detail or drop it"),
    (r"\bdelicious\b|\bamazing\b|\bincredible\b|\bstunning\b|\bunforgettable\b", 1, "empty superlative: name the detail"),
    (r"\bfresh(ly)?\b", 3, "'fresh' on everything stops meaning anything"),
    (r"!", 1, "exclamation marks"),
    (r"\brather than\b|\binstead of\b", 2, "'rather than / instead of' tic"),
]
TEMPLATE_HEADINGS = r"^(why choose us|our (services|features|mission|story|values)|features|testimonials|what (our )?(customers|clients|people) (say|are saying)|how it works|get started( today)?|ready to get started\??|meet the team|our journey|frequently asked questions)$"
GENERIC_CTA = r"^(learn more|get started|submit|click here|read more|discover more|explore now|shop now)$"
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌✨]")
UNCONTRACTED = [r"\bdo not\b", r"\bdoes not\b", r"\bis not\b", r"\bare not\b", r"\bwill not\b", r"\bcannot\b",
                r"\bwe are\b", r"\byou are\b", r"\byou will\b", r"\bit is\b", r"\bwe will\b", r"\bdid not\b", r"\bthat is\b"]

# ---------------------------------------------------------------- style
SLOP_CSS = [
    (r"background-clip:\s*text|text-fill-color:\s*transparent|bg-clip-text", "FAIL", "gradient text: make text one flat colour"),
    (r"\b(from|via|to)-(purple|indigo|violet|fuchsia|pink)-\d00\b", "FAIL", "the purple-to-pink generator gradient"),
    (r"(linear|radial|conic)-gradient\([^)]*(#[a-f0-9]{3,6}|rgb)[^)]*(#[a-f0-9]{3,6}|rgb)", "WARN", "colour gradient: fine as a dark scrim on a photo, not as decoration"),
    (r"box-shadow:[^;}]*\b0 0 (1[2-9]|[2-9]\d)px", "WARN", "glow: real things don't glow (a neon sign may)"),
    (r"backdrop-filter:\s*blur|backdrop-blur", "WARN", "frosted glass: fine for a bar over moving content, not as a card style"),
    (r"\banimate-(pulse|bounce|ping)\b|animation:[^;]*(pulse|bounce)", "WARN", "attention animation: move only on real state change"),
    (r"\b(rounded-3xl|shadow-2xl)\b", "WARN", "UI-generator default (huge radius / huge shadow)"),
]
DEFAULT_FONTS = r"font-family:[^;]*\b(Inter|Poppins|Montserrat|Space Grotesk|Sora|Plus Jakarta Sans)\b|family=(Inter|Poppins|Montserrat)\b"
SPARKLE = re.compile(r"[✦✧✨]|M\s?\d+\s+\d+l[\d.]+\s+[\d.]+L\d+\s+\d+l-[\d.]+\s+[\d.]+L\d+\s+\d+l-[\d.]+\s+-[\d.]+L\d+\s+\d+l[\d.]+\s+-[\d.]+z", re.I)
AI_IMAGE_NAME = re.compile(r"(dall[·-]?e|midjourney|gemini_generated|chatgpt image|stable[-_ ]?diffusion|firefly|_upscaled|ai[-_]generated)", re.I)
TEXT_EXT = {".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".md", ".mdx", ".txt", ".json"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "vendor", "__pycache__", "coverage"}


def visible_lines(src, kind):
    """The words a reader actually sees, as lines (one per block)."""
    if kind == "html":
        body = src[src.find("<body"):] if "<body" in src else src
        body = re.sub(r"<(script|style|svg|noscript|code|pre)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
        body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
        body = re.sub(r"</?(b|strong|em|i|span|a|small|abbr|u|mark|sup|sub|br)\b[^>]*>", " ", body, flags=re.I)
        txt = re.sub(r"<[^>]+>", "\n", body)
        for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"), ("&rsquo;", "'"), ("&mdash;", "—"), ("&ndash;", "–"), ("&quot;", '"')):
            txt = txt.replace(a, b)
        return [re.sub(r"\s+", " ", l).strip() for l in txt.split("\n") if l.strip()]
    if kind == "jsx":   # text between tags and string props people read
        out = re.findall(r">\s*([^<>{}\n][^<>{}]*?)\s*<", src)
        out += re.findall(r"\b(?:title|label|placeholder|alt|aria-label|description|subtitle|heading|cta|text)\s*[:=]\s*[\"'`]([^\"'`]{3,})[\"'`]", src)
        return [o.strip() for o in out if re.search(r"[A-Za-z]{3}", o)]
    if kind == "js":
        out = re.findall(r"\b(?:t|tr|i18n|__)\(\s*[\"']([^\"']{3,})[\"']", src)
        out += re.findall(r"\b(?:title|label|placeholder|message|text|description|heading)\s*:\s*[\"'`]([^\"'`]{3,})[\"'`]", src)
        return out
    if kind == "json":
        out = []
        def walk(v, key=""):
            if isinstance(v, str):
                if re.search(r"[A-Za-z]{3} [A-Za-z]", v) and not re.match(r"^(https?:|/|#|\.|[\w-]+\.(png|jpe?g|webp|svg|mp4))", v):
                    out.append(v)
            elif isinstance(v, dict):
                [walk(x, k) for k, x in v.items() if k not in ("id", "img", "src", "href", "url", "color", "icon")]
            elif isinstance(v, list):
                [walk(x, key) for x in v]
        try:
            walk(json.loads(src))
        except ValueError:
            pass
        return out
    if kind in ("md", "txt"):
        src = re.sub(r"```.*?```", " ", src, flags=re.S)
        src = re.sub(r"`[^`\n]*`", " ", src)
        return [l.strip(" #>*-") for l in src.splitlines() if l.strip()]
    return []


def kind_of(path):
    ext = path.suffix.lower()
    return {".html": "html", ".htm": "html", ".jsx": "jsx", ".tsx": "jsx", ".vue": "jsx", ".svelte": "jsx",
            ".js": "js", ".ts": "js", ".json": "json", ".md": "md", ".mdx": "md", ".txt": "txt"}.get(ext, "css" if ext in (".css", ".scss") else "")


def copy_findings(where, lines, allow):
    out = []
    keep = [l for l in lines if not any(a in l.lower() for a in allow)]
    for t in keep:
        low = t.lower()
        for word, why in BANNED.items():
            if word in low:
                out.append(("FAIL", where, f"{'em dash' if word == '—' else repr(word)} in “{t[:80]}”: {why}"))
        for pat, why in PROOF:
            if re.search(pat, t, flags=re.I):
                out.append(("FAIL", where, f"{why} in “{t[:80]}”: never invent proof. If it's true and confirmed, pass the phrase with --allow"))
        if re.search(URGENCY, t, flags=re.I):
            out.append(("FAIL", where, f"fake urgency in “{t[:80]}”: only real stock and real deadlines"))
        if EMOJI.search(t):
            out.append(("FAIL", where, f"emoji in “{t[:60]}”: a word, or a drawn icon where it helps a tap"))
        sents = [s for s in re.split(r"(?<=[.!?])\s+", t) if s]
        for i in range(len(sents) - 2):
            if all(len(s.split()) <= 4 for s in sents[i:i + 3]):
                out.append(("WARN", where, f"staccato triad “{' '.join(sents[i:i + 3])[:80]}”: the most common generated rhythm"))
                break
        words = t.split()
        if 3 <= len(words) <= 9 and all(w[:1].isupper() for w in words if w[:1].isalpha()) and not t.isupper() and not t.endswith(".") \
                and not re.search(r"[\d:@/]", t):   # labels with a number, a colon or an address are names, not headings
            out.append(("WARN", where, f"Title Case “{t}”: sentence case reads like a person (skip if it's a name)"))
        if re.match(TEMPLATE_HEADINGS, low.strip(" :")):
            out.append(("WARN", where, f"template section name “{t}”: name what's actually there"))
        if re.match(GENERIC_CTA, low.strip(" →›>")):
            out.append(("WARN", where, f"generic button “{t}”: say what happens when they tap"))
    every = " \n".join(keep)
    for pat, ceiling, why in WATCH:
        n = len(re.findall(pat, every, flags=re.I | re.M))
        if n > ceiling:
            out.append(("WARN", where, f"{n}x {why}"))
    full = sum(len(re.findall(p, every, flags=re.I)) for p in UNCONTRACTED)
    short = len(re.findall(r"\w[’'](t|s|re|ve|ll|d|m)\b", every))
    if full > 3 and short / (short + full) < 0.4:
        out.append(("WARN", where, f"{full} uncontracted forms vs {short} contractions: people say don't, we're, you'll"))
    return out


def style_findings(where, src, kind):
    out = []
    css = src
    if kind == "html":
        css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", src, flags=re.S | re.I) + re.findall(r'style="([^"]*)"', src) +
                        re.findall(r'class(?:Name)?="([^"]*)"', src) + re.findall(r'<link[^>]+href="([^"]+fonts[^"]+)"', src))
    elif kind == "jsx":
        css = "\n".join(re.findall(r'class(?:Name)?=\{?["`]([^"`]*)["`]', src)) + "\n" + src
    for pat, level, why in SLOP_CSS:
        n = len(re.findall(pat, css, flags=re.I))
        if n:
            out.append((level, where, f"{n}x {why}"))
    if re.search(DEFAULT_FONTS, css, flags=re.I):
        out.append(("WARN", where, "a template-default font (Inter, Poppins, Montserrat…): fine, but it's the first thing that makes a page look like every other"))
    pills = len(re.findall(r"border-radius:\s*(9{3,}|100)px|border-radius:\s*50vh|\brounded-full\b", css))
    if pills > 12:
        out.append(("WARN", where, f"{pills} pill shapes: chips on everything is the app-template look. Keep pills for things you tap"))
    centered = len(re.findall(r"text-align:\s*center|\btext-center\b", css))
    if centered > 15:
        out.append(("WARN", where, f"{centered}x centred text: left-aligned reads like a document, centred everything reads like a template"))
    if SPARKLE.search(src):
        out.append(("FAIL", where, "sparkle star (✦ / ✨ / a four-point star path): it's the icon of AI products"))
    return out


def image_findings(where, src, base_dir):
    """Same picture twice on one page, and generator file names."""
    out = []
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', src) + re.findall(r"url\(['\"]?([^)'\"]+\.(?:png|jpe?g|webp|avif))", src)
    seen = {}
    for s in srcs:
        key = s.split("?")[0]
        seen[key] = seen.get(key, 0) + 1
        if AI_IMAGE_NAME.search(s):
            out.append(("WARN", where, f"picture named like a generator export ({s.split('/')[-1]}): rename it, and check it shows the real thing"))
    for s, n in seen.items():
        if n > 1 and not re.search(r"(logo|icon|avatar|sprite|mark)", s, flags=re.I):
            out.append(("FAIL", where, f"the same picture {n} times on one page ({s.split('/')[-1]}): the stock-template look"))
    if base_dir is None:
        return out
    try:
        from PIL import Image
    except ImportError:
        return out
    files = []
    for s in seen:
        p = (base_dir / s.lstrip("/")).resolve() if not s.startswith("http") else None
        if p and p.exists():
            files.append(p)
    def dhash(im, n=12):
        px = list(im.convert("L").resize((n + 1, n), Image.LANCZOS).tobytes())
        return [px[r * (n + 1) + c] > px[r * (n + 1) + c + 1] for r in range(n) for c in range(n)]
    def zoom(im, s, ar):
        w, h = im.size
        cw = w * s; ch = cw / ar
        if ch > h * s:
            ch = h * s; cw = ch * ar
        l, t = (w - cw) / 2, (h - ch) / 2
        return im.crop((int(l), int(t), int(l + cw), int(t + ch)))
    def flat(im):   # a near-blank image (placeholder, solid colour) hashes like every other blank one
        from PIL import ImageStat
        return ImageStat.Stat(im.convert("L").resize((64, 64))).stddev[0] < 12
    def near(a, b):
        try:
            A, B = Image.open(a), Image.open(b)
        except OSError:
            return False
        if flat(A) or flat(B):
            return False
        ha, best = dhash(A), 1.0
        for s in (1, .9, .8, .7, .6):
            hb = dhash(zoom(B, s, A.width / A.height))
            best = min(best, sum(x != y for x, y in zip(ha, hb)) / len(ha))
        return best < 0.12
    for f in files:
        try:
            if flat(Image.open(f)):
                out.append(("WARN", where, f"{f.name} is a placeholder (almost one flat colour): a real photo goes here before anyone sees the page"))
        except OSError:
            pass
    for i in range(len(files)):
        for j in range(i + 1, min(len(files), i + 25)):
            if near(files[i], files[j]) or near(files[j], files[i]):
                out.append(("FAIL", where, f"{files[i].name} and {files[j].name} are the same picture (one is a crop or zoom of the other)"))
    return out


def gather(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in TEXT_EXT and not (set(f.parts) & SKIP_DIRS) and f.stat().st_size < 2_000_000:
                    if f.suffix == ".json" and f.name in ("package.json", "package-lock.json", "tsconfig.json", "manifest.json"):
                        continue
                    files.append(f)
        elif p.is_file():
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--url"); ap.add_argument("--text"); ap.add_argument("--allow")
    ap.add_argument("--show", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    allow = []
    if a.allow:
        allow = [l.strip().lower() for l in Path(a.allow).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    found, read = [], 0
    if a.text:
        lines = [l for l in a.text.splitlines() if l.strip()]
        read += len(lines)
        found += copy_findings("text", lines, allow)
    if a.url:
        req = urllib.request.Request(a.url, headers={"User-Agent": "Mozilla/5.0 slop-check"})
        src = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        lines = visible_lines(src, "html"); read += len(lines)
        found += copy_findings(a.url, lines, allow) + style_findings(a.url, src, "html") + image_findings(a.url, src, None)
        if a.show:
            print("\n".join("  " + l for l in lines))
    for f in gather(a.paths):
        src = f.read_text(encoding="utf-8", errors="replace")
        kind = kind_of(f)
        where = str(f)
        if kind == "css":
            found += style_findings(where, src, "css")
            continue
        lines = visible_lines(src, kind); read += len(lines)
        if a.show and lines:
            print(f"{where}:"); print("\n".join("  " + l for l in lines))
        found += copy_findings(where, lines, allow)
        if kind in ("html", "jsx"):
            found += style_findings(where, src, kind) + image_findings(where, src, f.parent if kind == "html" else None)
    seen, rows = set(), []
    for row in sorted(found, key=lambda r: (r[0] != "FAIL", r[1])):
        if row not in seen:
            seen.add(row); rows.append(row)
    fails = sum(r[0] == "FAIL" for r in rows)
    if a.json:
        print(json.dumps({"fail": fails, "warn": len(rows) - fails, "lines_read": read,
                          "findings": [{"level": l, "where": w, "what": m} for l, w, m in rows]}, indent=1, ensure_ascii=False))
    else:
        for l, w, m in rows:
            print(f"{l}  {w}  {m}")
        print(f"\n{fails} fail, {len(rows) - fails} warn, {read} lines of text read." +
              ("" if fails else " Now look at it: this script can't see a generated photo or a template layout."))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
