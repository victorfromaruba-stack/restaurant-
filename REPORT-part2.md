# Pidi part 2: kitchen and driver screens (19 Nov 2026)

Status (19 Nov, 08:30 AST): previews built and tested, committed on local main; NOT online yet, because the push to
main was refused on this machine (section 7). Then Victor's real test, then the swap (section 6). The live screens
(`ops/kitchen/`, `driver/`) are untouched.

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
of the other, and an order that already rang in one doesn't ring again in the other on that phone). Nothing is
shared between phones, so the chef's tablet running the live app is not affected by a test on Victor's phone.
The driver keeps its sign-in per browser tab, as before.

## 3. Victor's real test (one TEST order, about 10 minutes)

Do it before 10 PM, so no real driver is online to take it. You need the kitchen PIN and your own driver name and
PIN (add yourself as a driver on driver/admin if you aren't one yet).
1. Kitchen preview (tablet or second phone): open https://victorfromaruba-stack.github.io/restaurant-/ops/kitchen-next/,
   tap Orders, type the kitchen PIN, tap Open orders. Leave it open.
2. Driver preview (your phone): open https://victorfromaruba-stack.github.io/restaurant-/driver-next/, sign in,
   tap Go online.
3. Customer site (your phone, a new tab): open https://victorfromaruba-stack.github.io/restaurant-/, add one dish,
   tap Continue, use the name "TEST Victor" and the note "TEST, don't cook", pay Cash, tap Place order.
   Before 10 PM it goes in as a pre-order for tonight.
4. Kitchen preview: the order rings and shows NEW (a pre-order waits under "Later tonight"). Tap Accept, then
   Start cooking, then Food is ready. To cancel it instead: tap "Can't do this order", then "Yes, cancel the
   order" (this works until a driver taps Accept).
5. Driver preview: the offer rings. Tap Accept, then Picked up, then Delivered.
Then tell me "part 2 passed" and the swap goes live (section 6).

## 4. Tests (all with fake answers and invented TEST data; no real order, no PIN typed or read)

| Check | Where | Result |
|---|---|---|
| qa/check_site.py | live site | 511 passed, 0 failed |
| qa/check_api.py | checkout and order page | 146 passed, 0 failed |
| qa/check_kitchen.py | live ops/kitchen/ | 133 passed, 0 failed |
| qa/check_kitchen.py (KITCHEN_DIR=ops/kitchen-next/) | kitchen preview: K1-K16, every function of the chef app, incl. sold out in the Menu tile | 133 passed, 0 failed |
| qa/check_staff.py | live Orders, driver v2, old addresses, live driver offline cache | 113 passed, 0 failed |
| qa/check_staff.py (STAFF_KITCHEN, STAFF_DRIVER = the previews) | K2-K7 and D3-D9 on both previews (old-address and live-cache checks only apply to live) | 91 passed, 0 failed |
| qa/check_part2.py | the listed states on both previews + service-worker rules | 79 passed, 0 failed |
| swap rehearsal: build/swap_part2.py on a scratch copy, then check_staff.py, check_kitchen.py and check_site.py | the live folders as they will be after the swap | 113 + 133 + 511 passed, 0 failed |
| driver/tests/flow.py | v1 run links | red before this work started (tests v1 screens that only forward to v2 since 10 Oct) |

qa/check_part2.py covers, by name: orders arriving (ring, NEW, the lines exactly as sent, minutes), ringing again
after 20 s, the yellow bar on other screens, accept, cooking, ready, a driver takes it, picked up, cancel (asks
first), queue order and the 10-minute colour, slow network (placeholders, then the order), offline (last orders
stay, last good time, Try again), database error (its words, Try again); driver: slow network, offer (ring, numbers,
what to collect, seconds), Accept in the thumb zone, pickup, picked up, cash (collect, pays with, change), Maps /
Waze / Call / WhatsApp above the Delivered bar, offline (bar, the tap waits, the next drop shows, sent once when
back), US dollars, error (a refused tap says why), delivered with the cash per drop, empty, sign-in error; workers:
each preview's worker has only its own folder as scope, the live caches survive, a live page is never run by a
preview worker, no preview file names a live worker or cache or carries a key, and ops/kitchen/, driver/, sw.js
and shared/ are exactly origin/main. Sold out: check_kitchen [12] on the preview (Menu tile, sold out reaches the
order database at once).

Recording: /home/openclaw/premanifest-bot/feed/Pidi-part2-390.mp4 (390 x 844, dark, about 22 s): the kitchen preview
gets a TEST order, Accept, Start cooking, Food is ready; the driver preview takes the run, pickup, the cash drop,
the US-dollar drop, run finished.

Screenshots looked at (390 and 1024, light and dark): kitchen Orders, kitchen home, new order with the bar,
cancel sheet, offline, error, slow; driver offer, pickup, drop with cash, offline, error, done, sign in, empty.

## 5. Skills used
app-ux-craft (every state), design-direction-brief (DIRECTION.md "Part 2"), premium-feel-standard and
web-craft-standard (tokens, motion, targets), make-interfaces-feel-better (tabular numbers, press, no transition:
all), impeccable (Operate mode, craft floor), design-taste-frontend (only its anti-default and dark-mode rules:
the rest is for landing pages), anti-slop-design-audit (below). borrowed-effects is not installed on this machine.
scroll-craft does not apply (no landing page).

Anti-slop audit: no hard fail (contrast checked token by token, focus rings, every async state, no sideways scroll
at 390 per check_staff). Score 90/100: -5 middle dots as the separator in many lines (kept from the live screens,
the chef knows them), -3 the loading placeholders are plain slips, -2 the yellow bar moves the screen down when it
appears (on purpose: it must not cover Next or the timers). Premium scorecard 53/65, lowest item 4.

## 6. The swap to live (after Victor's test passes)
`python3 build/swap_part2.py`, then `python3 qa/check_all.py --local`, look at both live screens, commit and push.
It copies the previews over ops/kitchen/ and driver/v2/ with the live paths and cache names (kitchen-v19,
pidi-driver-v6), copies the two fonts into driver/fonts/, and lets /driver/sw.js keep the database library for
offline use. It stops if kitchen.js, menu-editor.js or books.js changed on live meanwhile. Rehearsed on a copy:
all green (section 4). The preview folders can go in a later commit.

Weight before photos (gzip, what a phone downloads first): kitchen preview 132 KB (live 159 KB), driver preview
57 KB (live 97 KB), both plus the same database library from the CDN. No Lighthouse run this time.

## 7. Open
- Not online yet: the push to main was refused by this machine's permission check (it would have used the
  machine's GitHub login). The work is committed on local main in /home/openclaw/jobs-scratch/restaurant-, ahead
  of origin by the part 2 commits. One `git push origin main` from a session allowed to push puts both previews
  live; GitHub Pages then needs about a minute. After that: open both links at 390 and 1024 once more.
- Victor's real test (section 3): needs the kitchen PIN and his driver PIN, so it is his step.
- The 3 TEST orders left by part 1 are still in the database (cancel them from the kitchen, live or preview).
- driver/tests/flow.py was already red before this work (it tests the v1 screens).
- After the swap: delete ops/kitchen-next/ and driver-next/ once the live screens have run one night.
