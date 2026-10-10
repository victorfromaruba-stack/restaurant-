# How Pidi writes

The test: **would the person at the counter say it out loud, to a customer, at 11 PM?**
If not, rewrite it.

Customers read in English, Papiamento, Dutch and Spanish, often on a phone, often in
a second language. Short sentences and common words get read right the first time.

## The rules

- **Facts over adjectives.** We know when we open, the areas, the price, what's in the
  dish and how it's cooked. Say those. Leave "delicious" to the picture. Numbers beat
  adjectives: "ƒ3.55 more food to order", "The driver brings ƒ19.05 change."
- **Pidi talks like the person at the counter**: short, plain, specific, calm, and says
  what happens next. It never jokes about money, fees or errors. Restaurants get their
  own voice in their taglines; Pidi's voice is the same everywhere.
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
- **Each restaurant is its own business.** A restaurant's own copy never names another
  restaurant, and nothing a customer sees names a shared kitchen or an owner (Victor,
  9 Oct 2026). The app is Pidi (never its old name, Order Aruba). Never "partner",
  "sister", "own restaurant", "our restaurants" or "our kitchen". A mixed order is
  "delivered together", never "made together".
- **Hours: "Late night from 10 PM".** No closing time, no last-orders time, no "until
  2 AM" anywhere, in any language, until Victor's permit is confirmed.
- **Nothing is charged on Pidi.** Never "charged" or "waived": "You pay ƒ5 delivery
  once.", "One ƒ5 delivery for your whole order."
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
| Hot. Fresh. Fast. | Cooked to order, delivered in 45–60 min. |
| Three wok mains in one order — enough for the table. | Three wok mains in one order. Enough for the table. |
| Smash burgers, tenders & loaded fries (and four more taglines in the same shape) | Thin patties, smashed hard on the flat-top |
| Signature dishes | Start with these |
| Featured | Start here |
| Experience the authentic taste of Aruba's best tacos! | Birria tacos with a cup of consommé to dip. Late night from 10 PM. |
| Open until 2 AM | Late night from 10 PM |
| Minimum order not reached | ƒ3.55 more food to order |
| Great news! Mix and match your favourites! | One ƒ5 delivery for your whole order. |
| The restaurant couldn't take this order | We couldn't take this order. We're sorry. |
| Your order is being processed | Dushi Wok and Taco Brava are making your food. |
| Bestseller / Fan favourite | House dish |
| Our passionate chefs craft every dish with love. | (nothing, until Victor gives us a true sentence) |

## Where words live

- Screen text: `tr("...")` in `shared/order-app.js`, or `data-t` in the HTML, plus a
  line in each of `shared/lang/pap.json`, `nl.json`, `es.json`. Run
  `python3 build/lang_keys.py` to see what's missing.
- Restaurant taglines and dish text: `<restaurant>/menu.json` (English only).
- After changing taglines or dishes: `python3 build/seo.py` and
  `python3 build/og/make_og.py`, then `qa/check_site.py`.
