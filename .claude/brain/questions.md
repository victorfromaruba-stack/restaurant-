# Open questions for Victor

Loaded into every session through CLAUDE.md. Things only Victor can answer or give.
Ask at most one or two per message, in plain words, with the choice spelled out.
When answered: record the decision in victor.md (dated) and delete it here.

- Papiamento: is `shared/lang/pap.json` right? He said "Oke" on 8 Oct, which may or may not mean yes. Ask once, clearly, with three or four lines to check.
- Book Keeper connection: OK to switch on? It needs one database change on the live Book Keeper (migration 026) and a merge (which deploys). Draft PR: victorfromaruba-stack/bookingkeepingaruba#3.
- Real photos: one photo of the takeaway box or bag going out, then the signature dishes (Menu tile → dish → Take a new photo). Real photos are the biggest single fix for "looks AI made".
- Taco Brava's birria picture has pink and green paint streaks behind it, and Smash Shack's burger has a thick patty, not a thin smashed one. Real photos would fix both.
- One sentence in his own words about why this kitchen exists (for the home page). Only use it if he writes it.
- Registered business name and KvK number, for customer receipts (`receipt` block in site.json). Only if he wants them on receipts.
- Each phone that changes the menu needs its own GitHub key (steps on the chef app's Menu screen). Has he and the chef set it up?
- Smash Shack patties: the kitchen's recipe cards cook the Smash cheeseburger with 2 thin patties and the Double with 4, but the website says 1 and 2. Which is right? I'll make the website match.
- Chips & salsa: are the tortilla chips corn or flour? I marked them 'contains gluten' to be safe; if they're pure corn I'll take it off.
- Allergens: I added milk (tenders), sesame and shellfish (oyster sauce) to Dushi Wok dishes, mustard (bitterballen), gluten (chips) on the website and in the chef app's data. Please make the same change in the recipe builder on your server, or the next rebuild undoes it in the chef app.
