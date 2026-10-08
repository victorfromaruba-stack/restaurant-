"""Dish pictures with Google Gemini. Every picture must show exactly what its menu text says: look at each try.
  python3 build/gemini/make_picture.py make <restaurant> <id> [--model gemini-3-pro-image]
      one try from build/gemini/prompts/<restaurant>-<id>.txt -> build/gemini/out/<restaurant>-<id>-<n>.<ext> (not committed)
  python3 build/gemini/make_picture.py use <try file> <restaurant> <id>
      after checking it against the menu: 780x446 WebP (under 70 KB) at that dish's "img" path in menu.json.
      Then run python3 build/thumbs.py and python3 build/og/make_og.py, and qa/check_site.py.
The key comes only from the GEMINI_API_KEY environment variable and is sent only as the x-goog-api-key header.
Never put it in this repo. A prompt file's first line is "ref: <picture path>" (style reference) or "ref: none"."""
import base64, json, os, sys, urllib.error, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "build", "gemini")
OUT = os.path.join(HERE, "out")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
MIME = {".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

def make(rest, iid, model):
    lines = open(os.path.join(HERE, "prompts", f"{rest}-{iid}.txt"), encoding="utf-8").read().split("\n", 1)
    ref, prompt = lines[0].replace("ref:", "").strip(), lines[1].strip()
    parts = [{"text": prompt}]
    if ref and ref != "none":
        parts.append({"inline_data": {"mime_type": MIME[os.path.splitext(ref)[1].lower()],
                                      "data": base64.b64encode(open(os.path.join(ROOT, ref), "rb").read()).decode()}})
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    key = os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is not set")
    req = urllib.request.Request(URL.format(model), json.dumps(body).encode(), {"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace").replace(key, "[key]")
        sys.exit(f"HTTP {e.code}: {msg[:600]}" + ("\n-> Add credit in Google AI Studio (Billing) and try again." if e.code == 402 else ""))
    for c in data.get("candidates", []):
        for p in (c.get("content") or {}).get("parts", []):
            blob = p.get("inlineData") or p.get("inline_data")
            if blob and blob.get("data"):
                ext = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(blob.get("mimeType") or blob.get("mime_type"), ".png")
                os.makedirs(OUT, exist_ok=True)
                n = 1 + sum(1 for f in os.listdir(OUT) if f.startswith(f"{rest}-{iid}-"))
                path = os.path.join(OUT, f"{rest}-{iid}-{n}{ext}")
                open(path, "wb").write(base64.b64decode(blob["data"]))
                return print("made", os.path.relpath(path, ROOT), "-> look at it and check it against the menu text")
    sys.exit("no picture came back: " + json.dumps(data.get("promptFeedback") or [c.get("finishReason") for c in data.get("candidates", [])]))

def use(src, rest, iid):
    menu = json.load(open(os.path.join(ROOT, rest, "menu.json"), encoding="utf-8"))
    img = [i for i in menu["items"] if i["id"] == iid][0]["img"]
    im = Image.open(src).convert("RGB"); w, h = im.size; t = 780 / 446
    box = ((w - round(h * t)) // 2, 0, (w + round(h * t)) // 2, h) if w / h > t else (0, (h - round(w / t)) // 2, w, (h + round(w / t)) // 2)
    im = im.crop(box).resize((780, 446), Image.LANCZOS)
    dest, q = os.path.join(ROOT, img), 80
    while True:
        im.save(dest, "WEBP", quality=q, method=6)
        if os.path.getsize(dest) <= 70 * 1024 or q <= 50: break
        q -= 4
    print(f"saved {img} ({os.path.getsize(dest) // 1024} KB). Now: python3 build/thumbs.py && python3 build/og/make_og.py")

if __name__ == "__main__":
    a = sys.argv[1:]
    model = a[a.index("--model") + 1] if "--model" in a else "gemini-3-pro-image"
    if a[:1] == ["make"]: make(a[1], a[2], model)
    elif a[:1] == ["use"]: use(a[1], a[2], a[3])
    else: print(__doc__)
