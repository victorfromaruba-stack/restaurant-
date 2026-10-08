# Lessons

Loaded into every session through CLAUDE.md. Gotchas that cost time, so the next
session doesn't pay for them again. One entry: date, what happens, what to do.
Newest on top. When a lesson turns into a rule everyone must follow, move it into
CLAUDE.md and delete it here.

- 2026-10-08 · A strong model already avoids most slop when the request says 'not AI'; skills earn their keep on consistency, tools and rules for proof and messages. Testing a skill against a no-skill run shows where it makes things worse (the first anti-slop draft made emails longer).
- 2026-10-08 · qa/check_site.py rewrites qa/wa-samples.json with new order numbers on every run. Commit it only when a ticket's content changed.
- 2026-10-08 · Routine runs start in a fresh session without this repo, so a push gets 403 ("not in this session's authorized repository set"). Fix: call mcp__claude-code-remote__add_repo directly (owner victorfromaruba-stack, repo restaurant-, access push) before cloning. It's already loaded, so ToolSearch won't find it; the first run searched, found nothing and gave up. A forced run (fire_trigger) always starts a fresh session, even for a routine bound to one.
- 2026-10-08 · Website allergens must cover the recipe card in ops/kitchen/kitchen-data.json (tenders in buttermilk, sesame garnish and oyster sauce were missing until today). qa/check_site.py now compares them; when it fails, add the allergen to menu.json and kitchen-data.json, and tell Victor to fix his private builder too.
- 2026-10-08 · Full-page screenshots show empty boxes where lazy pictures haven't loaded. Scroll through the page first (`shoot.py` does).
- 2026-10-08 · The chef app's menu editor saves menu.json with `JSON.stringify(data, null, 1)`, which matches the repo's format exactly (Python `json.dumps(indent=1, ensure_ascii=False)`, no trailing newline). Keep that format when editing menus by script, or every app save shows a huge diff.
- 2026-10-08 · iPhones can't make WebP from a canvas, so photos from the chef app arrive as `.jpg`. Thumbnails keep the picture's own file name and format (`thumbs/<same name>`); never assume `.webp`.
- 2026-10-08 · The ticket time contains a no-break space ("10:30 PM"). Match times with `\s`, not a plain space.
- 2026-10-08 · `qa/check_site.py | grep …` hides the exit code. Run it on its own, check `rc=$?`, and only commit at 0 problems.
- 2026-10-08 · Playwright must be 1.56.0 here to match the preinstalled Chromium (`pip install playwright==1.56.0`). Don't run `playwright install`.
- 2026-10-08 · Link-preview cards (`build/og/make_og.py`) need fonts loaded from the site: navigate to the local server first, then `document.fonts.load`.
- 2026-10-08 · Gemini answers 402 when the prepaid credit is gone. Don't retry; tell Victor and use what exists.
