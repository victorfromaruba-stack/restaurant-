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

## Next steps, in order
1. **Add CSS for the new pieces** in `shared/order.css` and `shared/hub.css`:

   | Selector | What it is |
   |---|---|
   | `.railnav` | Prev/next arrows. Show them only at 760px and wider, and flip the "next" icon. |
   | `.minis`, `.mini`, `.mini__n`, `.mini__c` | The "Also tonight" cards |
   | `.also__sub` | The line under "Also tonight" |
   | `.sugg--x h3 span` | The small "Still one ƒ5 delivery" note |
   | `.field__help` | The help line under the address field |
   | `.sent__k` | The order number on the sent screen |
   | `.cover__v`, `.cover__pp` | The video and its pause button, at least 44px |
   | `.feat.is-out` | Greyed sold-out Featured card |
   | `.bag.bump`, `.bar__btn.bump` | A small scale bounce when something is added. Respect reduced motion. |
   | `.order__send .sm` / `.lg` | Show "Send order" below 360px and "Send on WhatsApp" above |
   | `.chips--suggest`, `.chip--btn` | Search suggestions |
   | `.qk`, `.qk__c`, `.qk__n` | The home quick-row of 5 restaurants. Also add `<div class="quick" id="oa-quick"></div>` under the search on index.html. |
   | `.shop--fail` | A restaurant card whose menu didn't load |
   | `.sign.is-last` | The sign during last orders |
   | `.iab` | One compact line with a text link |

2. **Contrast and tap sizes (review items 11 and 12):**
   - Colours: WhatsApp green `#1C9E50` → about `#0F7A3D`. Taco Brava `color` in menu.json `#E6246E` → about `#D01C60`. Closed sign text `#5A6E92` → `#8FA0BF`. Field borders → about `#3A5585`.
   - Every tap target needs to be at least 44px. Grow the hit area with a `::after`, not the visible size, on: menu `+` (38px), can `+` (34px), cart −/+ (36px), area chips (40px), "Preview the message" (31px), "Copy the order instead" (33px) and the footer "All restaurants" link (15px).
3. **First screen (review item 8):**
   - Shrink "BON NOCHI." to one line, about 44px.
   - Keep the sign small beside it, and put the 5-restaurant quick-row above the fold.
   - Cut the restaurant cover to about 180px tall on phones.
   - Use a different picture for the Dushi Wok restaurant card. Fried rice currently shows up three times near the top.
4. **Copy:**
   - Hero: "Five restaurants. One kitchen. One ƒ5 delivery."
   - Footer: replace "Some dishes are drawings…" with "Pictures are illustrations."
   - Every menu.json `imageNote`: "Pictures are illustrations." (instead of "Photos show how we plate it").
   - cart.html: don't stack "YOUR ORDER" over the empty state.
5. **Menu data:**
   - Set `"fried": true` on: fries, chips & salsa, egg rolls, wings, sweet & sour chicken, crispy shrimp tacos, nachos, tenders, crispy chicken sandwich, and all Oranje Snack items except saté.
   - Add the `pork` flag to Frikandel special and Mixed snack box. Standard frikandel contains pork; Victor can remove the flag if his brand doesn't.
6. **Small phones (320px):**
   - Hide the "Order Aruba" logo text below 360px so the area chip fits.
   - Move the toast to the top so it doesn't cover Send.
7. **Speed:**
   - Fetch site.json and menu.json in parallel on restaurant pages.
   - Make about 360px thumbnails for menu rows; keep 780px for the dish popup.
   - Add a small service worker: network-first for HTML, JS, CSS and JSON; stale-while-revalidate for images and fonts. Pictures get replaced at the same paths, so don't cache-first them forever.
8. **Languages:** add an EN / PAP / NL / ES switch for screen text only, picked from the phone's language. The WhatsApp ticket stays in English for the kitchen. Victor must review the Papiamento.
9. **Google listing:** add JSON-LD (FoodEstablishment, hours from site.json, area served), plus `robots.txt` and `sitemap.xml`.

## Pictures and videos with Google Gemini
Victor wants Gemini to make the dish pictures and the restaurant videos.
- Victor approved using his existing Gemini key. Use it only from the environment (e.g. `GEMINI_API_KEY` or an already configured Gemini MCP). Never write it into this repo, and don't edit any other project of his to get it.
- In a **cloud** Claude Code session, Google's API is blocked. It only works if the environment has an API credential for `generativelanguage.googleapis.com` (header `x-goog-api-key`, no prefix).
- Check Google's docs for the current image and video model names before calling them.

**The rule that matters most** (CLAUDE.md): every picture must show exactly what its menu text says. Before using any picture, check it against the menu.json `desc`: count, fillings, sauce, bread and portion.

**Pictures to replace first (known wrong):**
- `smash-shack/assets/dishes/sc-hero.webp` (single Smash cheeseburger) shows **two** patties. The new one needs **one** smashed patty, cheddar, lettuce, tomato, onion, pickles, ketchup and mayo on a bun, with no fries.
- `smash-shack/assets/dishes/co.webp` (combo) also shows two patties. The new one needs one patty plus a side of fries.
- `taco-brava/assets/art/gt.webp` reads as flat tostadas. The new one needs three **soft folded** tacos with ground beef, onion, cilantro and salsa.
- The 6 Oranje Snack drawings (`oranje-snack/assets/art/*.webp`).
- The 7 Dushi Wok pictures are all the same top-down black-slate bowl. Vary the angle and dish while keeping one style.

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
- Ideas:
  - Wok tossing chicken fried rice over flame
  - Birria taco dipped in consommé
  - Smash patty pressed on a griddle
  - Fork twirling spaghetti and meatballs
  - Bitterballen lifted out of the fryer
- Tell Victor how many clips and the rough cost before making them, because video costs much more than pictures.

**Label honestly:** until real kitchen photos exist, menus say "Pictures are illustrations."

## How to check before showing Victor
1. `python3 -m http.server 8462 --bind 127.0.0.1` in the repo, then `QA_BASE=http://127.0.0.1:8462/ python3 qa/check_site.py`. It must report 0 problems.
2. Take Playwright screenshots at 390×844 and 320×640 with the clock fixed to an open time (Aruba 11:10 PM = `2026-10-09T03:10:00Z`) and a closed time (2 PM = `2026-10-08T18:00:00Z`).
3. Send a test order through to the WhatsApp preview and paste it into the chef app (`ops/kitchen/`) to confirm it reads every line.
4. Commit to `audit-fixes`, push, and send Victor screenshots. Merge to `main` only when he says so.
