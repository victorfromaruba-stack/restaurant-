# Handoff: continue Order Aruba in Claude Code

Read `CLAUDE.md` first: it holds the rules, the confirmed settings and the file map. This file covers what is in progress.

## Where things are
- **Repo:** github.com/victorfromaruba-stack/restaurant- (public).
- **Live site:** https://victorfromaruba-stack.github.io/restaurant-/ (GitHub Pages serves the `main` branch).
- **Work in progress:** branch `audit-fixes`. `main` is untouched. Merge only after Victor has checked the branch on his phone.
- **Victor:** works from his phone and is not a coder. Send him screenshots and short plain answers, not code.

## What an outside review found, and what's done
An independent review was run on 8 Oct 2026. Every fix below is in `shared/order-app.js` on `audit-fixes`, plus one line in `ops/kitchen/kitchen.js`. `qa/check_site.py` passes (0 problems).

| # | Problem | Status |
|---|---|---|
| 1 | A sent order never cleared, so the next + quietly added to last night's order and kept its number | **Done.** Adding after sending starts a new order with the toast "New order started". A sent order also clears itself after 3 hours. Order again still works. |
| 4 | No last-orders time; a 2 AM time slot; "12 AM" was confusing | **Done in code.** Optional `"lastOrder": "01:30"` in site.json. The sign shows "Last orders 1:30 AM" in the final 30 minutes; after that it switches to pre-orders. The closing minute is no longer a slot, and "12 AM" now reads "Midnight". **The setting is not added yet: ask Victor what time.** |
| 5 | "Other area" was accepted silently | **Done.** A warning shows, and the ticket says "Other area (please confirm)". |
| 6 | Random 4-digit order numbers could repeat | **Done.** Numbers are now the time sent plus 2 letters, e.g. `#2314-K7`. The chef app already reads them. |
| 10 | The sent screen said "Order is in WhatsApp" before the customer pressed Send | **Done.** It now says "One more step: press Send in WhatsApp". |
| 13 | Sold-out dishes still looked orderable in Featured | **Done.** They are greyed and marked "Sold out today". A restaurant's showcase picture skips a sold-out dish. |
| 15 | Cans were filed under whichever restaurant they were added from | **Done.** Cans are one shared "Drinks" group in the cart and on the ticket, and the chef app skips the `*Drinks*` header line. |
| 7 | "No major allergens" on fried food | **Done in code.** The dish sheet now says "No major allergens in the recipe" and adds a cross-contact line. Set `"fried": true` on fried items in menu.json and that line also says "fried in shared oil". **The menu.json flags are not set yet.** |
| 9 | Nothing pointed customers to the other restaurants | **Done.** The cart shows "From our other restaurants · Still one ƒ5 delivery". Restaurant pages end with an "Also tonight from our kitchen" strip. |
| 14 | Search missed "pasta", "coke", "kip", "pollo" and gave unranked results | **Done.** Search knows English, Papiamento, Dutch and Spanish food words, ranks name matches first, and offers tappable suggestions when nothing matches. |
| 17 | The desktop rail couldn't be scrolled with a mouse; the bar showed under popups | **Done in code.** The rail has arrow buttons and the bar hides while a popup is open. **The arrows have no CSS yet.** |
| 22 | Keyboard focus was lost after each tap in the cart; the sign re-announced every minute | **Done.** |
| 24 | Hours were typed into the home page by hand | **Done in code.** `data-oa-hours-t` and `data-oa-hours-d` fill from site.json. **index.html doesn't use them yet.** |
| 25 | The bar total added the ƒ5 fee before the customer chose delivery; "Add 2" counted wrong with extras | **Done.** The bar shows the food total, and the button counts extras ("Add 3 items"). |
| — | Payment method never stated | **Done in code.** Optional `"payment"` in site.json shows above Send. **Ask Victor how customers pay (cash ƒ / US$ / card?). Don't guess.** |
| — | Video covers | **Done in code.** Add `"video": {"src": "...mp4", "poster": "...webp"}` to a menu.json and the cover plays as a silent loop with a pause button. It is skipped when the phone has reduce-motion or data saver on. |

## Session 2 (8 Oct 2026): all nine next steps are done
One commit per step on `audit-fixes`; `qa/check_site.py` reports 0 problems. Victor got phone screenshots after each step.

| # | Step | Result |
|---|---|---|
| 1 | CSS for the new pieces | Done, plus the quick row of 5 restaurants under the search on index.html. |
| 2 | Contrast and 44px taps | Done. Field outlines are `#5574A6` (the suggested `#3A5585` only reached 2.3:1; this is 3:1). Hit areas measured in a browser. |
| 3 | First screen | Done. One-line BON NOCHI., small sign, quick row and first dish above the fold, 180px covers, lo mein on the Dushi Wok card, rail shows one signature per restaurant before family deals. |
| 4 | Copy | Done. Share cards rebuilt with `build/og/make_og.py`. |
| 5 | Menu data | Done. `fried` also on loaded fries, burger combo and Family Table (they contain fried items). Pork flag on frikandel special and mixed box: **Victor to confirm his frikandel has pork.** |
| 6 | Small phones | Done. Toast is at the top on every screen size. |
| 7 | Speed | Done: parallel loading, `build/thumbs.py` thumbnails, `sw.js`. Tested offline with the server switched off. |
| 8 | Languages | Done: `shared/lang/*.json`, `build/lang_keys.py`. **Papiamento is a draft: Victor was sent a numbered list to correct.** |
| 9 | Google listing | Done: `build/seo.py` writes the JSON-LD, `sitemap.xml`, `robots.txt`. robots.txt only works once there's an own domain. A Google Business Profile is the way onto Maps. |

