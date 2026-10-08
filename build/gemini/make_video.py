"""Restaurant cover videos with Google Veo: an 8-second loop that starts and ends on the same frame.
  python3 build/gemini/make_video.py frame <restaurant>     still start frame (gemini-3-pro-image) -> build/gemini/out/<restaurant>-frame-<n>.<ext>
  python3 build/gemini/make_video.py clip <restaurant> <frame file> [--model veo-3.1-generate-preview]
      Veo clip that begins and ends on that frame -> build/gemini/out/<restaurant>-clip-<n>.mp4 (with sound, not committed)
  python3 build/gemini/make_video.py still <restaurant> <picture>
      free, no Gemini: an 8-second slow push-in and back out on one picture (same first and last frame), then "use" it
  python3 build/gemini/make_video.py use <restaurant> <clip file>
      silent H.264 MP4 (under 1.5 MB) + WebP poster at <restaurant>/video/cover.mp4 / cover.webp, and the "video" field in menu.json
Prompts: build/gemini/videos/<restaurant>.txt ("frame: ..." and "motion: ..."). Look at every frame and clip before "use".
Key only from GEMINI_API_KEY, sent only as the x-goog-api-key header. Veo 3.1 standard costs $0.40 a second (8 s = $3.20)."""
import base64, json, os, re, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "build", "gemini")
OUT = os.path.join(HERE, "out")
API = "https://generativelanguage.googleapis.com/v1beta/"

def key():
    return os.environ.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is not set")

def call(url, body=None):
    req = urllib.request.Request(url if url.startswith("http") else API + url, json.dumps(body).encode() if body is not None else None,
                                 {"x-goog-api-key": key(), "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace').replace(key(), '[key]')[:800]}" +
                 ("\n-> The prepaid credit is used up: add credit in Google AI Studio (Billing), then run this again." if e.code == 402 else ""))

def prompts(rest):
    t = open(os.path.join(HERE, "videos", rest + ".txt"), encoding="utf-8").read()
    return re.search(r"frame:\s*(.*?)\n\s*\n\s*motion:", t, re.S).group(1).strip(), re.search(r"motion:\s*(.*)", t, re.S).group(1).strip()

def next_path(prefix, ext):
    os.makedirs(OUT, exist_ok=True)
    n = 1 + sum(1 for f in os.listdir(OUT) if f.startswith(prefix + "-"))
    return os.path.join(OUT, f"{prefix}-{n}{ext}")

def frame(rest):
    body = {"contents": [{"parts": [{"text": prompts(rest)[0]}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
    data = json.load(call("models/gemini-3-pro-image:generateContent", body))
    for c in data.get("candidates", []):
        for p in (c.get("content") or {}).get("parts", []):
            blob = p.get("inlineData") or p.get("inline_data")
            if blob and blob.get("data"):
                path = next_path(rest + "-frame", ".jpg" if "jpeg" in (blob.get("mimeType") or "") else ".png")
                open(path, "wb").write(base64.b64decode(blob["data"]))
                return print("made", os.path.relpath(path, ROOT))
    sys.exit("no frame came back: " + json.dumps(data.get("promptFeedback")))

def clip(rest, frame_file, model):
    mime = "image/jpeg" if frame_file.lower().endswith((".jpg", ".jpeg")) else "image/png"
    img = {"inlineData": {"mimeType": mime, "data": base64.b64encode(open(frame_file, "rb").read()).decode()}}
    body = {"instances": [{"prompt": prompts(rest)[1], "image": img, "lastFrame": img}],
            "parameters": {"aspectRatio": "16:9", "resolution": "720p", "durationSeconds": "8", "personGeneration": "allow_adult"}}
    op = json.load(call(f"models/{model}:predictLongRunning", body))
    print("started", op.get("name", "?"), flush=True)
    while not op.get("done"):
        time.sleep(10)
        op = json.load(call(op["name"]))
    if op.get("error"): sys.exit("Veo error: " + json.dumps(op["error"])[:600])
    res = op.get("response", {}).get("generateVideoResponse", {})
    samples = res.get("generatedSamples") or []
    if not samples: sys.exit("no video (filtered?): " + json.dumps(res)[:600])
    path = next_path(rest + "-clip", ".mp4")
    open(path, "wb").write(call(samples[0]["video"]["uri"]).read())
    print("made", os.path.relpath(path, ROOT))

def still(rest, picture):
    """A gentle 8 s zoom loop (1.00 -> 1.06 -> 1.00) on one picture. Scaled up first so the zoom doesn't jitter."""
    n = 200   # 8 s at 25 fps
    path = next_path(rest + "-still", ".mp4")
    vf = (f"scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
          f"zoompan=z='1+0.03*(1-cos(2*PI*on/{n}))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1280x720:fps=25")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", picture, "-vf", vf, "-frames:v", str(n), "-c:v", "libx264",
                    "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", path], check=True)
    print("made", os.path.relpath(path, ROOT))
    return path

def use(rest, src):
    d = os.path.join(ROOT, rest, "video"); os.makedirs(d, exist_ok=True)
    mp4, poster = os.path.join(d, "cover.mp4"), os.path.join(d, "cover.webp")
    for crf, w in [(28, 1280), (30, 1280), (30, 960), (32, 960), (34, 960)]:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-an", "-vf", f"scale={w}:-2", "-c:v", "libx264", "-preset", "slow",
                        "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], check=True)
        if os.path.getsize(mp4) <= 1.5 * 1024 * 1024: break
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "72", poster], check=True)
    p = os.path.join(ROOT, rest, "menu.json"); m = json.load(open(p, encoding="utf-8"))
    m["video"] = {"src": f"{rest}/video/cover.mp4", "poster": f"{rest}/video/cover.webp"}
    open(p, "w", encoding="utf-8").write(json.dumps(m, indent=1, ensure_ascii=False))
    print(f"saved {rest}/video/cover.mp4 ({os.path.getsize(mp4) // 1024} KB, crf {crf}, {w}px) + cover.webp; menu.json has \"video\"")

if __name__ == "__main__":
    a = sys.argv[1:]
    model = a[a.index("--model") + 1] if "--model" in a else "veo-3.1-generate-preview"
    if a[:1] == ["frame"]: frame(a[1])
    elif a[:1] == ["clip"]: clip(a[1], a[2], model)
    elif a[:1] == ["still"]: still(a[1], a[2])
    elif a[:1] == ["use"]: use(a[1], a[2])
    else: print(__doc__)
