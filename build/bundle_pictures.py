"""Pictures for bundle dishes (menu.json items with "includes", e.g. Dushi Wok's Family Table):
side-by-side panels cut from the pictures of the dishes it includes, so it always shows exactly those dishes.
Run after replacing any of those pictures:  python3 build/bundle_pictures.py  (then build/thumbs.py)"""
import json, os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, GAP, BG = 780, 446, 6, (21, 19, 15)   # gutters in the app's warm black (#15130F)

def panel(path, w, h):
    im = Image.open(os.path.join(ROOT, path)).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))

site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
for b in site["brands"]:
    m = json.load(open(os.path.join(ROOT, b["id"], "menu.json"), encoding="utf-8"))
    by = {i["id"]: i for i in m["items"]}
    for it in m["items"]:
        parts = [by[x]["img"] for x in it.get("includes", []) if x in by]
        if not 2 <= len(parts) <= 4: continue
        pw = (W - GAP * (len(parts) - 1)) // len(parts)
        out = Image.new("RGB", (W, H), BG)
        for k, p in enumerate(parts):
            out.paste(panel(p, pw, H), (k * (pw + GAP), 0))
        dest = os.path.join(ROOT, it["img"])
        out.save(dest, "WEBP", quality=80, method=6)
        print(f"{b['id']}/{it['id']}: {len(parts)} panels -> {it['img']} ({os.path.getsize(dest) // 1024} KB)")
