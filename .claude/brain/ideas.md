# Ideas

The improvement backlog. Any session may add ideas; the daily run picks from here.
Format: `- [ ] <impact H/M/L> · <effort S/M/L> · <idea> · done when: <check>`, plus
`(needs Victor)` when it can't be done without him. Tick `[x]` with the date and
commit when shipped, and move shipped lines to the bottom section. Keep the open list
under 25 lines: drop ideas that stopped making sense.

## Open
- [ ] H · S · On Victor's VPS copy only: add the 8 Oct allergens (tenders milk; fried rice, lo mein, Family Table sesame; lo mein, pork stir-fry, Family Table shellfish; bitterballen mustard; chips gluten) to the private kitchen-data builder in ops/kitchen/_build/, so a rebuild keeps them (needs Victor's server) · done when: a rebuilt kitchen-data.json still passes qa/check_site.py
- [ ] M · M · Share a dish: a share button on every dish sheet and links like taco-brava/#d=bt that open that dish (customers hear about us on WhatsApp) · done when: a shared link opens the dish ready to add, in all four languages (idea from a skill test run)
- [ ] H · S · Smash Shack and Taco Brava: the dish under "Start here" is still a glossy generated shot (birria has paint streaks). Needs real photos (needs Victor)
- [ ] M · S · Home "basics" strip (ƒ5 delivery / Free pickup / 10 PM–2 AM) is a three-column feature grid, the template look. Try one plain sentence block · done when: screenshots read as a note from the kitchen, not a feature grid
- [ ] H · L · Real photos, signatures first (needs Victor) · done when: the five signature dishes are real photos
- [ ] M · M · Chef app: send cash sales and receipt photos to Book Keeper (needs Victor: Book Keeper PR #3 merged and migration applied first)
- [ ] M · S · Unused menu.json fields (`kicker`, `headline`, `intro`) are never shown: use the best line of each somewhere real, or remove them
- [ ] L · M · Picture cards: a subtle shared grade (slightly less saturation) so the illustrations look like one set, not five prompts · done when: before/after screenshots look calmer and Victor agrees
- [ ] M · S · 320px check of the chef app's Menu screens (long dish names, the three status buttons)

## Shipped
- [x] 2026-10-08 · H · S · Home: each restaurant card shows a different dish from the one in the dish rail (no photo twice on the home page) · done when: check.py has no "restaurant card shows the same photo" warning
- [x] 2026-10-08 · H · S · Replace the sparkle star in the Order Aruba logo (it's the icon of AI products) · done when: no four-point star on any page
- [x] 2026-10-08 · H · M · Section titles in sentence case and smaller; one loud thing per screen · done when: screenshots show only the page title or the OPEN sign shouting
- [x] 2026-10-08 · M · S · Restaurant page facts as one plain line instead of three pills · done when: no pill that can't be tapped on the restaurant header
- [x] 2026-10-08 · M · S · Each restaurant tagline in its own voice, not the same "A, B & C" shape · done when: check.py has no tagline-shape warning
- [x] 2026-10-08 · M · S · Home subtitle without the staccato triad · done when: check.py has no triad warning
- [x] 2026-10-08 · M · S · "Signature dishes" / "Featured" renamed to "Start with these" (home) and "Start here" (restaurant pages) in all four languages
- [x] 2026-10-08 · New app icon and favicon (OA in a neon frame), new cover loops for Smash Shack (double smash) and Taco Brava (quesadilla) so the cover isn't the same dish as Start here
- [x] 2026-10-08 · M · S · QA starts its own local server, so a dead :8462 never costs time (idea from a skill test run: qa/local_server.py) · done when: qa/check_site.py passes with nothing running on 8462
