"""Contact sheets: python3 contact.py oranje|drinks"""
import sys, os
from PIL import Image, ImageDraw
SCR = "/tmp/claude-0/-home-claude/9a0b2e7f-5cb4-59c4-ad93-cd3a82fe42c3/scratchpad"
BH = "/home/claude/work/brand-hub"

def load(p):
    return Image.open(p).convert("RGBA")

def sheet_food():
    files = [f"{BH}/oranje-snack/assets/art/{i}.webp" for i in ("bb", "kr", "fk", "mx", "st", "fs")]
    files.append(f"{BH}/taco-brava/assets/art/gt.webp")
    files = [p for p in files if os.path.exists(p)]
    tw, th = 466, 266
    cols = 3
    rows = (len(files) + cols - 1) // cols
    pad = 14
    W = cols * tw + (cols + 1) * pad
    thumb = 110
    H = rows * th + (rows + 1) * pad + thumb + 2 * pad
    im = Image.new("RGB", (W, H), (30, 30, 34))
    for k, p in enumerate(files):
        a = load(p).convert("RGB").resize((tw, th), Image.LANCZOS)
        r, c = divmod(k, cols)
        im.paste(a, (pad + c * (tw + pad), pad + r * (th + pad)))
    # centre-square thumbnails at list size
    y = pad + rows * (th + pad) + pad
    for k, p in enumerate(files):
        a = load(p).convert("RGB")
        s = min(a.size)
        x0 = (a.width - s) // 2; y0 = (a.height - s) // 2
        t = a.crop((x0, y0, x0 + s, y0 + s)).resize((thumb, thumb), Image.LANCZOS)
        im.paste(t, (pad + k * (thumb + pad), y))
    out = f"{SCR}/art_oranje-snack.png"
    im.save(out); print(out)

def sheet_drinks():
    files = [f"{BH}/shared/drinks/{i}.webp" for i in ("ck", "cz", "sp")]
    pad = 20; S = 300
    W = 3 * S + 4 * pad
    H = 2 * S + 3 * pad + 80 + pad
    im = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    # light bg row and dark bg row to check transparency edges
    d.rectangle((0, pad + S + pad // 2, W, pad + 2 * S + pad + pad // 2), fill=(26, 28, 34))
    for k, p in enumerate(files):
        a = load(p).resize((S, S), Image.LANCZOS)
        im.paste(a, (pad + k * (S + pad), pad), a)
        im.paste(a, (pad + k * (S + pad), 2 * pad + S), a)
        sm = load(p).resize((80, 80), Image.LANCZOS)
        im.paste(sm, (pad + k * (S + pad) + S // 2 - 40, 3 * pad + 2 * S), sm)
    out = f"{SCR}/art_drinks.png"
    im.save(out); print(out)

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "oranje"
    sheet_food() if which == "oranje" else sheet_drinks()
