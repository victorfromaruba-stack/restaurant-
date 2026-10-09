#!/usr/bin/env python3
"""Count the tells that make Order Aruba look or read machine-made.

    python3 .claude/skills/human-touch/scripts/check.py            # the whole customer site
    python3 .claude/skills/human-touch/scripts/check.py --show     # also print every line of copy it read
    python3 .claude/skills/human-touch/scripts/check.py page.html  # just these files (html, md, json, js)

It reads what a customer actually sees: the pages, every tr("...") string in
shared/order-app.js, the rendered menu fields and site.json. The chef app is
skipped (staff screen, different rules).

  FAIL  breaks a rule we don't bend: em dashes, generator words, invented proof,
        emoji, the same picture twice on one screen. Exit code 1.
  WARN  worth a look: formula copy repeated across restaurants, staccato triads,
        pill shapes everywhere, gradients. Exit code stays 0.

It counts what can be counted. Whether a photo looks generated, or a page
looks like every other delivery app, needs eyes: run shoot.py and look.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # .claude/skills/human-touch/scripts -> repo
ALLOW = Path(__file__).resolve().parents[1] / "allow.txt"

# ---------------------------------------------------------------- copy rules
# Words a generator reaches for when it has nothing specific to say about the food.
BANNED = {
    "—": "em dash: use a full stop, a comma or two sentences (a real menu board never has one)",
    "mouthwatering": "generator word: name the ingredient that makes it good",
    "mouth-watering": "generator word: name the ingredient that makes it good",
    "delectable": "generator word", "scrumptious": "generator word", "sumptuous": "generator word",
    "tantaliz": "generator word", "tantalis": "generator word", "decadent": "generator word",
    "indulge": "generator word: say what it is", "indulgent": "generator word",
    "savor": "generator word", "savour": "generator word",
    "culinary": "nobody orders 'culinary' at midnight", "gastronom": "nobody says this out loud",
    "journey": "food isn't a journey", "elevate": "agency word", "symphony": "generator word",
    "burst of flavo": "generator phrase: name the flavour", "explosion of": "generator phrase",
    "crave-worthy": "generator phrase", "irresistible": "generator word", "unforgettable": "generator word",
    "unparalleled": "generator word", "unrivaled": "generator word", "perfection": "generator word",
    "perfectly": "say what was done to it instead", "artisan": "only if it's true and you can say who",
    "gourmet": "our prices are snackbar prices: say what's in it", "handcrafted": "generator word",
    "hand-crafted": "generator word", "crafted with": "generator phrase", "made with love": "generator phrase",
    "passion": "generator word", "like never before": "generator phrase", "next level": "generator phrase",
    "next-level": "generator phrase", "game changer": "generator phrase", "game-changer": "generator phrase",
    "seamless": "nobody says it out loud", "vibrant": "generator word", "nestled": "generator word",
    "look no further": "generator opener", "whether you're": "generator opener",
    "treat yourself": "generator phrase", "satisfy your cravings": "generator phrase",
    "world-class": "unprovable", "heavenly": "generator word", "lorem ipsum": "placeholder text",
}
# Claims nobody measured. Fine only once Victor confirms them: add the exact phrase to allow.txt.
PROOF = [
    (r"\baward", "award claim"), (r"\bbest (in|on) aruba\b", "'best in Aruba'"), (r"#\s?1\b|\bnumber one\b", "'#1'"),
    (r"\b(5|five)[- ]star", "star rating"), (r"★", "star rating"), (r"\brated\b", "rating claim"),
    (r"\bcustomers love\b|\bloved by\b|\bfan favou?rite", "popularity claim"), (r"\bthousands of\b", "volume claim"),
    (r"\bsince (19|20)\d\d\b", "founding year"), (r"\b(family|secret|grandma'?s|nonna'?s) recipe", "recipe story"),
    (r"\blocally sourced\b|\borganic\b|\bfarm[- ]fresh\b", "sourcing claim"), (r"\bour chef\b|\bchef [A-Z]", "a chef nobody has named"),
]
WATCH = [   # (pattern, how many are fine across the whole site, why)
    (r"\bauthentic\b", 0, "'authentic': prove it with a detail or drop it"),
    (r"\bdelicious\b", 1, "'delicious': the photo and the ingredients say that"),
    (r"\bfresh(ly)?\b", 3, "'fresh' on everything stops meaning anything"),
    (r"\bfavou?rites?\b", 1, "'favourites': filler, name the dish"),
    (r"\bbold\b", 0, "'bold': filler"), (r"\bexperience\b", 0, "'experience': say what happens"),
    (r"\bsucculent\b|\bzesty\b|\bmelt-in", 0, "menu cliché: name the cut, the sauce, the cooking"),
    (r"\bnot just\b|\bmore than just\b", 0, "'not just X but Y' rhythm"),
    (r"!", 1, "exclamation marks: one, at most, on the whole site"),
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
UNCONTRACTED = [r"\bdo not\b", r"\bdoes not\b", r"\bis not\b", r"\bare not\b", r"\bwill not\b", r"\bcannot\b",
                r"\bwe are\b", r"\byou are\b", r"\byou will\b", r"\bit is\b", r"\bwe will\b", r"\bdid not\b"]

# ---------------------------------------------------------------- style rules
SLOP_CSS = [   # (pattern, level, why); rules whose selector mentions .sign are skipped: the OPEN sign is neon on purpose
    (r"background-clip:\s*text|text-fill-color:\s*transparent", "FAIL", "gradient text"),
    (r"box-shadow:[^;}]*\b0 0 (1[2-9]|[2-9]\d)px", "WARN", "big glow: the OPEN sign may glow, nothing else"),
]


def allowed():
    if not ALLOW.exists():
        return []
    return [l.strip().lower() for l in ALLOW.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def html_text(src):
    body = src[src.find("<body"):] if "<body" in src else src
    body = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    body = re.sub(r"</?(b|strong|em|i|span|a|small|abbr)\b[^>]*>", "", body, flags=re.I)   # inline tags don't end a line
    txt = re.sub(r"<[^>]+>", "\n", body)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"), ("&rsquo;", "'"), ("&mdash;", "—"), ("&ndash;", "–")):
        txt = txt.replace(a, b)
    return [l.strip() for l in txt.split("\n") if l.strip()]


def js_strings(src):
    out = re.findall(r'\btr\(\s*"((?:[^"\\]|\\.)*)"', src) + re.findall(r"\btr\(\s*'((?:[^'\\]|\\.)*)'", src)
    return [bytes(s, "utf-8").decode("unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore") if "\\u" in s else s
            for s in out]


def site_copy():
    """Every piece of customer-facing copy, as (where, text)."""
    items = []
    site = json.loads((ROOT / "shared/site.json").read_text(encoding="utf-8"))
    for page in [b["id"] + "/index.html" for b in site["brands"]]:
        p = ROOT / page
        if p.exists():
            items += [(page, t) for t in html_text(p.read_text(encoding="utf-8"))]
    app = ROOT / "shared/order-app.js"
    items += [("shared/order-app.js", t) for t in js_strings(app.read_text(encoding="utf-8"))]
    for k in ("eta", "deliveryTime", "payment"):
        if isinstance(site.get(k), str):
            items.append(("shared/site.json " + k, site[k]))
    for b in site["brands"]:
        m = json.loads((ROOT / b["id"] / "menu.json").read_text(encoding="utf-8"))
        where = b["id"] + "/menu.json"
        for k in ("name", "tagline", "cuisine", "imageNote"):
            if m.get(k):
                items.append((where + " " + k, m[k]))
        items += [(where + " section", s["title"]) for s in m["sections"]]
        for it in m["items"]:
            items += [(where + " " + it["id"], it["name"]), (where + " " + it["id"], it.get("desc", ""))]
            for o in it.get("options", []):
                items.append((where + " " + it["id"] + " option", o.get("label", "")))
                items += [(where + " " + it["id"] + " option", c.get("label", "")) for c in o.get("choices", [])]
    return [(w, t) for w, t in items if t]


def file_copy(paths):
    items = []
    for p in paths:
        src = Path(p).read_text(encoding="utf-8", errors="replace")
        if p.endswith((".html", ".htm")):
            items += [(p, t) for t in html_text(src)]
        elif p.endswith(".js"):
            items += [(p, t) for t in js_strings(src)]
        elif p.endswith(".json"):
            def walk(v):
                if isinstance(v, str):
                    items.append((p, v))
                elif isinstance(v, dict):
                    [walk(x) for k, x in v.items() if k not in ("img", "src", "poster", "id", "color", "logo", "mark", "hero")]
                elif isinstance(v, list):
                    [walk(x) for x in v]
            walk(json.loads(src))
        else:
            src = re.sub(r"```.*?```", " ", src, flags=re.S)
            items += [(p, l.strip()) for l in src.splitlines() if l.strip()]
    return items


def names():
    site = json.loads((ROOT / "shared/site.json").read_text(encoding="utf-8"))
    out = {"Order Aruba"}
    for b in site["brands"]:
        m = json.loads((ROOT / b["id"] / "menu.json").read_text(encoding="utf-8"))
        out |= {m["name"]} | {i["name"] for i in m["items"]}
    return out


def copy_findings(items, ok):
    out = []
    proper = names()
    def allowed_here(t):
        tl = t.lower()
        return any(a in tl for a in ok)
    for where, t in items:
        low = t.lower()
        if allowed_here(t):
            continue
        for word, why in BANNED.items():
            if word in low:
                out.append(("FAIL", where, f"{'em dash' if word == '—' else repr(word)} in “{t[:70]}”: {why}"))
        for pat, why in PROOF:
            if re.search(pat, t, flags=0 if "[A-Z]" in pat else re.I):
                out.append(("FAIL", where, f"{why} in “{t[:70]}”: never invent proof. If Victor confirmed it, add the phrase to allow.txt"))
        if EMOJI.search(t):
            out.append(("FAIL", where, f"emoji in “{t[:60]}”: use a word or a drawn icon"))
        # staccato triad: three short sentences in a row ("Five restaurants. One kitchen. One price.")
        sents = [s for s in re.split(r"(?<=[.!?])\s+", t) if s]
        for i in range(len(sents) - 2):
            if all(len(s.split()) <= 4 for s in sents[i:i + 3]):
                out.append(("WARN", where, f"staccato triad “{' '.join(sents[i:i + 3])[:70]}”: the most common generated rhythm. Say it once, plainly"))
                break
        words = t.split()
        if len(words) >= 3 and all(w[:1].isupper() for w in words) and not t.isupper() and len(t) < 60 and t not in proper:
            out.append(("WARN", where, f"Title Case “{t}”: sentence case reads like a person wrote it"))
    every = " \n".join(t for _, t in items if not allowed_here(t))
    for pat, ceiling, why in WATCH:
        n = len(re.findall(pat, every, flags=re.I))
        if n > ceiling:
            out.append(("WARN", "site", f"{n}x {why}"))
    full = sum(len(re.findall(p, every, flags=re.I)) for p in UNCONTRACTED)
    short = len(re.findall(r"\w[’'](t|s|re|ve|ll|d|m)\b", every))
    if full > 3 and short / (short + full) < 0.4:
        out.append(("WARN", "site", f"{full} uncontracted forms vs {short} contractions: people say don't, we're, you'll"))
    return out


def formula_findings():
    """The same sentence shape stamped onto every restaurant is a template tell."""
    out = []
    site = json.loads((ROOT / "shared/site.json").read_text(encoding="utf-8"))
    menus = {b["id"]: json.loads((ROOT / b["id"] / "menu.json").read_text(encoding="utf-8")) for b in site["brands"]}
    tags = [m.get("tagline", "") for m in menus.values()]
    shape = [t for t in tags if re.fullmatch(r"[^,&]+, [^,&]+ & [^,&]+", t)]
    if len(shape) >= 3:
        out.append(("WARN", "menus tagline", f"{len(shape)} of {len(tags)} restaurants use the same 'A, B & C' tagline shape: give each its own voice"))
    grams = {}
    for b, m in menus.items():
        # drinks are the same three cans everywhere on purpose
        text = " ".join([m.get("tagline", "")] + [i.get("desc", "") for i in m["items"] if i.get("kind") != "drink"]).lower()
        ws = re.findall(r"[a-z']+", text)
        for g in {" ".join(ws[i:i + 4]) for i in range(len(ws) - 3)}:
            grams.setdefault(g, set()).add(b)
    rep = sorted((g for g, bs in grams.items() if len(bs) >= 3), key=lambda g: -len(grams[g]))
    for g in rep[:5]:
        out.append(("WARN", "menus", f"“{g}” appears in {len(grams[g])} restaurants: copy-paste across brands reads generated"))
    return out


def image_findings():
    """Near-identical pictures on one restaurant screen (cover vs Featured), and one picture used for two dishes."""
    out = []
    try:
        from PIL import Image
    except ImportError:
        return [("WARN", "images", "Pillow missing: picture checks skipped (pip install pillow)")]
    def dhash(im, n=12):
        px = list(im.convert("L").resize((n + 1, n), Image.LANCZOS).tobytes())
        return [px[r * (n + 1) + c] > px[r * (n + 1) + c + 1] for r in range(n) for c in range(n)]
    def zoom(im, s, ar):   # centre crop at scale s with aspect ar (cover loops zoom into a dish picture)
        w, h = im.size
        cw = w * s; ch = cw / ar
        if ch > h * s:
            ch = h * s; cw = ch * ar
        l, t = (w - cw) / 2, (h - ch) / 2
        return im.crop((int(l), int(t), int(l + cw), int(t + ch)))
    def near(a, b):
        """Same picture, even when one is a crop or zoom of the other. Calibrated: same source < 0.06, different dishes > 0.25."""
        try:
            A, B = Image.open(ROOT / a), Image.open(ROOT / b)
        except (FileNotFoundError, OSError):
            return False
        ha, best = dhash(A), 1.0
        for s in (1, .95, .9, .85, .8, .75, .7, .65, .6):
            hb = dhash(zoom(B, s, A.width / A.height))
            best = min(best, sum(x != y for x, y in zip(ha, hb)) / len(ha))
        return best < 0.12
    site = json.loads((ROOT / "shared/site.json").read_text(encoding="utf-8"))
    for b in site["brands"]:
        m = json.loads((ROOT / b["id"] / "menu.json").read_text(encoding="utf-8"))
        feat = [i for i in m["items"] if i.get("style") in ("signature", "bundle")]
        by = {}
        for i in m["items"]:
            if i.get("kind") != "drink":
                by.setdefault(i["img"], []).append(i["name"])
        for img, names in by.items():
            if len(names) > 1:
                out.append(("WARN", b["id"], f"one picture for {len(names)} dishes ({', '.join(names)}): each dish should show itself"))
        # Restaurant page: the cover (video poster, or the dish order-app.js picks) against Featured right under it.
        ids = [f["id"] for f in feat] + [x for f in feat for x in f.get("includes", [])]   # featured dishes and the dishes inside a bundle picture
        pool = [i for i in m["items"] if i.get("kind") not in ("drink", "side") and i["id"] not in ids]
        pick = next((i for i in m["items"] if i["id"] == m.get("cover")), None) or \
            next((i for i in pool if "/art/" not in i["img"] and not i.get("soldOut")), None) or (pool or feat or m["items"])[0]
        cover = (m.get("video") or {}).get("poster") or pick["img"]
        for f in feat:
            if near(cover, f["img"]) or near(f["img"], cover):
                out.append(("FAIL", b["id"] + "/index.html", f"the cover ({cover.split('/')[-1]}) is the same picture as Featured “{f['name']}” right under it: the same photo twice on one screen is a stock-site tell"))
    return out


def css_findings():
    out = []
    pills = 0
    for css in [ROOT / "shared/order.css"]:
        if not css.exists():
            continue
        src = css.read_text(encoding="utf-8")
        for pat, level, why in SLOP_CSS:
            for m in re.finditer(pat, src):
                selector = src[src.rfind("}", 0, m.start()) + 1:src.rfind("{", 0, m.start())]
                if ".sign" not in selector:
                    out.append((level, f"{css.relative_to(ROOT)}:{src.count(chr(10), 0, m.start()) + 1}", why))
        pills += len(re.findall(r"border-radius:\s*(999|9999|100)px|border-radius:\s*50vh", src))
        for m in re.finditer(r"(linear|radial)-gradient\(([^;]*)", src):
            body = m.group(2)
            if not re.search(r"rgba?\(\s*(0|11|8|7)\s*,|transparent|var\(--(night|ink|bg)", body):   # dark scrims over photos are fine
                out.append(("WARN", f"{css.relative_to(ROOT)}:{src.count(chr(10), 0, m.start()) + 1}", "decorative gradient: flat colour or a photo scrim only"))
    if pills > 12:
        out.append(("WARN", "shared/*.css", f"{pills} pill-shaped rules: chips on everything is the delivery-app template look. Keep pills for real taps"))
    return out


LEAKS = ("order aruba", "one kitchen", "shared kitchen", "same kitchen", "other restaurant", "five restaurants", "all five",
         "sister restaurant", "kitchen order")


def leak_findings(items):
    """Victor, 9 Oct 2026: customers must believe each restaurant is its own business. Copy that names
    the restaurants together, a shared kitchen, or another restaurant on one's own menu is a FAIL."""
    site = json.loads((ROOT / "shared/site.json").read_text(encoding="utf-8"))
    names = {}
    for b in site["brands"]:
        names[b["id"]] = json.loads((ROOT / b["id"] / "menu.json").read_text(encoding="utf-8"))["name"]
    out = []
    for where, text in items:
        low = text.lower()
        for w in LEAKS:
            if w in low:
                out.append(("FAIL", where, f"“{text[:70]}” says “{w}”: each restaurant has to read as its own business"))
        here = where.split("/")[0]
        if here in names:   # a restaurant's own page or menu: no other restaurant's name
            for b, n in names.items():
                if b != here and (n in text or n.replace("’", "'") in text):
                    out.append(("FAIL", where, f"names {n}: a restaurant never mentions another one"))
    return out


def main(argv):
    show = "--show" in argv
    files = [a for a in argv if not a.startswith("--")]
    ok = allowed()
    items = file_copy(files) if files else site_copy()
    found = copy_findings(items, ok) + leak_findings(items)
    if not files:
        found += formula_findings() + image_findings() + css_findings()
    if show:
        for w, t in items:
            print(f"  {w}: {t}")
        print()
    seen = set()
    for level, where, msg in sorted(found, key=lambda f: (f[0] != "FAIL", f[1])):
        if (level, where, msg) in seen:
            continue
        seen.add((level, where, msg))
        print(f"{level}  {where}  {msg}")
    fails = sum(1 for f in seen if f[0] == "FAIL")
    warns = len(seen) - fails
    print(f"\n{fails} fail, {warns} warn, {len(items)} pieces of copy read." +
          ("" if fails else " Now look at the screenshots: this script can't see a generated photo."))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
