"""One look for every generated dish picture, so five restaurants read as one set shot in one kitchen.

Generated pictures come out glossy and over-saturated, each in its own style. This pulls them together:
a touch less colour, slightly warm, blacks lifted a little, a hair less contrast, fine grain (pictures only;
grain in a video doubles its size). It is done once per file and recorded in build/graded.txt, so running
it again never grades a picture twice.

Never run it on a real photo (from the chef app's Menu tile or from Victor): real photos stay as taken.

  python3 build/grade.py --all          every illustration in */assets/dishes and */assets/art not graded yet,
                                        plus the cover videos and their posters
  python3 build/grade.py FILE...        just these files
Then: python3 build/bundle_pictures.py && python3 build/thumbs.py && python3 build/og/make_og.py

Bundle pictures (Family Table) are not graded here: bundle_pictures.py rebuilds them from graded dishes."""
import glob, hashlib, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "build", "graded.txt")
SAT, WARM, LIFT, SOFT, CONTRAST, GRAIN = 0.86, (1.015, 1.0, 0.965), 0.035, 0.05, 0.97, 0.012


def grade(im, seed=7):
    im = ImageEnhance.Color(im.convert("RGB")).enhance(SAT)
    a = np.asarray(im).astype(np.float32) / 255
    a = a * np.array(WARM, np.float32)
    a = LIFT + a * (1 - SOFT)
    a = 0.5 + (a - 0.5) * CONTRAST
    a = a + np.random.default_rng(seed).normal(0, GRAIN, a.shape[:2]).astype(np.float32)[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


def grade_video(path):
    # Same colour steps as grade(), in ffmpeg: saturation, then per channel warm, lift, soften, contrast.
    def ch(k):
        return f"clip((0.5+(({LIFT}+val/255*{WARM[k]}*{1 - SOFT})-0.5)*{CONTRAST})*255\\,0\\,255)"
    tmp = path + ".tmp.mp4"
    vf = f"eq=saturation={SAT},format=rgb24,lutrgb=r={ch(0)}:g={ch(1)}:b={ch(2)},format=yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "27", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, path)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def done():
    if not os.path.exists(LOG):
        return {}
    return dict(line.split()[:2] for line in open(LOG, encoding="utf-8") if line.strip() and not line.startswith("#"))


def bundles():
    out = set()
    site = json.load(open(os.path.join(ROOT, "shared/site.json"), encoding="utf-8"))
    for b in site["brands"]:
        m = json.load(open(os.path.join(ROOT, b["id"], "menu.json"), encoding="utf-8"))
        out |= {i["img"] for i in m["items"] if i.get("includes")}
    return out


def main(args):
    if args == ["--all"]:
        skip = bundles()
        files = [os.path.relpath(f, ROOT) for f in sorted(glob.glob(os.path.join(ROOT, "*/assets/dishes/*.webp")) +
                                                          glob.glob(os.path.join(ROOT, "*/assets/art/*.webp")) +
                                                          glob.glob(os.path.join(ROOT, "*/video/cover.webp")) +
                                                          glob.glob(os.path.join(ROOT, "*/video/cover.mp4")))]
        files = [f for f in files if f not in skip]
    else:
        files = [os.path.relpath(os.path.abspath(f), ROOT) for f in args]
    seen, new = done(), []
    for rel in files:
        path = os.path.join(ROOT, rel)
        if rel in seen:
            continue
        before = os.path.getsize(path)
        if rel.endswith(".mp4"):
            grade_video(path)
        else:
            grade(Image.open(path)).save(path, "WEBP", quality=82, method=6)
        new.append(f"{rel} {sha(path)}")
        print(f"graded {rel}: {before // 1024} KB -> {os.path.getsize(path) // 1024} KB")
    if new:
        with open(LOG, "a", encoding="utf-8") as f:
            if not seen:
                f.write("# Pictures build/grade.py has graded (path, sha256 prefix after grading). Never grade these again.\n")
            f.write("\n".join(new) + "\n")
    print(f"{len(new)} graded, {len(files) - len(new)} already done")


if __name__ == "__main__":
    if not sys.argv[1:] or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
    else:
        main(sys.argv[1:])
