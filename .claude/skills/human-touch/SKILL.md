---
name: human-touch
description: Make the Order Aruba site (this repo) look and read like a real late-night kitchen in Aruba made it, not a generator. Use it whenever you change, review or add anything a customer sees (pages, menus, dish text, pictures, headings, buttons, colours, icons) and whenever Victor says the site looks fake, AI-made, generic, like a template, cheap, or asks to make it nicer, better or more real, even if he never says "AI". Also use it for the audit in a daily improvement run. Comes with check.py (counts the tells, must say 0 fail) and shoot.py (phone screenshots to look at).
---

# Human touch

Victor, 8 Oct 2026: "it still feels a bit AI made." That is a sales problem, not a
taste problem. People in Aruba order food from people they trust. A page that looks
generated reads like a dropshipping front, and the order goes to the snack down the
road. Every dish picture is an illustration for now, so everything around the
pictures has to carry the trust.

The test for every screen: **would someone hungry in Noord at 11 PM, on a phone,
believe a real kitchen is behind this?**

## How to work

1. **Look first.** `python3 .claude/skills/human-touch/scripts/shoot.py --out /tmp/before`,
   then open every `-top.png` (that's the first screen, the only one most people see).
   Look as a customer: one thumb, late, a bit impatient. Note each thing that makes
   you doubt it's real. `references/tells.md` is the list of what to look for. Read it
   before an audit; the photo tells in particular are easy to stop seeing.
2. **Count.** `python3 .claude/skills/human-touch/scripts/check.py`. FAIL has to reach
   zero before you're done. WARNs are judgment calls: read each one and decide.
3. **Rank by what a customer meets first:** the first screen, then pictures, then
   headings and buttons, then copy inside sheets. One strong change a customer
   notices beats ten they don't.
4. **Fix what's yours** (see the split below). For what only Victor can give, don't
   fake it: write a one-line ask in `.claude/brain/questions.md` (real photos, his
   words, a fact to confirm).
5. **Prove it.** Shoot again with `--out /tmp/after`, put before and after side by
   side, run `python3 qa/check_site.py` (0 problems; it serves the repo itself), and
   send Victor the before/after pair with three plain lines on what changed.

## Yours to change, Victor's to decide

**Yours:** layout, spacing, type sizes, which picture goes where and how it's cropped,
section names, UI words, the wording of dish descriptions (same ingredients, better
words), icons, colours inside the palette, motion.

**Victor's:** prices, which dishes exist, hours, areas, payment, restaurant names and
logos, anything stated as fact about the business, new food pictures (each must show
exactly what its text says), removing anything customers use. Ask, or leave it.

## The rules, and why

1. **Never invent proof.** No reviews, ratings, "since 2019", a chef's name, "family
   recipe", "locally sourced", "100s of happy customers". Made-up proof is the
   surest generator tell, and on a public page it's a lie. An empty spot is better.
   Once Victor confirms a fact, add the exact phrase to `allow.txt` and use it.
2. **True specifics beat adjectives.** "Open till 2 AM", "ƒ5 delivery, Santa Cruz to
   Noord", "House colour helps the driver", "Pay cash or by bank transfer". A generator
   writes "delicious", "fresh", "bold" because it knows nothing. We know the details,
   so we say them. The best source is the kitchen itself: `ops/kitchen/kitchen-data.json`
   holds every dish's recipe card (what goes in, how it's cooked, how it's packed: burger
   box with a deli liner, fries upright in a cup, tenders brined overnight in buttermilk).
   Read the card before rewriting a dish, and when the website and the card disagree
   (a patty count, a sauce, an allergen), that's a finding: allergens get fixed to match
   the card at once, anything else goes to Victor in `questions.md`.
3. **One picture, one place.** The same photo twice on one screen (cover and the
   Featured card under it, or a restaurant card and the dish rail above it) is the
   stock-template look. check.py catches exact repeats; you catch "two different
   pictures of the same burger on the same checkered paper".
4. **Pictures match the text, and real beats pretty.** The chef app's Menu tile takes
   a real photo of the real box in 30 seconds. A slightly messy real photo earns more
   trust than a perfect generated one. Ask for real photos every time it fits, and
   never put up a generated picture that adds things the description doesn't list.
5. **Keep the identity, drop the template.** Ours: the night palette, Archivo, each
   restaurant's own colour, logo and voice, the honest "Pictures are illustrations." The
   template: sparkle icons, every heading in giant capitals, pills on everything,
   identical cards, generic section names like "Featured" and "Popular". Change the
   template, keep the identity. A full restyle needs Victor's yes first.
6. **Write like the person at the counter.** Short, contracted, plain, local.
   `references/voice.md` has the rules and before/after lines from our own pages.
7. **Four languages.** New screen text goes through `tr("...")` (or `data-t`) and into
   `shared/lang/pap.json`, `nl.json`, `es.json`; `python3 build/lang_keys.py` lists
   what's missing. Dish names, descriptions, taglines and the WhatsApp ticket stay
   English. Victor checks Papiamento, so keep new Papiamento short and simple.
8. **Each restaurant is its own business** (Victor, 9 Oct 2026: "people also cannot
   know it's all the same kitchen, they really need to believe each restaurant is their
   own business"). On anything a customer sees (pages, tickets, receipts, link cards,
   Google data, `shared/lang/*.json`, `shared/site.json`): never another restaurant's
   name or link, no cross-selling, no "Order Aruba", no shared or "one" kitchen, no shared
   order. Delivery only. check.py and `qa/check_site.py` fail on these. Honest stays
   honest: the allergen line still says the kitchen handles the big allergens.
9. **Ordering keeps working.** After any change: `qa/check_site.py` = 0 problems. If you
   changed taglines or menus, also run `python3 build/seo.py` and
   `python3 build/og/make_og.py` so Google and the link previews match.

## Files

| File | Use |
|---|---|
| `references/tells.md` | what makes a food site look generated, by pictures, layout and copy, with what we do instead |
| `references/voice.md` | how Order Aruba writes, banned words with reasons, before/after from our pages |
| `scripts/check.py` | counts copy, picture and style tells across the customer site. `--show` prints all copy it read. Pass files to check just those |
| `scripts/shoot.py` | phone screenshots (`--closed`, `--width 320`, `--lang nl-NL`, `--out DIR`); flags broken pictures, sideways scroll, repeats on the first screen |
| `allow.txt` | phrases Victor confirmed as true, so check.py lets them through |

check.py counts what can be counted. It can't see a generated photo or a page that
looks like every other delivery app. That part is your eyes on the screenshots.
