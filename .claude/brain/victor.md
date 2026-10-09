# Victor: how he works and what he decided

Loaded into every session through CLAUDE.md. Newest decisions on top. Stable rules
live in CLAUDE.md; this file is for preferences and decisions that are still settling.
Public repo: nothing private here (no costs, margins, buyer prices, plans, contact details).

## How he works
- Owner, not a coder, works from his phone. Wants ready results and phone screenshots, not code talk.
- Short messages, often one line ("Oke", "Great work but…"). "Oke" alone is not a yes to a specific question: if it matters, ask again with the exact choice.
- Likes it when Claude decides and builds ("you should come up with it yourself"), then shows before/after.
- Money is tight (8 Oct 2026: "Don't have the money now use what you can"). No paid APIs, no Gemini spend, no paid tools without asking.

## Decisions (dated)
- 2026-10-09: 'Drop it if it's Dutch translated it should be all Dutch aka the language the person is using the website that's it there shouldn't be small translation spots': the Spanish/Dutch section names (Platos, Para picar, Uit de frituur…) with small English beside them are gone; section names follow the visitor's language. Read "Drop it" as the answer to "keep or drop the bar under the Smash Shack logo": dropped (shared/logos/smash-shack*.svg; undo with git).
- 2026-10-09: 'Big redesign the website looks a lot like AI build it /design redesign the website 100 times better': the full restyle he must OK first (human-touch rule 5) is OK'd. Shipped the same day: each restaurant its own look, Order Aruba as the app layer.
- 2026-10-09: 'Bring the mix back for those restaurants in specific since these are part of the ghost kitchen concept': the five share one order and one ƒ5 delivery again (site.json "mix": true), shown as the app's perk; a future restaurant outside the ghost kitchen keeps its own order. WhatsApp: 'Put the number we have right now' = keep +297 747 7794.
- 2026-10-09 (later): 'Keep in mind we need to still use all kitchen on website like Uber'. So Order Aruba is a delivery app like Uber Eats: the home page lists all restaurants again, restaurant pages show 'More on Order Aruba', the app name is on the receipt and the WhatsApp. Kept from the morning: one order per restaurant, delivery only, never a word about a shared kitchen.
- 2026-10-09: 'Its delivery only and people also cannot know its all the same kitchen they really need to believe each restaurant is their own business'. Done the same day: no home page, no shared order, no links or add-ons between restaurants, delivery only (pickup gone), receipts and tickets carry the one restaurant's name, "Order Aruba" kept as an internal name only. Rule in CLAUDE.md; qa and check.py enforce it. This replaces the 8 Oct study idea of telling customers it's one kitchen.
- 2026-10-08: 'you can't dine in it's all take out aka delivery': no dine-in, ever. (9 Oct: no pickup either.)
- 2026-10-08: 'On Aruba of course we take usd': cash in florins or US dollars, or bank transfer (site.json `payment`; the Cash tap stays one choice). Rate and change not given yet, so the site names no rate.
- 2026-10-08: Google Business Profile: 'Yes I will'. He opens it himself. (9 Oct: the 'Order Aruba' steps were withdrawn; one listing per restaurant instead.)
- 2026-10-08: 'Generate images if you have to' — OK to spend Gemini credit on pictures that are wrong (not on more generated pictures for their own sake). Credit was empty that day.
- 2026-10-08: His own Book Keeper business ("Victor") made a paid account at his request ('make it into a subscription account'): subscription_status set to active by hand, no Stripe customer, nothing is charged. Stripe webhooks can't overwrite it (they match on the Stripe customer). Billing's 'Manage billing' has no card behind it.
- 2026-10-08: Book Keeper connection switched on ('Yes, switch it on'): migration 026 applied, PR #3 merged. He wants the chef never to log in to Book Keeper: receipts go from the chef app with a key per phone.
- 2026-10-08: Smash Shack patties: he let Claude choose ('The AI made it see which one is the best'). The website now follows the recipe cards: Smash cheeseburger 2 thin patties, Double 4. Tortilla chips: 'They can pick' (either may be used), so the 'contains gluten' label stays. Builder allergens: 'Oke'.
- 2026-10-08: Wants Claude to keep improving the site every day, remember things between sessions, and come up with improvements itself. Site "still feels a bit AI made": that's the main thing to fix.
- 2026-10-08: The chef app is for him and the chef: receipts for customers (sent on WhatsApp), shop receipts into Book Keeper, menu changes from the phone. Book Keeper already has the restaurant as a business.
- 2026-10-08: Direct pushes to `main` of this repo are allowed for finished, checked work. No pull requests needed here. (Book Keeper is different: merging there deploys; ask first.)
- 2026-10-08: Customers pay cash or bank transfer. Last orders 1:30 AM. Frikandel has pork. Videos: free zoom loops for now, real cooking clips only when there's budget.
