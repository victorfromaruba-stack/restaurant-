# Order Aruba — Victor's ghost kitchen website

Victor is the owner. He is not a coder and works from his phone: give him ready-to-use results, not code explanations.

## Memory and skills (read first)
What earlier sessions learned and what Victor decided, loaded into every session:
@.claude/brain/victor.md
@.claude/brain/lessons.md
@.claude/brain/questions.md

Skills in `.claude/skills/`:
- `anti-ai-slop`: the general version for anything people see, in any project (pages, app screens, emails, posts). `human-touch` adds this site's specifics on top.
- `human-touch`: for anything a customer sees. The site must look and read like a real kitchen made it, not a generator (Victor, 8 Oct: "it still feels a bit AI made").
- `brain`: before your final reply, write down what the next session should know (journal, lessons, decisions, ideas, questions).
- `daily-improvement`: one finished, proven improvement a day, picked from `.claude/brain/ideas.md`.

## What it is
One licensed kitchen in Aruba, five delivery-only restaurants. "Order Aruba" is only our internal name.
**To customers each restaurant is its own business** (Victor, 9 Oct 2026: "people also cannot know it's all the same kitchen, they really need to believe each restaurant is their own business"). Each has its own page, its own order, its own WhatsApp ticket and receipt. There is no home page listing them and no shared order. Delivery only: no pickup, no dine-in.
Customers open one restaurant's page, pick dishes and send the order on WhatsApp.
Static site, no framework, no build step. Hosted on GitHub Pages from this repo (`main` branch, root folder).

## Restaurants (folder: what it is)
- `dushi-wok/`: Chinese (soft-launch lead)
- `taco-brava/`: Mexican
- `smash-shack/`: smash burgers
- `nonnas-night-in/`: Italian, pasta-led, not pizza
- `oranje-snack/`: Dutch snackbar (bitterballen, kroket, frikandel, saté)
Haus Kitchen (German) and Warung Sranan (Surinamese) were removed on 7 Oct 2026. Don't bring them back unless Victor asks.

