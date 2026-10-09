# Open questions for Victor

Loaded into every session through CLAUDE.md. Things only Victor can answer or give.
Ask at most one or two per message, in plain words, with the choice spelled out.
When answered: record the decision in victor.md (dated) and delete it here.

- Papiamento: is `shared/lang/pap.json` right? He said "Oke" on 8 Oct, which may or may not mean yes. Ask once, clearly, with three or four lines to check.
- Book Keeper: the first phone is connected (key "Kitchen App", 8 Oct). Does the chef's own phone need a key too? And did the first real receipt arrive and read well?
- Real photos: one photo of the takeaway box or bag going out, then the signature dishes (Menu tile → dish → Take a new photo). Real photos are the biggest single fix for "looks AI made".
- Gemini credit: Victor said 'Generate images if you have to' (8 Oct), but the prepaid credit is empty (402). Has he added credit in Google AI Studio (Billing, https://ai.studio/projects)? Then make smash-shack sc and co (prompts ready: two thin patties), check each try, `use`, grade (build/grade.py after removing their lines from build/graded.txt), thumbs, og. A real photo would also fix it.
- Registered business name and KvK number, for customer receipts (`receipt` block in site.json). Only if he wants them on receipts.
- Each phone that changes the menu needs its own GitHub key (steps on the chef app's Menu screen). Has he and the chef set it up?
- US dollars: what rate does the driver use (1.75? 1.80?), and is change given in florins? Then the site can say it. Card machine for the driver (CMB wireless Afl. 100/month + fees) or a Sentoo link (Aruba Bank business account) stay his call.
- WhatsApp: all five restaurants send orders to one number, so a customer of two of them ends up in the same chat with the same name. Separate numbers (a prepaid SIM each; the WhatsApp Business app holds two accounts per phone)? Then add `"whatsapp"` per brand in site.json. Until then: what name does the WhatsApp Business profile show? It should not say Order Aruba.
- Web addresses: all five links start with victorfromaruba-stack.github.io/restaurant-/. Own addresses (about $10–15 a year each, e.g. dushiwok.com) would make each look like its own business. Which, if any?
- GitHub repo is public, and the live site also serves the notes (CLAUDE.md, .claude/brain/) that describe the shared kitchen. Private needs GitHub Pro ($4/month) or a free move to Cloudflare Pages (chef app link changes). His call.
- Google: one listing per restaurant (Google allows delivery-only brands from a shared kitchen when each has its own website and its own branded packaging, address hidden, service areas). Each needs its own branded bag sticker or box. Steps sent 9 Oct; once each exists, put its review link in the chef app's after-delivery reply.
