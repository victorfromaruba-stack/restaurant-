# Pidi customer site: direction (14 Nov 2026, redesign week 2, day 1)

Scope: the customer pages only (home, five restaurant pages, checkout, order status, 404, offline page).
`ops/kitchen/` and `driver/` are untouched (part 2). The order payload, the database calls, the ƒ15 food minimum
and every word of the delivery rules stay exactly as they are.

## Facts the page may state
Late-night delivery in Aruba, every night 10 PM to 2 AM, last orders 1:30 AM. Flat ƒ5 delivery per order, 35-50 min,
Noord to Santa Cruz. Minimum ƒ15 in food. Cash (florins or US dollars) or bank transfer. English, Papiamento, Dutch
and Spanish. Five restaurants, one open soon. Pictures are illustrations (no real kitchen photos exist yet): they are
kept, labelled "Illustration" next to the first one and in the footer, never captioned as a photo of the real dish.
No reviews, no counts, no ratings, no invented claims.

## The world: the counter after 10 PM
Ten nouns: neon tube, the OPEN sign, sodium streetlight, order slip, perforation, foil tray, paper bag, scooter,
warm dark street, florin.

## Chosen direction: Night Slip
A warm-black counter lit by one neon (the PIDI sign, sodium yellow, already the app icon) and paper order slips.
Everything you pay for is a printed slip: the cart, the checkout summary, the order status. Everything else is quiet.
- Swap test: put another delivery app's name on it and it stops being true. The slip, the sign and the 10 PM counter
  are Pidi's.
- Tokens: ground #100E0C, surfaces #181512 / #211D19 / #2B2621, text #F5EDE0, muted #B8AC9C, paper #F2E9D8 with
  ink #1B1611, accent sodium #FFC93C (each restaurant page swaps in its own colour as before), bad #FF8A7A on dark
  and #B3261E on paper, ok #5FD38D. Contrast: muted on ground 8.7:1, paper ink on paper 14:1, ink on sodium 12:1.
- Type: Big Shoulders Display 800-900 (signage caps: the sign, headlines, numbers) and Hanken Grotesk 400-800
  (everything you read; its digits are tabular, so prices line up). Both OFL, self-hosted, subset to Latin-1 + ƒ,
  28 KB + 20 KB. Not Inter, not system-ui, no serif. Scale 12 14 16 18 22 28 40 56 76 (Big Shoulders runs larger).
- Shape: one family. 14px on buttons, fields and pictures, 999px on chips, qty and the status sign; slips are square
  with a perforated edge.
- Motion: calm. ease-out cubic-bezier(.22,1,.36,1); press .97 in 90ms; the sign flickers once when it lights; the
  slip slides up 320ms; skeletons shimmer after 300ms; reduced motion turns all of it off except opacity.
- Signature moment (only one): the cart is a paper slip that prints up from the bottom edge.
- Imagery: the repo's existing illustrations, full-bleed on the first screen, labelled. Added art is typographic
  (the sign, the perforation), never a new picture of food.
- One action always on screen: "Order" in the top bar on the home page, the bag on restaurant pages, and the order
  bar once anything is in the bag.

## References (opened 14 Nov, what is taken)
- Sweetgreen (mobile): one full-bleed food picture and "ORDER" in the header the whole time. Not taken: its cookie wall.
- Wolt (mobile): rounded category tiles, search and basket always reachable. Not taken: its sign-in wall.
- Aruba Webstudio home (demo C, our own benchmark): huge confident type, one pill action, restraint, mono-weight labels.
- Aruba bar brief (13 Nov): a real picture first, one action on screen, light and fast, nothing covering the first screen.

## States designed
Loading (skeleton shaped like the page), empty bag, closed (pre-order wording), sold out, opening soon, menu failed
(retry), offline banner (saved menus stay, ordering waits), minimum not reached (meter and a disabled Continue),
checkout errors in plain words, placing (button busy), order failed (WhatsApp fallback), status page offline,
404 and offline pages.

## Not doing
Purple gradients, glass, three equal feature cards, emoji icons, a hero text strip, numbered section labels, a
carousel hero, fake reviews, discount banners, countdowns, "trusted by" rows, new pictures of food.

# Part 2: the kitchen and the driver (19 Nov 2026, redesign week 2)

Scope: the chef app (preview `ops/kitchen-next/`) and the driver app (preview `driver-next/`). Same Night Slip world,
carried behind the counter and onto the road. Every function and every word the screens had stays; only the look,
the states and a few kitchen-floor habits change. The live `ops/kitchen/` and `driver/` are untouched until Victor's
real test passes.

## The two worlds
- Kitchen: steam, the ticket rail, paper slips, the bell, a wet thumb, bright lights, the pass, timers, foil trays.
  Read from 1-2 m on a tablet or phone. A new order must be heard and seen from across the room.
