# Lessons

Loaded into every session through CLAUDE.md. Gotchas that cost time, so the next
session doesn't pay for them again. One entry: date, what happens, what to do.
Newest on top. When a lesson turns into a rule everyone must follow, move it into
CLAUDE.md and delete it here.

- 2026-10-09 · Browsers break lines after a hyphen or en dash ("stir-/fry", "dine-/in", "35–/50") and `hyphens:none` doesn't stop it. order-app.js `keep()` wraps such words in `<span class="nw">`; use it for any new name or sentence on screen. Never put that span straight inside a flex box next to loose text (a chip's `inline-flex` span ate the space: "Coca-ColaZero"): wrap the label or use plain `esc()` there.
- 2026-10-09 · The restaurant SVG logos had padding and background plates in their viewBox, so they sat indented from the text under them. They're trimmed to their ink now; a new logo needs the same (measure with getBBox in Chromium, drop the full-size background rect).
- 2026-10-09 · With `.nojekyll`, GitHub Pages serves every file in the repo, dot-folders included: /restaurant-/CLAUDE.md and /.claude/brain/victor.md answer 200 on the live site. Anything in the repo is public twice (GitHub and the site). Write internal notes knowing that until the repo is private.
- 2026-10-09 · Public files the restaurant pages load (shared/site.json, shared/lang/*.json) also leak: old phrases like "Also tonight from our kitchen" stayed in the language files after the code stopped using them. `build/lang_keys.py --prune` removes them, and `--check` now fails on them.
- 2026-10-08 · A subagent with fresh eyes (first-time customer at 11 PM, screenshots only, no edits) found 8 real problems after 0 fail from check.py, incl. a one-card rail wasting the first screen and the same dish twice via a bundle picture. Worth one run after any big pass.
- 2026-10-08 · Book Keeper's database (Supabase, free plan) pauses after about a week with no use. Then logged-in pages hang and the chef app's Receipts tile opens a black page; /api/health shows supabaseReachable:false and get_project says INACTIVE. Fix: Victor taps Restore at supabase.com/dashboard/project/orxpuikpgshcajwripxy (Claude's restore_project call was refused as a shared-resource change). Daily use keeps it awake.
- 2026-10-08 · Nobody but the account owner can make a GitHub personal key: there is no API, and Claude's own GitHub access can't be handed to a phone. The template link (?name=&description=&target_name=&expires_in=&contents=write) pre-fills everything except which repository; that one tap stays with Victor.
- 2026-10-08 · A strong model already avoids most slop when the request says 'not AI'; skills earn their keep on consistency, tools and rules for proof and messages. Testing a skill against a no-skill run shows where it makes things worse (the first anti-slop draft made emails longer).
- 2026-10-08 · qa/check_site.py rewrites qa/wa-samples.json with new order numbers on every run. Commit it only when a ticket's content changed.
- 2026-10-08 · A fresh-session routine created from chat starts with no repo, and add_repo wasn't even loaded in it (first daily run, 17:48Z: 'No such tool', clone 403, nothing done). Fix: the routine fires into a dedicated session made with create_session + source_url ("Order Aruba daily worker"), which has the repo attached; the run sends its three lines with PushNotification. A forced run (fire_trigger) still starts a fresh session, so test by send_message to the worker instead.
- 2026-10-08 · Website allergens must cover the recipe card in ops/kitchen/kitchen-data.json (tenders in buttermilk, sesame garnish and oyster sauce were missing until today). qa/check_site.py now compares them; when it fails, add the allergen to menu.json and kitchen-data.json, and tell Victor to fix his private builder too.
- 2026-10-08 · Full-page screenshots show empty boxes where lazy pictures haven't loaded. Scroll through the page first (`shoot.py` does).
- 2026-10-08 · The chef app's menu editor saves menu.json with `JSON.stringify(data, null, 1)`, which matches the repo's format exactly (Python `json.dumps(indent=1, ensure_ascii=False)`, no trailing newline). Keep that format when editing menus by script, or every app save shows a huge diff.
- 2026-10-08 · iPhones can't make WebP from a canvas, so photos from the chef app arrive as `.jpg`. Thumbnails keep the picture's own file name and format (`thumbs/<same name>`); never assume `.webp`.
- 2026-10-08 · The ticket time contains a no-break space ("10:30 PM"). Match times with `\s`, not a plain space.
- 2026-10-08 · `qa/check_site.py | grep …` hides the exit code. Run it on its own, check `rc=$?`, and only commit at 0 problems.
- 2026-10-08 · Playwright must be 1.56.0 here to match the preinstalled Chromium (`pip install playwright==1.56.0`). Don't run `playwright install`.
- 2026-10-08 · Link-preview cards (`build/og/make_og.py`) need fonts loaded from the site: navigate to the local server first, then `document.fonts.load`.
- 2026-10-08 · Gemini answers 402 when the prepaid credit is gone. Don't retry; tell Victor and use what exists.
