"""Small square pictures for the menu rows: <picture folder>/thumbs/<same file name>, 360x360, centre crop.
Same format as the picture (WebP, or JPEG for photos the chef app saved from an iPhone).
Run from the repo folder after adding or replacing any dish picture:  python3 build/thumbs.py
(qa/check_site.py fails when a thumbnail is missing or no longer matches its picture.)"""
import json, os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE, QUALITY = 360, 76

FORMATS = {".webp": ("WEBP", {"quality": QUALITY, "method": 6}), ".jpg": ("JPEG", {"quality": 80, "optimize": True}),
           ".jpeg": ("JPEG", {"quality": 80, "optimize": True}), ".png": ("PNG", {"optimize": True})}

def thumb_path(img):
    d, f = os.path.split(img)
    return os.path.join(d, "thumbs", f)

def make(img):
    src, out = os.path.join(ROOT, img), os.path.join(ROOT, thumb_path(img))
    im = Image.open(src).convert("RGB")
    s = min(im.size); l, t = (im.width - s) // 2, (im.height - s) // 2
    im = im.crop((l, t, l + s, t + s)).resize((SIZE, SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fmt, opts = FORMATS[os.path.splitext(img)[1].lower()]
    im.save(out, fmt, **opts)
    return out

def dish_pictures():
    site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
    seen = []
    for b in site["brands"]:
        m = json.load(open(os.path.join(ROOT, b["id"], "menu.json"), encoding="utf-8"))
        for it in m["items"]:
            if it.get("kind") != "drink" and it["img"] not in seen:
                seen.append(it["img"])
    return seen

if __name__ == "__main__":
    for img in dish_pictures():
        out = make(img)
        print(os.path.relpath(out, ROOT), os.path.getsize(out) // 1024, "KB")
