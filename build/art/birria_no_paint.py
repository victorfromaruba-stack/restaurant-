"""Taco Brava birria (taco-brava/assets/dishes/bt-hero.webp): fade the pink and lime-green paint dust on the
stone board into the board itself. The generated picture had them; the dish never comes with paint. Done once on
8 Oct 2026 (before build/grade.py); kept so the change can be redone from the git history if needed.
  python3 build/art/birria_no_paint.py SRC DST"""
import sys
import numpy as np
from PIL import Image, ImageFilter
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src).convert('RGB')
a = np.asarray(im).astype(np.float32)
hsv = np.asarray(im.convert('HSV')).astype(np.float32)
h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
H, W = s.shape
xx = np.tile(np.arange(W), (H, 1))
lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
# board: light, low-colour pixels on the stone (not the grey table, which is darker)
board = (s < 0.12) & (v > 0.78)
out = a.copy()
for name, sel in (('pink', (h > 300) & (h < 350) & (s > 0.12) & (v > 0.5) & (xx < 330)),
                  ('green', (h > 55) & (h < 110) & (((s > 0.12) & (v > 0.5)) | ((s > 0.25) & (v > 0.25))) & (xx > 590))):
    m = Image.fromarray((sel * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(2.5))
    m = np.asarray(m).astype(np.float32)[..., None] / 255
    m[..., 0] *= (xx < 330) if name == 'pink' else (xx > 585)
    # board colour next to this streak
    near = board & ((xx < 330) if name == 'pink' else (xx > 560))
    bcol = a[near].mean(0); blum = lum[near].mean(); bstd = lum[near].std()
    slum = lum[sel].mean(); sstd = max(lum[sel].std(), 1)
    # keep the streak's grain as texture, rescaled to the board's brightness and spread
    t = blum + (lum - slum) * (bstd / sstd) * 0.55
    fill = bcol[None, None, :] * (t / blum)[..., None]
    fill = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32)
    out = out * (1 - m) + fill * m
    print(name, int(sel.sum()), 'board', bcol.round(), round(float(blum)), round(float(bstd), 1))
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dst)
