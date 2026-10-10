"""Small square pictures for the menu rows: <picture folder>/thumbs/<same file name>, 360x360, centre crop.
Same format as the picture (WebP, or JPEG for photos the chef app saved from an iPhone).
It also writes each dish's average colour into its menu.json ("ph": "#7A5B3C", right after "img"): the colour a
picture's box shows while the picture loads, so there is never a grey box (brief 3.5).
Run from the repo folder after adding or replacing any dish picture:  python3 build/thumbs.py
Only the colours, no new thumbnails:                                   python3 build/thumbs.py --ph
(qa/check_site.py fails when a thumbnail or a colour is missing or no longer matches its picture.
The chef app's Menu tile writes both itself when it saves a new photo.)"""
import json, os, sys
from PIL import Image, ImageStat

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

def average(img):
    """The picture's average colour, as "#RRGGBB" (the plain mean of every pixel; the chef app works it out the same way)."""
    im = Image.open(os.path.join(ROOT, img)).convert("RGB")
    im.thumbnail((96, 96), Image.BOX)   # each small pixel is the mean of the pixels it covers
    return "#%02X%02X%02X" % tuple(round(c) for c in ImageStat.Stat(im).mean)

def menus():
    site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
    return [os.path.join(ROOT, b["id"], "menu.json") for b in site["brands"]]

def dish_pictures():
    seen = []
    for f in menus():
        m = json.load(open(f, encoding="utf-8"))
        for it in m["items"]:
            if it.get("kind") != "drink" and it["img"] not in seen:
                seen.append(it["img"])
    return seen

def with_ph(item, ph):
    """The same dish with "ph" right after "img" (key order kept, so a save shows only the colour that changed)."""
    out = {}
    for k, v in item.items():
        if k != "ph":
            out[k] = v
        if k == "img":
            out["ph"] = ph
    return out

def write_colours():
    """Every dish picture's colour into its menu.json, in the repo's format: indent 1, UTF-8, no newline at the end
    (the format the chef app saves in, so its saves never show a huge diff)."""
    cache = {}
    for f in menus():
        text = open(f, encoding="utf-8").read()
        m = json.loads(text)
        m["items"] = [with_ph(it, cache.setdefault(it["img"], average(it["img"]))) if it.get("kind") != "drink" else it
                      for it in m["items"]]
        new = json.dumps(m, indent=1, ensure_ascii=False)
        if new != text:
            open(f, "w", encoding="utf-8").write(new)
            print("colours:", os.path.relpath(f, ROOT))

if __name__ == "__main__":
    if "--ph" not in sys.argv:
        for img in dish_pictures():
            out = make(img)
            print(os.path.relpath(out, ROOT), os.path.getsize(out) // 1024, "KB")
    write_colours()