## Where things live
- `shared/site.json`: WhatsApp number, opening hours, delivery fee, delivery areas, delivery time text, and which restaurants are `open` / `soon` / `hidden`. Most day-to-day changes happen here. A restaurant can get its own WhatsApp number: `"whatsapp": "297…"` on its line under `brands` (pages, ticket, receipt and Google data use it). Customers' phones load this file, so no shared name in it. Optional: `"lastOrder": "01:30"` (new orders stop then), `"payWith": ["Cash", "Bank transfer"]` (taps at checkout; the choice goes on the ticket as `Pay: Cash` and the chef app shows it), and `"payment": "…"` (a sentence above Send, only used without `payWith`). Only set these from values Victor gives.
- `<restaurant>/menu.json`: the menu. Names, prices in cents (1295 = ƒ12.95), descriptions, pictures, allergens, flags (shrimp, pork, peanut, spicy, vegetarian), tap options, `"soldOut": true`. Optional: `"fried": true` (adds a shared-oil note), `"cover": "<item id>"` (restaurant cover picture), `"video": {"src","poster"}` (silent cover loop).
- `shared/order-app.js`: the ordering engine for the restaurant pages. One order per restaurant in localStorage `order.<restaurant>.v1` (the old shared bag `orderaruba.cart.v2` moves over once, that restaurant's lines only); "Order again" from `last.<restaurant>.v1`.
- `shared/order.css`: the whole look (one font, Archivo, in `shared/fonts/`; night palette). Each restaurant's accent colour comes from `color` in its menu.json.
- `<restaurant>/index.html`: thin shell (title, description, Google data, link card, its own `manifest.webmanifest` and icon in its folder). `404.html` is what the bare site address shows: there is no home page on purpose.
- `ops/kitchen/`: the chef app (Prep / Cook an order / Close up), live at https://victorfromaruba-stack.github.io/restaurant-/ops/kitchen/ (not linked from the site, noindex; Victor shares the link with the chef only). Its data builder and the cost/buyer screens are private (see `.gitignore`) and live only on Victor's VPS copy.
- `shared/lang/{pap,nl,es}.json`: screen text in Papiamento, Dutch and Spanish (`{"English": "translation"}`). The language follows the phone, with an EN/PAP/NL/ES switch at the bottom of pages. The WhatsApp ticket, dish names and descriptions stay English. New screen text goes through `tr("...")` in order-app.js (or `data-t` in HTML); `build/lang_keys.py` lists every phrase, and `--prune` drops old phrases (these files are public). Victor reviews the Papiamento.
- `sw.js`: offline cache (network first for pages/code/menus, cached-first for pictures and fonts, refreshed in the background). Bump `CACHE` to clear it.
- `qa/check_site.py`: checks every image, thumbnail, page and language, the Google data, that no restaurant names or links another one or a shared kitchen (pages, order sheet, tickets, receipts, public files) and that an order never carries over, and writes real WhatsApp samples to `qa/wa-samples.json`. Run it after every change; it must say 0 problems.
- `build/thumbs.py`: 360px square thumbnails for menu rows (`<picture folder>/thumbs/<same file name>`, same format: WebP, or JPEG for iPhone photos from the chef app). Run after adding or replacing any dish picture.
- `build/gemini/`: `make_picture.py` + one prompt per dish for Gemini pictures (key only from `GEMINI_API_KEY`, never in the repo). Look at every try and check it against the menu text before `use`.
- `build/grade.py`: a colour grade for the generated dish pictures and cover videos (a touch less colour, warm, fine grain), so they look less glossy and generated. Done once per file, logged in `build/graded.txt`. Never run it on a real photo. `build/art/birria_no_paint.py` took the paint dust off the birria picture.
- `build/bundle_pictures.py`: the Family Table picture is panels of the dishes it includes; rerun after replacing any of them.
- `build/og/make_og.py`: rebuilds the link preview cards in `shared/og/` from the menus (one per restaurant, no shared name). `build/seo.py`: Google data (JSON-LD in the pages), `sitemap.xml`, `robots.txt`; run after changing hours, areas or menus.
- `build/art/`: scripts + SVG sources for the drawn pictures (Oranje Snack dishes, the three cans).
- `shared/og/*.jpg`: link preview cards (one per restaurant) used by `og:image` tags. The tags use the full address `https://victorfromaruba-stack.github.io/restaurant-/`; change them (and rerun `build/seo.py`) if the site moves to its own domain.
- "Add to home screen": each restaurant's own icon and name (`<restaurant>/manifest.webmanifest`, `<restaurant>/assets/icon-*.png`). No sparkle star anywhere: it reads as an AI-product icon.

## Features (Oct 2026)
- No home page and no shared order since 9 Oct 2026 (the old home, search and cart page were removed; git history has them). Nothing on a restaurant page names or links another restaurant.
- Restaurant page: cover photo (or a silent video loop if menu.json has `video`), logo, open status (one plain line, not pills), "Order again" (this restaurant's last sent order, one tap), "Start here" rail only when there are 2+ featured dishes (`style` signature or bundle; otherwise the signature dish leads its section, and a section holding only it folds into the next), cover never a featured dish or one inside a bundle picture (`"cover"` in menu.json picks it), menu rows with + on each photo, "Goes well with" add-ons in the dish sheet (its own sides and drinks), and "How ordering works" at the end (three steps, then fee, delivery only, hours, areas, WhatsApp number), since shared dish links land here.
- Share a dish: a share button on every dish (phone share sheet, else the link is copied). Links look like `taco-brava/#d=bt` and open that dish; qa/check_site.py tests one per restaurant.
- Four languages for screen text; works offline for pages already opened.
- Checkout (delivery only): "When": as soon as possible (while open) or a 15-minute slot tonight; delivery area and address; "How will you pay?": Cash or Bank transfer. The WhatsApp ticket starts `*<Restaurant> order* #2314-K7` and carries `Time: …` and `Pay: …`; the chef app shows both on the ticket.
- Chef app: paste the WhatsApp order, cook step by step, ready-made customer replies (confirm, on the way / ready for pickup, sold out).
- Chef app also: a **Menu** tile (`ops/kitchen/menu-editor.js`) for Victor and the chef: sold out / back on, restaurant open / opening soon / hidden, change name, price, description, labels, allergens, take a new photo, add or remove a dish. It saves straight to `main` through the GitHub API with a fine-grained key per phone (Contents: Read and write on this repo only, kept in that phone's localStorage `kitchen.github.v1`, never in the repo). Each save reads the latest file first and retries once on a clash. Photos are saved at 780×446 plus the row thumbnail (WebP, JPEG on iPhones). A dish inside a bundle (Family Table) can't be removed there. New dishes have no chef recipe cards: those come from the private data builder on Victor's VPS. `.github/workflows/site-data.yml` reruns `build/seo.py` after any `menu.json` / `site.json` push and commits the Google data.
- Chef app also: a customer receipt from any pasted order (picture or text, sent on WhatsApp; it carries the restaurant's own name and WhatsApp, plus an optional `receipt` block in site.json with legalName / kvk / address), and a Receipts tile (`ops/kitchen/books.js`) that sends shop-receipt photos straight into Book Keeper's review list (https://bookingkeepingaruba.vercel.app), no login: each phone gets its own key, made by Victor in Book Keeper → Settings → Connected apps and kept only in that phone's localStorage `kitchen.books.v1`, never in the repo. A send with no answer is never retried (it may have arrived).

## Settings Victor confirmed (8 Oct 2026)
- WhatsApp `2977477794` is correct.
- Open every night 10 PM to 2 AM (hours cross midnight; site.json uses `["22:00","02:00"]`).
- Delivery area: Santa Cruz to Noord (Noord, Palm Beach, Eagle Beach, Oranjestad, Paradera, Santa Cruz). Other areas: customer asks on WhatsApp.
- Usual delivery time 35–50 min.
- Last orders 1:30 AM (`"lastOrder": "01:30"`). Customers pay cash in florins or US dollars, or by bank transfer (`payment`, `payWith`). Frikandel contains pork (keep the flag).

## Rules (keep these)
- **Each restaurant stands alone.** On anything a customer sees (pages, order sheet, WhatsApp ticket, receipt, link cards, Google data, `shared/lang/*.json`, `shared/site.json`): never another restaurant's name or link, no cross-selling, no "Order Aruba", no shared or "one" kitchen, no shared order. qa/check_site.py and the human-touch check.py fail on it.
- Delivery only (no pickup, no dine-in). Delivery is a flat ƒ5 per order.
- Coke, Coke Zero and Sprite are separate items at ƒ3. Never ask for the flavour in the note.
- Prices stay low but the food looks expensive. Birria stays at ƒ27; drinks and fries are cheap on purpose.
- One chef shares stock across the brands. Keep 6 to 8 dishes per restaurant.
- Every image must show exactly what its text says. No near-miss photos.
- Choices like "no onion" or "sauce on the side" are taps (options in menu.json), never typed notes. Only offer options the kitchen can do with stock it already has.
- Chef screens use plain words, never codes like DW-wg-MAR. Big photos, one step per screen.
- This repo is public: never commit food costs, buyer prices, margins or business plans.
- Never use VapVap as a sales channel. Don't touch Frank's app.

## Still open
- Real kitchen photos one day: every dish picture is an illustration for now (menus say "Pictures are illustrations."). Keep the same file path or update `img` in menu.json, then run `build/thumbs.py`.
- The three cans are still drawings: photograph the real cans (don't generate brand logos).
- Victor still has to check the Papiamento (`shared/lang/pap.json`).
- Own web address per restaurant when Victor wants them: today all five links start with victorfromaruba-stack.github.io/restaurant-/, which shows they belong together.
- One WhatsApp number for all five: a customer of two restaurants lands in the same chat. Separate numbers when Victor gets them (`"whatsapp"` per brand in site.json).
- The GitHub repo is public, and GitHub Pages (with `.nojekyll`) serves every file, including CLAUDE.md and `.claude/brain/`, which describe the shared kitchen. Making it private needs GitHub Pro or moving hosting (e.g. Cloudflare Pages, free); Victor's call.

## Run locally
`python3 qa/check_site.py` in the repo folder (needs Python Playwright 1.56.0 and Pillow). It serves the repo itself for the run (`qa/local_server.py`), so there's no server to start or keep alive; `QA_BASE=<url>` checks another server instead. To click around yourself: `python3 qa/local_server.py` or `python3 -m http.server 8462 --bind 127.0.0.1`. The check also compares every dish's allergens with its recipe card in `ops/kitchen/kitchen-data.json`.