## Still waiting on Victor
- Answered 8 Oct: payment "cash or bank transfer" and last orders 1:30 AM are set in site.json; frikandel has pork (flag stays); videos approved at top quality (Veo 3.1 standard).
- Papiamento corrections → `shared/lang/pap.json`.
- Videos: approved at top quality, but **blocked**: the Gemini prepaid credit ran out (HTTP 402) before any video was made. Victor tops up in Google AI Studio → Billing (about $35 covers 5 clips with retries, plus start frames). Then run the steps under Videos.
- Merge `audit-fixes` into `main` only when he says so.

## Pictures and videos with Google Gemini
Victor wants Gemini to make the dish pictures and the restaurant videos.
- Victor approved using his existing Gemini key. Use it only from the environment (e.g. `GEMINI_API_KEY` or an already configured Gemini MCP). Never write it into this repo, and don't edit any other project of his to get it.
- In a **cloud** Claude Code session, Google's API is blocked. It only works if the environment has an API credential for `generativelanguage.googleapis.com` (header `x-goog-api-key`, no prefix).
- Check Google's docs for the current image and video model names before calling them.

**The rule that matters most** (CLAUDE.md): every picture must show exactly what its menu text says. Before using any picture, check it against the menu.json `desc`: count, fillings, sauce, bread and portion.

**Pictures: done (8 Oct).** All 18 known-wrong or placeholder pictures were remade with `gemini-3-pro-image` and checked against the menu text: Smash cheeseburger and combo (one patty), soft ground-beef tacos, flour-tortilla shrimp tacos, all 6 Oranje Snack dishes, and 7 Dushi Wok dishes with varied angles. The Dushi Wok Family Table is still the earlier composite. 23 tries in total at $0.134 each (about $3). The account ran out of prepaid credit once mid-way (HTTP 402) and worked again later.
To redo one: `python3 build/gemini/make_picture.py make <restaurant> <id>`, look at it, then `... use <file> <restaurant> <id>`, then `python3 build/thumbs.py`, `python3 build/og/make_og.py` and the site check.

**Don't generate:**
- Coke, Coke Zero or Sprite cans. Those are brand logos; photograph the real cans instead.
- People's faces.
- Any text inside the picture.

**One look across the whole site:** night-time, warm light, food filling the frame, the same surface and light per restaurant, and realistic portions for the price. Delivery food can be shown on a plate or in the box it actually comes in, but never with extra food that isn't in the order.

**Picture files:**
- Dish pictures: 780×446 WebP, quality about 80, under 70 KB, at the same path (or update `img` in menu.json).
- Share images: 1200×630 JPG in `shared/og/`.

**Videos:**
- One per restaurant: a 6–8 second loop that starts and ends on the same frame.
- 1280×720 or 960×540, H.264 MP4 with no audio, under 1.5 MB. Use ffmpeg: `-an -movflags +faststart -crf 28`.
- Poster: the first frame as WebP.
- Save as `<restaurant>/video/cover.mp4` and `cover.webp`, then add the `video` field to that menu.json.
- Ready to run (`build/gemini/make_video.py`, prompts in `build/gemini/videos/`), per restaurant:
  1. `python3 build/gemini/make_video.py frame <restaurant>`: a still start frame. Check it (one patty, right dish, no faces, no text).
  2. `python3 build/gemini/make_video.py clip <restaurant> build/gemini/out/<restaurant>-frame-1.jpg`: Veo 3.1 standard, 8 s, starts and ends on that frame ($3.20 per try). Check frames from it (e.g. `ffmpeg -i clip.mp4 -vf fps=1 f%d.png`).
  3. `python3 build/gemini/make_video.py use <restaurant> <clip>`: silent MP4 under 1.5 MB + poster + menu.json `video` field. Then the site check and phone screenshots.
  If the image field is refused (HTTP 400), the older REST shape is `{"bytesBase64Encoded": ..., "mimeType": ...}` instead of `inlineData`.
- Ideas:
  - Wok tossing chicken fried rice over flame
  - Birria taco dipped in consommé
  - Smash patty pressed on a griddle
  - Fork twirling spaghetti and meatballs
  - Bitterballen lifted out of the fryer
- Tell Victor how many clips and the rough cost before making them, because video costs much more than pictures.
- Prices on 8 Oct 2026 (ai.google.dev pricing page), per second at 720p: `veo-3.1-generate-preview` $0.40, `veo-3.1-fast-generate-preview` $0.10, `veo-3.1-lite-generate-preview` $0.05. 5 clips × 8 s on Fast is about $4, or about $8 with one retry each. Use the restaurant's dish picture as both the first and the last frame, so the clip loops cleanly.

**Label honestly:** until real kitchen photos exist, menus say "Pictures are illustrations."

## How to check before showing Victor
1. `python3 -m http.server 8462 --bind 127.0.0.1` in the repo, then `QA_BASE=http://127.0.0.1:8462/ python3 qa/check_site.py`. It must report 0 problems.
2. Take Playwright screenshots at 390×844 and 320×640 with the clock fixed to an open time (Aruba 11:10 PM = `2026-10-09T03:10:00Z`) and a closed time (2 PM = `2026-10-08T18:00:00Z`).
3. Send a test order through to the WhatsApp preview and paste it into the chef app (`ops/kitchen/`) to confirm it reads every line.
4. Commit to `audit-fixes`, push, and send Victor screenshots. Merge to `main` only when he says so.
