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
One licensed kitchen in Aruba, five delivery-only restaurants, one order website.
Customers pick dishes from any restaurant (one shared order), choose delivery or pickup, and send the order on WhatsApp.
Static site, no framework, no build step. Hosted on GitHub Pages from this repo (`main` branch, root folder).

## Restaurants (folder: what it is)
- `dushi-wok/`: Chinese (soft-launch lead)
- `taco-brava/`: Mexican
- `smash-shack/`: smash burgers
- `nonnas-night-in/`: Italian, pasta-led, not pizza
- `oranje-snack/`: Dutch snackbar (bitterballen, kroket, frikandel, saté)
Haus Kitchen (German) and Warung Sranan (Surinamese) were removed on 7 Oct 2026. Don't bring them back unless Victor asks.

## Where things live
- `shared/site.json`: WhatsApp number, opening hours, delivery fee, delivery areas, delivery time text, and which restaurants are `open` / `soon` / `hidden`. Most day-to-day changes happen here. Optional: `"lastOrder": "01:30"` (new orders stop then), `"payWith": ["Cash", "Bank transfer"]` (taps at checkout; the choice goes on the ticket as `Pay: Cash` and the chef app shows it), and `"payment": "…"` (a sentence above Send, only used without `payWith`). Only set these from values Victor gives.
- `<restaurant>/menu.json`: the menu. Names, prices in cents (1295 = ƒ12.95), descriptions, pictures, allergens, flags (shrimp, pork, peanut, spicy, vegetarian), tap options, `"soldOut": true`. Optional: `"fried": true` (adds a shared-oil note), `"cover": "<item id>"` (restaurant cover picture), `"video": {"src","poster"}` (silent cover loop).
- `shared/order-app.js`: the one ordering engine for every page. Shared cart in localStorage `orderaruba.cart.v2`.
- `shared/order.css` (the whole look: one font, Archivo, in `shared/fonts/`; night palette), `shared/hub.css` (home + cart extras). Each restaurant's accent colour comes from `color` in its menu.json. There are no per-restaurant stylesheets or fonts any more.
- `index.html` home, `cart.html` full-page order, `<restaurant>/index.html` thin shell.
- `ops/kitchen/`: the chef app (Prep / Cook an order / Close up), live at https://victorfromaruba-stack.github.io/restaurant-/ops/kitchen/ (not linked from the site, noindex; Victor shares the link with the chef only). Its data builder and the cost/buyer screens are private (see `.gitignore`) and live only on Victor's VPS copy.
- `shared/lang/{pap,nl,es}.json`: screen text in Papiamento, Dutch and Spanish (`{"English": "translation"}`). The language follows the phone, with an EN/PAP/NL/ES switch at the bottom of pages. The WhatsApp ticket, dish names and descriptions stay English. New screen text goes through `tr("...")` in order-app.js (or `data-t` in HTML); `build/lang_keys.py` lists every phrase. Victor reviews the Papiamento.
- `sw.js`: offline cache (network first for pages/code/menus, cached-first for pictures and fonts, refreshed in the background). Bump `CACHE` to clear it.
- `qa/check_site.py`: checks every image, thumbnail, page and language, the Google data, and writes real WhatsApp samples to `qa/wa-samples.json`. Run it after every change; it must say 0 problems.
- `build/thumbs.py`: 360px square thumbnails for menu rows (`<picture folder>/thumbs/<same file name>`, same format: WebP, or JPEG for iPhone photos from the chef app). Run after adding or replacing any dish picture.
- `build/gemini/`: `make_picture.py` + one prompt per dish for Gemini pictures (key only from `GEMINI_API_KEY`, never in the repo). Look at every try and check it against the menu text before `use`.
- `build/grade.py`: one shared colour grade for the generated dish pictures and cover videos (a touch less colour, warm, fine grain), so the five restaurants read as one set. Done once per file, logged in `build/graded.txt`. Never run it on a real photo. `build/art/birria_no_paint.py` took the paint dust off the birria picture.
- `build/bundle_pictures.py`: the Family Table picture is panels of the dishes it includes; rerun after replacing any of them.
- `build/og/make_og.py`: rebuilds the link preview cards in `shared/og/` from the menus. `build/seo.py`: Google data (JSON-LD in the pages), `sitemap.xml`, `robots.txt`; run after changing hours, areas or menus.
- `build/art/`: scripts + SVG sources for the drawn pictures (Oranje Snack dishes, the three cans).
- `shared/og/*.jpg`: link preview cards (home + one per restaurant) used by `og:image` tags. The tags use the full address `https://victorfromaruba-stack.github.io/restaurant-/`; change them (and rerun `build/seo.py`) if the site moves to its own domain.
- `manifest.webmanifest` + `shared/icons/`: "Add to home screen" app icon for Order Aruba: "OA" in a neon frame like the OPEN sign (`build/icons/make_icon.py`). The header logo is the wordmark only. No sparkle star anywhere: it reads as an AI-product icon.

