# How Order Aruba writes

The test: **would the person at the counter say it out loud, to a customer, at 11 PM?**
If not, rewrite it.

Customers read in English, Papiamento, Dutch and Spanish, often on a phone, often in
a second language. Short sentences and common words get read right the first time.

## The rules

- **Facts over adjectives.** We know the hours, the areas, the price, what's in the
  dish and how it's cooked. Say those. Leave "delicious" to the picture.
- **Contract.** We're, it's, don't, you'll. A page with no contractions sounds like a form.
- **No em dashes.** A full stop or a comma. Two sentences are fine.
- **Sentence case** for headings and buttons. Buttons say what happens next:
  "Send on WhatsApp", "Add", "Order again".
- **Each restaurant has its own voice.** Dushi Wok is quick and hot, Taco Brava is
  about the birria and the dip, Smash Shack about the flat-top, Nonna's about a slow
  night in, Oranje Snack about the fryer and Dutch snackbar habits. Don't stamp one
  sentence shape on all five.
- **Papiamento is a greeting and a wink, not a translation trick.** A "Bon nochi." or
  "Danki!" works because it's how people talk here. Full Papiamento screens come from
  `shared/lang/pap.json`, which Victor checks.
- **Each restaurant is its own business.** Never name another restaurant, a shared
  kitchen, or "Order Aruba" on anything a customer sees (Victor, 9 Oct 2026).
- **Never invent proof.** No ratings, reviews, years, names, sourcing claims.
- **Dish descriptions: what's in it, then how it comes.** Ingredients in the order you'd
  see them, then the one detail that matters ("with a cup of consommé", "cut on a
  bias, with mustard"). The description must match the picture and the recipe.

## Words with reasons

<!-- These are checked by scripts/check.py. -->
- mouthwatering, delectable, scrumptious, tantalizing: say the ingredient instead.
- indulge, treat yourself, satisfy your cravings: tell people what they get, not how to feel.
- culinary, gastronomic, journey, experience: nobody orders an experience at midnight.
- elevate, crafted, handcrafted, artisan, gourmet: agency words, and our prices are snackbar prices.
- perfectly, perfection: say what was done ("crisp edges"), not that it was perfect.
- authentic: prove it with a detail, or drop it.
- fresh: true, but on every line it stops meaning anything. Three times on the site, at most.
- favourites: filler. Name the dish.

## Before and after, from our own pages

| Before | After |
|---|---|
| Hot. Fresh. Fast. | Cooked to order, delivered in 35–50 min. |
| Three wok mains in one order — enough for the table. | Three wok mains in one order. Enough for the table. |
| Smash burgers, tenders & loaded fries (and four more taglines in the same shape) | Thin patties, smashed hard on the flat-top |
| Signature dishes | Start with these |
| Featured | Start here |
| Experience the authentic taste of Aruba's best tacos! | Birria tacos with a cup of consommé to dip. Open till 2 AM. |
| Our passionate chefs craft every dish with love. | (nothing, until Victor gives us a true sentence) |

## Where words live

- Screen text: `tr("...")` in `shared/order-app.js`, or `data-t` in the HTML, plus a
  line in each of `shared/lang/pap.json`, `nl.json`, `es.json`. Run
  `python3 build/lang_keys.py` to see what's missing.
- Restaurant taglines and dish text: `<restaurant>/menu.json` (English only).
- After changing taglines or dishes: `python3 build/seo.py` and
  `python3 build/og/make_og.py`, then `qa/check_site.py`.
