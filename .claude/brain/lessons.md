# Lessons

Loaded into every session through CLAUDE.md. Gotchas that cost time, so the next
session doesn't pay for them again. One entry: date, what happens, what to do.
Newest on top. When a lesson turns into a rule everyone must follow, move it into
CLAUDE.md and delete it here.

- 2026-10-08 · Full-page screenshots show empty boxes where lazy pictures haven't loaded. Scroll through the page first (`shoot.py` does).
- 2026-10-08 · The chef app's menu editor saves menu.json with `JSON.stringify(data, null, 1)`, which matches the repo's format exactly (Python `json.dumps(indent=1, ensure_ascii=False)`, no trailing newline). Keep that format when editing menus by script, or every app save shows a huge diff.
- 2026-10-08 · iPhones can't make WebP from a canvas, so photos from the chef app arrive as `.jpg`. Thumbnails keep the picture's own file name and format (`thumbs/<same name>`); never assume `.webp`.
- 2026-10-08 · The ticket time contains a no-break space ("10:30 PM"). Match times with `\s`, not a plain space.
- 2026-10-08 · `qa/check_site.py | grep …` hides the exit code. Run it on its own, check `rc=$?`, and only commit at 0 problems.
- 2026-10-08 · Playwright must be 1.56.0 here to match the preinstalled Chromium (`pip install playwright==1.56.0`). Don't run `playwright install`.
- 2026-10-08 · Link-preview cards (`build/og/make_og.py`) need fonts loaded from the site: navigate to the local server first, then `document.fonts.load`.
- 2026-10-08 · The local test server on :8462 dies when the container restarts. Check `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8462/` before QA and start it again if needed.
- 2026-10-08 · Gemini answers 402 when the prepaid credit is gone. Don't retry; tell Victor and use what exists.
