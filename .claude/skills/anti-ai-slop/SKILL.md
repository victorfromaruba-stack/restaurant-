---
name: anti-ai-slop
description: Find and remove "AI slop", the tells that make a website, app screen, menu, email, social post, document or picture look machine-made, and replace them with specific, true, human work. Use it whenever you build, write, restyle or review anything people will see, and whenever someone says it looks AI-made, generated, fake, generic, like a template or ChatGPT, cheap or soulless, or asks to make it more real, more human or less AI. That holds even if they never say "slop". Also use it before showing your own drafts of copy or UI. Comes with slop_check.py (counts the tells in files, a URL or plain text) and shoot.py (phone-first screenshots).
---

# Anti AI slop

People spot generated work in seconds, and once they do, they stop trusting it. For a
small business that's the whole game: a page that looks like every other template reads
as a scam, a dropshipping front, or a place that doesn't care. The order or the booking
goes somewhere else.

Slop isn't "made with AI". It's work that is **generic** (it could sit unchanged on a
competitor's site), **unearned** (it claims things nobody showed: "award-winning",
"passionate", five stars) or **unlooked-at** (nobody checked it on a phone, or checked that
the picture matches the words). The cure is specific, true detail and a person's eye,
not more decoration.

**The test for every sentence, section and picture:** could it appear, unchanged, on
another business's page? If yes, it's slop. Replace it with something only this business
could say, or cut it.

## How to work

1. **Look first.** `python3 <skill>/scripts/shoot.py <folder or URL> --out /tmp/before`, then
   open the `-390-top.png` shots: the first screen on a phone is all most people ever see.
   Look as the real customer would: one thumb, a bit impatient, deciding whether to trust it.
2. **Count.** `python3 <skill>/scripts/slop_check.py <files, folder, --url or --text>`.
   FAIL must reach zero. Read every WARN and decide; some are fine in context.
3. **Collect the true details before you write a word.** Read what the project already
   knows: its README or CLAUDE.md, data files (menus, prices, recipes, opening hours),
   the owner's own messages. Real specifics are the raw material: names, numbers,
   places, times, how the thing is made or packed, what it costs, what's included.
   Never invent them. A made-up specific ("Captain Mike has 30 years at sea") is worse
   than a generic line, because it's a lie that looks like a fact.
4. **Fix in the order people meet things.** First screen, then pictures, then headings and
   buttons, then body text. One change people notice beats ten they don't.
5. **What only the owner can give, ask for.** Real photos, a real quote from a real
   customer (with permission), the founder's own sentence, a fact to confirm. Keep these
   as a short, plain list. Leave the spot empty or honest until then.
6. **Prove it.** Shoot again (`--out /tmp/after`), compare before and after side by side,
   run the project's own checks, and show the person the before/after pair with a few
   plain lines on what changed and why.

When the project has its own brand or voice rules (a brand skill, a style guide, a
CLAUDE.md), those decide the look. This skill decides what counts as slop.

## The rules, and why

1. **Never invent proof.** No reviews, ratings, star rows, customer counts, "since 2015",
   awards, "trusted by", stock-name testimonials ("Sarah M., California"), fake urgency
   ("only 3 spots left", "12 people viewing"). Readers know the trick, and on a business
   page it's simply false. Once the owner confirms a fact, pass the phrase to
   `slop_check.py --allow` and use it.
2. **Specific beats impressive, and few beats all.** "Leaves 4:30 PM from the dock behind
   the fish market, back after dark" sells a sunset sail better than "unforgettable sunset
   adventures". Adjectives (amazing, stunning, delicious, premium) are what a writer
   reaches for when they know nothing. But specific doesn't mean complete: pick the two or
   three details this reader needs right now and leave the rest where it's used (the
   product, the menu, the FAQ). A message that lists every true feature is a brochure,
   and brochures read generated too.
3. **Write like a person talking.** Contractions, short sentences, plain verbs, sentence
   case, no em dashes, no staccato triads ("Relax. Unwind. Experience."), no "not just X,
   it's Y", no rhetorical-question openers. `references/copy.md` has the full list with
   reasons and before/after examples.
4. **Kill the template furniture.** Sparkle icons, purple-to-pink gradients, gradient
   text, glass cards with glows, pills on everything, emoji as icons, centred everything,
   "Why choose us" three-card grids, "Learn more" buttons, pulsing buttons. See
   `references/visual.md`. Keep the brand's real identity; remove the generator defaults.
5. **One picture, one place, and it shows the real thing.** The same photo twice on a
   page is the stock-site look. A generated photo that adds things the text doesn't
   list (or shows the wrong dish, the wrong boat, the wrong room) breaks trust the moment
   the real thing arrives. A slightly messy real photo beats a perfect generated one.
   See `references/images.md`.
6. **Say less.** Generated pages pad: three features where there's one, a FAQ nobody
   asked, a "Ready to get started?" section. Cut what the reader doesn't need to decide.
7. **Don't break what works.** Accessibility, contrast, tap sizes, translations, and the
   actual function (ordering, booking, paying) stay intact. A less-sloppy page that no
   longer takes orders is a failure.

## Messages: emails, notifications, onboarding, posts

One message, one job. Open with the one thing the reader should do or know now ("If you
only do one thing today, snap a receipt"), give it in their words, then stop. Put the
details where they'll be used: the screen, the menu, the help page. A welcome email that
tours every feature reads like a generated brochure, however true each line is. Most
messages land under 150 words; longer needs a reason. `references/copy.md` has examples.

## When you're writing from scratch

Draft, then do a slop pass before you show it: run `slop_check.py --text "..."` (or on the
file), cut every adjective that a fact could replace, read it aloud once. If a line would
fit any business, rewrite it with something only this one has, or delete it.

## Files

| File | Read when |
|---|---|
| `references/copy.md` | writing or fixing any words: banned words with reasons, rhythms, before/after |
| `references/visual.md` | pages and app screens: layout, colour, type and icon tells, and what to do instead |
| `references/images.md` | pictures: generated-photo tells, honesty, briefing a photo or an image model |
| `references/food.md` | restaurants, menus, delivery and ordering sites |
| `scripts/slop_check.py` | counts the tells in files, a folder, a URL (`--url`) or text (`--text`); `--allow facts.txt`, `--show`, `--json` |
| `scripts/shoot.py` | phone-first screenshots of a folder or URL; flags broken pictures, sideways scroll, repeats on the first screen |

The script counts what can be counted. It can't see that a photo is generated, that a
page looks like every other template, or that a line is true. That part is your eyes and
the owner's facts.
