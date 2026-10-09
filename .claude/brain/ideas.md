# Ideas

The improvement backlog. Any session may add ideas; the daily run picks from here.
Format: `- [ ] <impact H/M/L> · <effort S/M/L> · <idea> · done when: <check>`, plus
`(needs Victor)` when it can't be done without him. Tick `[x]` with the date and
commit when shipped, and move shipped lines to the bottom section. Keep the open list
under 25 lines: drop ideas that stopped making sense.

## Open
- [ ] M · S · Diet filters on each restaurant page: vegetarian, no pork, no shrimp, no peanuts (labels already exist; none of the 8 big apps has them, Baymard 2026) · done when: filters work on every restaurant page in 4 languages
- [ ] M · S · Chef app replies name the dish ("Your birria is on the stove now") and go out at the same moments every order (seeing the work raised food ratings 22%, Buell 2017) · done when: confirm/cooking/on-the-way replies use the ticket's first dish
- [ ] M · M · Chef app "busy tonight: +15 min" switch that changes the delivery time the site shows (lateness costs ~3 future orders; widen the window instead of missing it) · done when: one tap saves site.json eta and the site shows it
- [ ] M · S · "It's for someone else": optional name + phone for the person receiving, on the WhatsApp ticket and in the chef app · done when: ticket line parsed by the chef app, qa passes
- [ ] L · M · Count dishes from tickets in the chef app; only after a month of real counts, a "Most ordered this month" mark (the lift only comes when it's true, NBER 2007) · done when: counts visible to Victor; no label before real data
- [ ] M · S · Plainer dish names ("Smash burger combo (burger + fries)", "Fries (side)", "Penne arrabbiata (vegetarian)" read like a till export). Names feed the WhatsApp ticket and the chef app's matching (kitchen-data.json, and Victor's private builder), so ask Victor first (needs Victor) · done when: new names on site, tickets and chef app agree and qa passes
- [ ] H · S · On Victor's VPS copy only: add the 8 Oct allergens (tenders milk; fried rice, lo mein, Family Table sesame; lo mein, pork stir-fry, Family Table shellfish; bitterballen mustard; chips gluten) to the private kitchen-data builder in ops/kitchen/_build/, so a rebuild keeps them (needs Victor's server) · done when: a rebuilt kitchen-data.json still passes qa/check_site.py
- [ ] H · S · Smash Shack: the cheeseburger under "Start here" is still a generated shot with a thick patty. Needs a real photo (needs Victor)
- [ ] H · L · Real photos, signatures first (needs Victor) · done when: the five signature dishes are real photos
- [ ] M · M · Chef app: send cash sales to Book Keeper at Close up (Book Keeper's /api/intake/sales is live; only orders paid cash, same date the order was placed, never bank transfers) · done when: a test order sent twice shows once in Book Keeper

- [ ] M · S · Per-restaurant hours and delivery time in site.json (all five identical is a small tell), only with Victor's real numbers (needs Victor)
- [ ] M · S · Picture look per restaurant: build/grade.py gives all five the same warm grain, which makes them read as one set. A grade per restaurant, regrading from the originals in git history · done when: thumbnails per restaurant look distinct, qa passes

## Shipped
- [x] 2026-10-09 · H · L · Order Aruba as a delivery app like Uber, each restaurant its own business (Victor): home lists restaurants, cards open the dish on its own page, 'More on Order Aruba', one order per restaurant, delivery only, no shared-kitchen wording anywhere public, receipts 'Order Aruba' + restaurant. Earlier the same day: no home or cart page, one order per restaurant, no cross-selling, delivery only, receipts and tickets carry only that restaurant, Google data and link cards per restaurant, public language and settings files cleaned, Order again on the restaurant page; qa and check.py fail on any leak
- [x] 2026-10-08 · H · M · From a fresh-eyes review: restaurant pages open on the menu (no one-card rail), Dushi cover pk (no dish twice), home facts line, rows show the tagline, cart says where the order goes, plain steps, no rail stickers, sentence-case sheet titles, toast at the bottom, stray dots, chip centring, add-ons name their restaurant, pre-order line in the customer's voice
- [x] 2026-10-08 · M · S · Unused menu.json fields kicker/headline removed (intro stays: it's Google's description); chef app Menu screens fixed at 320px (long names wrap)
- [x] 2026-10-08 · M · M · Share a dish: share button on the dish sheet, links like taco-brava/#d=bt open the dish (checked in qa/check_site.py)
- [x] 2026-10-08 · H · M · Home: "How ordering works" (WhatsApp, we confirm, pay cash or transfer) replaces the three-column basics strip; restaurants as compact rows with dish names (home a fifth shorter)
- [x] 2026-10-08 · L · M · One shared grade on every generated picture and cover video (build/grade.py); birria paint dust removed
- [x] 2026-10-08 · M · M · Chef app Receipts: photo straight into Book Keeper's review list, no login (books.js, 72b0161); Book Keeper intake API live
- [x] 2026-10-08 · H · S · Home: each restaurant card shows a different dish from the one in the dish rail (no photo twice on the home page) · done when: check.py has no "restaurant card shows the same photo" warning
- [x] 2026-10-08 · H · S · Replace the sparkle star in the Order Aruba logo (it's the icon of AI products) · done when: no four-point star on any page
- [x] 2026-10-08 · H · M · Section titles in sentence case and smaller; one loud thing per screen · done when: screenshots show only the page title or the OPEN sign shouting
- [x] 2026-10-08 · M · S · Restaurant page facts as one plain line instead of three pills · done when: no pill that can't be tapped on the restaurant header
- [x] 2026-10-08 · M · S · Each restaurant tagline in its own voice, not the same "A, B & C" shape · done when: check.py has no tagline-shape warning
- [x] 2026-10-08 · M · S · Home subtitle without the staccato triad · done when: check.py has no triad warning
- [x] 2026-10-08 · M · S · "Signature dishes" / "Featured" renamed to "Start with these" (home) and "Start here" (restaurant pages) in all four languages
- [x] 2026-10-08 · New app icon and favicon (OA in a neon frame), new cover loops for Smash Shack (double smash) and Taco Brava (quesadilla) so the cover isn't the same dish as Start here
- [x] 2026-10-08 · M · S · QA starts its own local server, so a dead :8462 never costs time (idea from a skill test run: qa/local_server.py) · done when: qa/check_site.py passes with nothing running on 8462
