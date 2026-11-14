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
