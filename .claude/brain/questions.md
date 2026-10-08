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
