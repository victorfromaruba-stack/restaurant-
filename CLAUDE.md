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
- `shared/site.json`: WhatsApp number, opening hours, delivery fee, delivery areas, delivery time text, and which restaurants are `open` / `soon` / `hidden`. Most day-to-day changes happen here.
- `<restaurant>/menu.json`: the menu. Names, prices in cents (1295 = ƒ12.95), descriptions, pictures, allergens, flags (shrimp, pork, peanut, spicy, vegetarian), tap options, `"soldOut": true`.
- `shared/order-app.js`: the one ordering engine for every page. Shared cart in localStorage `orderaruba.cart.v2`.
- `shared/order.css` (the whole look: one font, Archivo, in `shared/fonts/`; night palette), `shared/hub.css` (home + cart extras). Each restaurant's accent colour comes from `color` in its menu.json. There are no per-restaurant stylesheets or fonts any more.
- `index.html` home, `cart.html` full-page order, `<restaurant>/index.html` thin shell.
- `ops/kitchen/`: the chef app (Prep / Cook an order / Close up). Its data builder and the cost/buyer screens are private (see `.gitignore`) and live only on Victor's VPS copy.
- `qa/check_site.py`: checks every image and page and writes real WhatsApp samples to `qa/wa-samples.json`. Run it after every change.
- `build/art/`: scripts + SVG sources for the drawn pictures (Oranje Snack dishes, taco `gt`, the three cans).
- `shared/og/*.jpg`: link preview cards (home + one per restaurant) used by `og:image` tags. The tags use the full address `https://victorfromaruba-stack.github.io/restaurant-/`; change them if the site moves to its own domain.
- `manifest.webmanifest` + `shared/icons/`: "Add to home screen" app icon for Order Aruba.

## Features (Oct 2026)
- Home: OPEN sign (lights up during hours), search across all menus, delivery/pickup + area picker in the top bar, "Order again" (last sent order, one tap), signature dish rail, restaurant cards.
- Restaurant page: cover photo, logo, open status, Featured rail, menu rows with + on each photo, "Goes well with" add-ons in the dish sheet.
- Checkout: "When": as soon as possible (while open) or a 15-minute slot tonight. WhatsApp ticket carries `Time: …`; the chef app shows it on the ticket.
- Chef app: paste the WhatsApp order, cook step by step, ready-made customer replies (confirm, on the way / ready for pickup, sold out).

## Settings Victor confirmed (8 Oct 2026)
- WhatsApp `2977477794` is correct.
- Open every night 10 PM to 2 AM (hours cross midnight; site.json uses `["22:00","02:00"]`).
- Delivery area: Santa Cruz to Noord (Noord, Palm Beach, Eagle Beach, Oranjestad, Paradera, Santa Cruz). Other areas: customer asks on WhatsApp.
- Usual delivery time 35–50 min.

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
- Real kitchen photos to replace the drawings (Oranje Snack x6, Ground beef street tacos, the 3 cans). Keep the same file path or update `img` in menu.json.
- Own domain (e.g. a .com pointed at GitHub Pages) when Victor wants one.

## Run locally
`python3 -m http.server 8462 --bind 127.0.0.1` in the repo folder, open http://127.0.0.1:8462/, then `python3 qa/check_site.py` (needs Python Playwright).
