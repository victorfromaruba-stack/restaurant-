"""Every English phrase the site shows, in page order: the keys for shared/lang/<code>.json.
  python3 build/lang_keys.py            prints the list
  python3 build/lang_keys.py --check    lists phrases missing from pap/nl/es, and old ones the site no longer shows
                                        (qa/check_site.py runs this too)
  python3 build/lang_keys.py --prune    removes those old phrases from the language files (they are public, so a
                                        phrase from an old version of the site shouldn't stay readable there)"""
import json, os, re, sys, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def js_string(lit):
    return json.loads('"' + lit.replace("\\'", "'") + '"')

def keys():
    out = []
    def add(k):
        k = k.strip() if k else k
        if k and k not in out: out.append(k)
    js = open(os.path.join(ROOT, "shared/order-app.js"), encoding="utf-8").read()
    # string literals inside tr( ... ), ternaries included
    for m in re.finditer(r"\btr\(", js):
        i, depth = m.end(), 1
        while depth and i < len(js):
            c = js[i]
            if c == '"':
                j = i + 1
                while js[j] != '"': j += 2 if js[j] == "\\" else 1
                lit = js[i + 1:j]
                compared = re.search(r"[=!]==\s*$", js[max(0, i - 6):i])   # s.mode === "delivery" is code, not text
                if depth == 1 and not compared: add(js_string(lit))
                i = j
            elif c in "({[": depth += 1
            elif c in ")}]": depth -= 1
            i += 1
    # word lists that go through tr() as variables
    for name in ("DAY_NAMES",):
        arr = re.search(name + r" = \[([^\]]*)\]", js).group(1)
        for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', arr): add(js_string(lit))
    for name in ("ALLERGEN_NAMES", "FLAG_NAMES"):
        obj = re.search(name + r" = \{([^}]*)\}", js).group(1)
        for lit in re.findall(r':\s*"((?:[^"\\]|\\.)*)"', obj): add(js_string(lit))
    for name in ("OTHER", "OTHER_NOTE"):
        add(js_string(re.search(r"var " + name + r' = "((?:[^"\\]|\\.)*)"', js).group(1)))
    for one, many in re.findall(r'plural\([^,]+,\s*"([^"]+)",\s*"([^"]+)"\)', js): add(one); add(many)
    # menu words shown through tr(): section titles, cuisines, picture note
    site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
    add(site.get("payment"))
    for v in site.get("payWith", []): add(v)
    for b in site["brands"]:
        m = json.load(open(os.path.join(ROOT, b["id"], "menu.json"), encoding="utf-8"))
        add(m["cuisine"]); add(m.get("imageNote"))
        for sec in m["sections"]: add(sec["title"])
    # fixed words in the HTML files
    for p in sorted(glob.glob(os.path.join(ROOT, "*/index.html"))):
        h = open(os.path.join(ROOT, p), encoding="utf-8").read()
        for m in re.finditer(r'<(\w+)([^>]*)\bdata-t(?:="([^"]*)")?([^>]*)>([^<]*)<', h):
            add(m.group(3) or m.group(5))
        for m in re.finditer(r'<\w+([^>]*)data-t-attr="([^"]+)"([^>]*)>', h):
            attrs = m.group(1) + m.group(3)
            for a in m.group(2).split(","):
                v = re.search(a + r'="([^"]*)"', attrs)
                if v: add(v.group(1))
        for v in re.findall(r'data-oa-fee-t="([^"]+)"', h): add(v)
    return out

if __name__ == "__main__":
    ks = keys()
    if "--prune" in sys.argv:
        for code in ("pap", "nl", "es"):
            f = os.path.join(ROOT, "shared/lang", code + ".json")
            raw = open(f, encoding="utf-8").read(); d = json.loads(raw)
            keep = {k: v for k, v in d.items() if k in ks or k.startswith("_")}
            for k in d:
                if k not in keep: print(f"{code}: removed {k!r}")
            open(f, "w", encoding="utf-8").write(json.dumps(keep, indent=1, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
        sys.exit(0)
    if "--check" in sys.argv:
        bad = 0
        for code in ("pap", "nl", "es"):
            f = os.path.join(ROOT, "shared/lang", code + ".json")
            d = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
            miss = [k for k in ks if not d.get(k)]
            for k in miss: print(f"{code}: missing {k!r}")
            old = [k for k in d if k not in ks and not k.startswith("_")]
            for k in old: print(f"{code}: no longer on the site {k!r} (run --prune)")
            bad += len(old)
            for k in d:
                for v in re.findall(r"\{\w+\}", k):
                    if v not in d[k]: print(f"{code}: {k!r} lost {v}"); bad += 1
            bad += len(miss)
        print(f"{len(ks)} phrases, {bad} problem(s)"); sys.exit(1 if bad else 0)
    for k in ks: print(k)
