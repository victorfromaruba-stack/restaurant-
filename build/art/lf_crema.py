"""Loaded fries: the recipe card finishes them with a sour-cream zig-zag under the scallion, the picture had none.
Draws the zig-zag onto the picture (scallion stays on top), so the picture shows what the menu says.
  python3 build/art/lf_crema.py [out.webp]   reads the picture as it was before (git 85dedc9), writes over it by default"""
import io, math, random, subprocess, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIC = "smash-shack/assets/dishes/lf.webp"
src = subprocess.run(["git", "-C", ROOT, "show", "85dedc9:" + PIC], capture_output=True, check=True).stdout
im = Image.open(io.BytesIO(src)).convert("RGB")
W, H = im.size
a = np.asarray(im).astype(np.float32)
rnd = random.Random(7)

# the pile: roughly an ellipse; the zig-zag runs corner to corner across it, slightly slanted
cx, cy, rx, ry = 395, 222, 215, 175
passes = 6
pts = []
for i in range(passes + 1):
    t = i / passes
    y = cy - ry * 0.70 + t * ry * 1.45 + rnd.uniform(-12, 12)
    half = rx * rnd.uniform(0.52, 0.74) * math.sqrt(max(0.0, 1 - ((y - cy) / (ry * 1.02)) ** 2))
    x = cx + (half if i % 2 else -half) + rnd.uniform(-20, 20) + (y - cy) * 0.22
    pts.append((x, y))

def catmull(p, n=900):
    out = []
    p = [p[0]] + p + [p[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(p[-2])
    return out

path = catmull(pts)
S = 4
mask = Image.new("L", (W * S, H * S), 0)
d = ImageDraw.Draw(mask)
phase = rnd.uniform(0, 6)
for i, (x, y) in enumerate(path):
    w = 4.2 + 1.2 * math.sin(i / 260.0 + phase) + 0.5 * math.sin(i / 70.0)   # a hand-squeezed line is never even
    wob = 1.8 * math.sin(i / 110.0) + 0.8 * math.sin(i / 37.0) + 0.5 * math.sin(i / 9.0)
    X, Y = (x + wob) * S, (y + wob * 0.6) * S
    d.ellipse([X - w * S, Y - w * S, X + w * S, Y + w * S], fill=255)
mask = mask.resize((W, H), Image.LANCZOS)

# scallion sits on top of the cream: no cream (and no cream shadow) on green pixels
r, g, b = a[..., 0], a[..., 1], a[..., 2]
green = ((g > r + 18) & (g > b + 18) & (g > 80)).astype(np.uint8) * 255
green = np.asarray(Image.fromarray(green).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.7))).astype(np.float32) / 255
top = 1 - green

m = np.asarray(mask).astype(np.float32) / 255 * top
shadow = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).transform((W, H), Image.AFFINE, (1, 0, -2.5, 0, 1, -4)).filter(ImageFilter.GaussianBlur(3.0))).astype(np.float32) / 255
out = a * (1 - 0.55 * (shadow * (1 - m) * top)[..., None])

# the cream as a soft rounded bead: shaded from its own height, light from the top left like the photo
hgt = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2))).astype(np.float32) / 255
hgt = np.sqrt(np.clip(hgt, 0, 1)) * m
gy, gx = np.gradient(hgt)
k = 5.0
n = np.dstack([-gx * k, -gy * k, np.ones_like(hgt)])
n /= np.linalg.norm(n, axis=2, keepdims=True)
L = np.array([-0.45, -0.65, 0.62], np.float32); L /= np.linalg.norm(L)
Hh = L + np.array([0, 0, 1], np.float32); Hh /= np.linalg.norm(Hh)
diff = np.clip((n * L).sum(2), 0, 1)
spec = np.clip((n * Hh).sum(2), 0, 1) ** 38
base = np.array([238, 234, 222], np.float32)
cream = base[None, None, :] * (0.72 + 0.34 * diff)[..., None] + 255 * 0.55 * spec[..., None]
cream = cream * 0.93 + a * 0.07          # thin edges let a little of the cheese through
noise = np.random.default_rng(3).normal(0, 3.0, (H, W, 1)).astype(np.float32)   # the same fine grain as build/grade.py
cream = cream + noise
out = out * (1 - m[..., None]) + cream * m[..., None]
res = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, PIC)
res.save(dst, "WEBP", quality=86, method=6) if dst.endswith(".webp") else res.save(dst)
print("wrote", dst)
