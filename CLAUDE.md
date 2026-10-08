# Order Aruba — Victor's ghost kitchen website

Victor is the owner. He is not a coder and works from his phone: give him ready-to-use results, not code explanations.

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
- `shared/site.json`: WhatsApp number, opening hours, delivery fee, delivery areas, delivery time text, and which restaurants are `open` / `soon` / `hidden`. Most day-to-day changes happen here. Optional: `"lastOrder": "01:30"` (new orders stop then) and `"payment": "…"` (how to pay, shown above Send). Only add these once Victor gives the values.
- `<restaurant>/menu.json`: the menu. Names, prices in cents (1295 = ƒ12.95), descriptions, pictures, allergens, flags (shrimp, pork, peanut, spicy, vegetarian), tap options, `"soldOut": true`. Optional: `"fried": true` (adds a shared-oil note), `"cover": "<item id>"` (restaurant cover picture), `"video": {"src","poster"}` (silent cover loop).
- `shared/order-app.js`: the one ordering engine for every page. Shared cart in localStorage `orderaruba.cart.v2`.
- `shared/order.css` (the whole look: one font, Archivo, in `shared/fonts/`; night palette), `shared/hub.css` (home + cart extras). Each restaurant's accent colour comes from `color` in its menu.json. There are no per-restaurant stylesheets or fonts any more.
- `index.html` home, `cart.html` full-page order, `<restaurant>/index.html` thin shell.
- `ops/kitchen/`: the chef app (Prep / Cook an order / Close up). Its data builder and the cost/buyer screens are private (see `.gitignore`) and live only on Victor's VPS copy.
- `shared/lang/{pap,nl,es}.json`: screen text in Papiamento, Dutch and Spanish (`{"English": "translation"}`). The language follows the phone, with an EN/PAP/NL/ES switch at the bottom of pages. The WhatsApp ticket, dish names and descriptions stay English. New screen text goes through `tr("...")` in order-app.js (or `data-t` in HTML); `build/lang_keys.py` lists every phrase. Victor reviews the Papiamento.
- `sw.js`: offline cache (network first for pages/code/menus, cached-first for pictures and fonts, refreshed in the background). Bump `CACHE` to clear it.
- `qa/check_site.py`: checks every image, thumbnail, page and language, the Google data, and writes real WhatsApp samples to `qa/wa-samples.json`. Run it after every change; it must say 0 problems.
- `build/thumbs.py`: 360px square thumbnails for menu rows (`<picture folder>/thumbs/`). Run after adding or replacing any dish picture.
- `build/gemini/`: `make_picture.py` + one prompt per dish for Gemini pictures (key only from `GEMINI_API_KEY`, never in the repo). Look at every try and check it against the menu text before `use`.
- `build/og/make_og.py`: rebuilds the link preview cards in `shared/og/` from the menus. `build/seo.py`: Google data (JSON-LD in the pages), `sitemap.xml`, `robots.txt`; run after changing hours, areas or menus.
- `build/art/`: scripts + SVG sources for the drawn pictures (Oranje Snack dishes, the three cans).
- `shared/og/*.jpg`: link preview cards (home + one per restaurant) used by `og:image` tags. The tags use the full address `https://victorfromaruba-stack.github.io/restaurant-/`; change them (and rerun `build/seo.py`) if the site moves to its own domain.
- `manifest.webmanifest` + `shared/icons/`: "Add to home screen" app icon for Order Aruba.

## Features (Oct 2026)
- Home: OPEN sign (lights up during hours), search across all menus, delivery/pickup + area picker in the top bar, "Order again" (last sent order, one tap), signature dish rail, restaurant cards.
- Home also: a row of the five restaurants under the search, desktop arrows on the dish rail.
- Restaurant page: cover photo (or a silent video loop if menu.json has `video`), logo, open status, Featured rail, menu rows with + on each photo, "Goes well with" add-ons in the dish sheet, "Also tonight from our kitchen" at the end.
- Four languages for screen text; works offline for pages already opened.
- Checkout: "When": as soon as possible (while open) or a 15-minute slot tonight. WhatsApp ticket carries `Time: …`; the chef app shows it on the ticket.
- Chef app: paste the WhatsApp order, cook step by step, ready-made customer replies (confirm, on the way / ready for pickup, sold out).

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
`python3 -m http.server 8462 --bind 127.0.0.1` in the repo folder, open http://127.0.0.1:8462/, then `python3 qa/check_site.py` (needs Python Playwright).