- Driver: night streets, a scooter, one hand on the phone, glare, the bag, a door, cash and change. The address and
  the money to collect come first, in tall numbers, and the app keeps working in a dead zone.

## Conventions kept (opened 19 Nov; what is taken)
- Toast KDS, https://support.toasttab.com/en/article/Basic-Kitchen-Configuration and
  https://doc.toasttab.com/doc/platformguide/platformKDSOverview.html : a sound for every new ticket, ticket colour by
  age, fulfilled tickets step back. Taken: the age colour and the sound. Not taken: per-station routing (one chef).
- Square KDS, https://squareup.com/help/us/en/article/7944-get-started-with-square-kds-android : a yellow timer and
  a red timer after set minutes, "play sound when new tickets arrive". Taken: yellow at 10 min, red at 20 min, counted
  from when the order came in (a pre-order from when it has to start).
- DoorDash Dasher, https://help.doordash.com/en-us/dashers/article/how-to-accept-an-order and
  https://dasher.doordash.com/en-us/blog/how-to-use-dasher-app : an offer card with a countdown, Accept or decline,
  then pickup and drop-off as separate steps. Taken: the seconds left on the slip, Accept in the thumb zone.
- Uber driver app, https://www.uber.com/us/en/deliver/driver-app/ and
  https://www.uber.com/us/en/blog/introducing-cash-payment-for-deliveries/ : Go online, Accept before time runs out,
  three stages (to the pickup, "I have the order", drop-off), a Cash badge on the offer and the change shown at the
  door. Taken: what to collect is on the offer before Accept, and the change to give is the loudest line at the door.

## Tokens (added to part 1's)
- Same ground, surfaces, text, paper, ink and sodium as the customer site (top of this file). Light is designed:
  warm white ground, white slips, the main button black with yellow text, red text #B3261E.
- Kitchen reds: #E5383B for big fills with large white text (the chef's red since October), #B42A26 under small
  white text (6:1). Green #5FD38D for "ready" with ink text. Pay chips: cash green #17733E, transfer #5E5244,
  US dollars ink with sodium.
- Type: Big Shoulders Display 800-900 for order numbers (64-72 px), minutes, titles and the main buttons; Hanken
  Grotesk for every line you read, digits tabular. Kitchen body 19-22 px, ticket lines 21-25 px; driver money 58-68 px.
- Shape: 14 px on buttons, tiles and fields, 999 px on pills (busy switch, NEW, online); slips are square (4 px)
  with the punched top edge from the customer's order slip.
- Targets: kitchen main buttons 72-80 px high and full slip width; driver buttons 64 px in the bottom bar, 56 px
  for Maps / Waze / Call / WhatsApp.
- Motion: press .97 in 120-140 ms; a new slip's sodium frame breathes (1.4 s), the Orders tile and the yellow bar
  ring; sheets rise 260 ms. Reduced motion: no movement, a thick static frame instead.

## Screens
- Kitchen Orders: a rail of paper slips. New orders first (NEW, a breathing frame, the bell every 20 s until
  someone taps Accept), then what is cooking oldest first, then what waits for a driver. One column on a phone, two
  on a 1024 tablet. Each slip: ORDER and the number big, the minutes big in the corner, pay chip, note, the lines
  exactly as sent, one full-width button for the next step. On every other screen a yellow bar under the top bar
  says "New order 14 · Open" (it pushes the screen down, it never covers Next or the timers).
- Kitchen home: Orders is the sign (yellow when an order waits), Cook an order is a paper slip, the rest quiet tiles.
- Driver: the PIDI sign, the driver's name, an Online pill. The offer is a slip with each drop, what to collect
  and the seconds left; Accept in the bottom bar. Pickup: one slip per order with its bags. Drop: name, area, the
  money slip (collect, pays with, the change on yellow; US dollars on a dark slip), then Maps, Waze, Call and
  WhatsApp above the Delivered bar. Run finished: the cash from each drop.

## States designed
Kitchen: loading (slip-shaped placeholders after 300 ms), empty, nothing to cook now, new order (sound, buzz,
frame, bar, tile), cooking, ready, a driver took it, the driver has it, cancel (asks first), couldn't check with
the last good time and Try again (offline and database error worded apart), the busy switch saving, TEST orders,
price warnings, pre-orders later tonight. Driver: not connected, sign-in error (the name stays), checking for runs,
no offer, offline (a bar; taps saved and sent in order when the signal is back; the run stays on screen), a refused
tap says why, sending (button busy), run finished.

## Not doing
New pictures of food, glass, gradients, emoji, a dashboard of numbers, a map inside the app (Maps and Waze do it),
swipe-to-confirm (a tap is surer with a wet or gloved thumb), sound on the driver app beyond the existing ring.
