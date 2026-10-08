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
- 2026-10-08: His own Book Keeper business ("Victor") made a paid account at his request ('make it into a subscription account'): subscription_status set to active by hand, no Stripe customer, nothing is charged. Stripe webhooks can't overwrite it (they match on the Stripe customer). Billing's 'Manage billing' has no card behind it.
- 2026-10-08: Book Keeper connection switched on ('Yes, switch it on'): migration 026 applied, PR #3 merged. He wants the chef never to log in to Book Keeper: receipts go from the chef app with a key per phone.
- 2026-10-08: Smash Shack patties: he let Claude choose ('The AI made it see which one is the best'). The website now follows the recipe cards: Smash cheeseburger 2 thin patties, Double 4. Tortilla chips: 'They can pick' (either may be used), so the 'contains gluten' label stays. Builder allergens: 'Oke'.
- 2026-10-08: Wants Claude to keep improving the site every day, remember things between sessions, and come up with improvements itself. Site "still feels a bit AI made": that's the main thing to fix.
- 2026-10-08: The chef app is for him and the chef: receipts for customers (sent on WhatsApp), shop receipts into Book Keeper, menu changes from the phone. Book Keeper already has the restaurant as a business.
- 2026-10-08: Direct pushes to `main` of this repo are allowed for finished, checked work. No pull requests needed here. (Book Keeper is different: merging there deploys; ask first.)
- 2026-10-08: Customers pay cash or bank transfer. Last orders 1:30 AM. Frikandel has pork. Videos: free zoom loops for now, real cooking clips only when there's budget.
