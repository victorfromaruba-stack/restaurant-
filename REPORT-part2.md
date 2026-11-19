# Pidi part 2: kitchen and driver screens (19 Nov 2026)

Status: previews built and tested; waiting for Victor's real test. The live screens (`ops/kitchen/`, `driver/`)
are untouched. The swap to live is one small commit after his test passes (section 6).

Preview links (GitHub Pages, from `main`):
- Kitchen: https://victorfromaruba-stack.github.io/restaurant-/ops/kitchen-next/
- Driver: https://victorfromaruba-stack.github.io/restaurant-/driver-next/

## 1. What both screens do today (listed from the code before any change)

Every line below must still work in the preview. Section 4 says which test proves it.

### Kitchen (`ops/kitchen/`)
- K1 Home: six tiles. Orders (live count; yellow and pulsing with a new order; red frame when the database couldn't be checked; "Sign in with the kitchen PIN"), Cook an order (open orders count), Prep and Close up (N of M done today), Receipts, Menu. Date in the top bar.
- K2 Orders sign-in: kitchen PIN (4 to 8 numbers), Enter submits, error line, "Checking…" while busy, 12-hour session on this phone, Sign out on this phone, an expired session asks again.
- K3 Orders feed: asked every 8 s on every screen, plus the realtime topic; "Couldn't check for orders" banner with Try again and "last good hh:mm" in the bar; loading; empty ("No orders right now"); "Nothing to cook right now"; screen kept awake on Orders.
- K4 New order: three-tone beep and vibration once per order (seen list kept 2 days), a toast on other screens, the home tile turns yellow and pulses.
- K5 Kitchen busy?: Normal / +15 min / +30 min (+30 asks first), saving state, minutes read from the feed or the public state, a sentence when nothing is cooking.
- K6 Order ticket: order number (or time), TEST mark, note and striped ticket, came-in time and minutes ago, pre-order delivery time and start-cooking time, pay line (cash with change, US dollars with total, transfer in or not yet), customer note, a header per restaurant in its colour with a Ready tick, lines "qty × dish" with options as sent, a red price check (menu price with options; dish not on the menu), Accept, Start cooking (quiet for a pre-order not due yet), "<Restaurant> is ready" / "Food is ready" per restaurant while cooking, "Waiting for a driver", "A driver took it" / "The driver has it", Cook step by step, totals, customer name, phone, area and address, Call and WhatsApp, The transfer came in, Can't do this order (asks first, then cancels).
- K7 Later tonight / Pre-orders for later: sorted by start time, moves up when due.
- K8 Menu copy for the order database: each restaurant's menu and open / soon / hidden, sent when it changed (checked every 10 min) and right after a Menu-tile save; a new sign-in sends all again.
- K9 Cook an order: paste a WhatsApp order (two orders in one paste refused, WhatsApp prefixes stripped), or pick dishes by tile (+ / −, clear, cook these); open orders with replaced flags.
- K10 Order screen: header (time, pay, note, TEST), dishes with recipe cards, steps with photos, timers, drinks, item done, ready screen, customer replies (confirm with the delivery time, cooking, on the way, sold out), receipt (picture, text, save), close and delete (asks first), "Replaces order" banners, "Ticket says…" for a renamed dish, "No recipe card yet".
- K11 Prep and Close up: section jump, tick per day, counts, steps links, untick all (asks first).
- K12 Task screens: steps with photos and timers. K13 Timer tray on every screen: +1 min, stop, done flash.
- K14 Receipts tile: key per phone, receipt photo to Book Keeper, send again, "may have arrived" rule (never retried by itself), disconnect (asks first).
- K15 Menu tile: fine-grained GitHub key per phone, sold out / back on, open / opening soon / hidden (asks first), name, price, description, labels, allergens, new photo, add / remove dish (asks first, bundle guard), save with clash retry, plain errors, disconnect.
- K16 Offline: service worker, saved copy after 3 s of slow network, works offline with the menus, photos warmed, deletes only its own caches.

### Driver (`driver/` opens `driver/v2/`)
- D1 Old addresses (driver/, index, run, cash, dispatch, help, v2/status) forward to v2 or the order page.
- D2 "Not connected yet" banner when the database doesn't answer; Sign in disabled.
- D3 Sign in: name and PIN, error line, session per browser tab.
- D4 Home: driver's name, Online / Offline line, Go online / Go offline in the bottom bar, screen kept awake while online, sound unlocked by the tap.
- D5 Offers: asked every 8 s plus the realtime broadcast; ring and vibration on a new offer; per drop: order number, restaurant, area and name, "Deliver at" for a pre-order, what to collect (cash, US dollars, transfer); countdown that refreshes at 0; Accept (in the bottom bar with one offer), Not this one; "Another driver took that run." / "That run changed…"; empty lines; error line; expired session asks to sign in again.
- D6 Sign out (goes offline first).
- D7 Run, pickup: pickup name, each order number and name with its bags by restaurant and the items, Maps and Waze when the pickup has an address, Picked up.
- D8 Run, drop: "Drop 1 of 2 · Order 12", name, area, "Deliver at", money box (Collect total, Pays with, Give change / Short, delivery included; US dollars: collect in dollars, total; transfer: awaiting or paid, don't collect cash), Google Maps, Waze, Call, WhatsApp with a ready message, address, note, items, Delivered.
- D9 Run finished, Back. Each step starts at the top. Location sent every 15 s during a run. Run asked every 8 s.
- D10 Help: hand over at the door, Call 911, Police 100, WhatsApp, live-location tip.
- D11 Offline: the /driver/ service worker keeps the app; a page never saved says "No internet"; no loops.

Not part of this redesign: `driver/admin/` (Victor's kitchen PIN and drivers screen), `driver/install/`, `driver/setup/`.

### Checks before any change (07:50 AST)
`qa/check_all.py --local`: check_site 511 passed, check_api 146, check_kitchen 133, check_staff 113, 0 failed.
`driver/tests/flow.py`: already red before this work. It tests the v1 run-link screens, which only forward to v2
since 10 Oct (driver/V2_NOTES.md says so); check_staff.py covers v2 instead.

## 2. What changed (previews only)

Kitchen (`ops/kitchen-next/`, a copy of `ops/kitchen/`; kitchen.js, menu-editor.js, books.js and
kitchen-data.json are unchanged copies):
- The Night Slip look from the customer site: warm-black counter, sodium yellow for the next step, order tickets
  as paper slips with the punched edge, Big Shoulders for numbers, times and buttons, Hanken Grotesk for reading.
  Dark designed for the night, light designed for a bright kitchen (the phone's setting picks). `kitchen.css` keeps
  every old rule and re-themes from one token block; a part 2 layer at the end restyles the screens.
- Orders (`live.js`): the order number and the minutes since it came in are big on every slip; the minutes turn
  yellow at 10 and red at 20 (Square and Toast kitchen screens do this); NEW on a new slip with a breathing yellow
  frame; an order nobody accepted rings again every 20 s; on every other screen a yellow bar "New order 14 · Open"
  sits under the top bar until someone accepts (it pushes the screen down, never covers Next or the timers); the
  phone buzzes even before the first tap has unlocked sound; the queue is new orders first, then cooking oldest
  first, then waiting for a driver; one column on a phone, two slips side by side on a 1024 tablet; slip-shaped
  placeholders on a slow first load; "Couldn't check for orders" says whether the phone or the database is out and
  when the last good check was. Every button, word and database call is the same as live.
- Home: Orders is the sign (yellow when an order waits), Cook an order a paper slip, the other four quiet tiles;
  all six fit the first screen of a 1024 tablet.
- Its service worker: scope `ops/kitchen-next/` only, caches `next-kitchen-…`, deletes only its own old ones.

Driver (`driver-next/`, a copy of `driver/v2/`):
- Same look: the PIDI sign in the header, the driver's name, an Online pill, the offer as a paper slip with each
  drop, what to collect and the seconds left; Accept, Picked up and Delivered as the 64 px bottom-bar button; the
  money slip at the door (collect, pays with, the change on yellow; US dollars on a dark slip).
- No signal: a bar at the top, the run stays on screen (this tab keeps its last copy), Picked up and Delivered
  wait on the phone and go out in order when the signal is back. A tap the database refuses now says why (v2 said
  nothing). The button says "Sending…" while it works, so a quick double tap sends once.
- Designed states: checking for runs, no offer, no signal on the offers, sign-in error (the name stays typed),
  run finished with the cash from each drop.
- `config.js` in the preview only points at `driver/v2/config.js` (no address or key copied). Its service worker:
  scope `driver-next/` only, caches `next-driver-…`.

Same phone, two apps: the previews use the same origin, so the kitchen preview shares the kitchen's sign-in and
saved orders on a phone that has both (the formats are unchanged, so nothing breaks; signing out of one signs out
of the other). The driver keeps its sign-in per browser tab, as before.