## Features (Oct 2026)
- Home: OPEN sign (lights up during hours), search across all menus, delivery/pickup + area picker in the top bar, "Order again" (last sent order, one tap), "Start with these" dish rail (each restaurant's signature), restaurants as rows like a printed menu index (small picture from menu.json `hero`, a different dish from the rail so no photo shows twice; the dish names; from-price), then "How ordering works" (three steps, then fee, pickup, hours and areas, all from site.json).
- Home also: a row of the five restaurants under the search, desktop arrows on the dish rail.
- Restaurant page: cover photo (or a silent video loop if menu.json has `video`), logo, open status (one plain line, not pills), "Start here" rail (dishes with `style` signature or bundle; the cover must be a different dish), menu rows with + on each photo, "Goes well with" add-ons in the dish sheet, "Also tonight from our kitchen" at the end.
- Share a dish: a share button on every dish (phone share sheet, else the link is copied). Links look like `taco-brava/#d=bt` and open that dish; qa/check_site.py tests one per restaurant.
- Four languages for screen text; works offline for pages already opened.
- Checkout: "When": as soon as possible (while open) or a 15-minute slot tonight; "How will you pay?": Cash or Bank transfer. WhatsApp ticket carries `Time: …` and `Pay: …`; the chef app shows both on the ticket.
- Chef app: paste the WhatsApp order, cook step by step, ready-made customer replies (confirm, on the way / ready for pickup, sold out).
- Chef app also: a **Menu** tile (`ops/kitchen/menu-editor.js`) for Victor and the chef: sold out / back on, restaurant open / opening soon / hidden, change name, price, description, labels, allergens, take a new photo, add or remove a dish. It saves straight to `main` through the GitHub API with a fine-grained key per phone (Contents: Read and write on this repo only, kept in that phone's localStorage `kitchen.github.v1`, never in the repo). Each save reads the latest file first and retries once on a clash. Photos are saved at 780×446 plus the row thumbnail (WebP, JPEG on iPhones). A dish inside a bundle (Family Table) can't be removed there. New dishes have no chef recipe cards: those come from the private data builder on Victor's VPS. `.github/workflows/site-data.yml` reruns `build/seo.py` after any `menu.json` / `site.json` push and commits the Google data.
- Chef app also: a customer receipt from any pasted order (picture or text, sent on WhatsApp; business lines from site.json and an optional `receipt` block with legalName / kvk / address), and a Receipts tile (`ops/kitchen/books.js`) that sends shop-receipt photos straight into Book Keeper's review list (https://bookingkeepingaruba.vercel.app), no login: each phone gets its own key, made by Victor in Book Keeper → Settings → Connected apps and kept only in that phone's localStorage `kitchen.books.v1`, never in the repo. A send with no answer is never retried (it may have arrived).

## Settings Victor confirmed (8 Oct 2026)
- WhatsApp `2977477794` is correct.
- Open every night 10 PM to 2 AM (hours cross midnight; site.json uses `["22:00","02:00"]`).
- Delivery area: Santa Cruz to Noord (Noord, Palm Beach, Eagle Beach, Oranjestad, Paradera, Santa Cruz). Other areas: customer asks on WhatsApp.
- Usual delivery time 35–50 min.
- Last orders 1:30 AM (`"lastOrder": "01:30"`). Customers pay in cash or by bank transfer (`payment`). Frikandel contains pork (keep the flag).

## Rules (keep these)
- Delivery is a flat ƒ5, charged once per order even across restaurants. Pickup is free.
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
- Own domain (e.g. a .com pointed at GitHub Pages) when Victor wants one.

## Run locally
`python3 qa/check_site.py` in the repo folder (needs Python Playwright 1.56.0 and Pillow). It serves the repo itself for the run (`qa/local_server.py`), so there's no server to start or keep alive; `QA_BASE=<url>` checks another server instead. To click around yourself: `python3 qa/local_server.py` or `python3 -m http.server 8462 --bind 127.0.0.1`. The check also compares every dish's allergens with its recipe card in `ops/kitchen/kitchen-data.json`.
