# Pidi v2

Since 10 Oct 2026 `/driver/` opens v2: the old v1 pages (`index.html`, `run.html`, `cash.html`, `dispatch.html`, `help.html`) only send the phone on to `v2/` (keeping `?…` and `#…`), and the installed app starts at `v2/`. The v1 scripts stay in the repo, unused. `driver/v2/status/` sends an old customer link on to `/order/`. Merge this to `main` only after a TEST order has gone through end to end. `qa/check_staff.py` tests the staff screens with fake database answers.

This talks to the live bookkeeping database at `https://cdkopyphjvfxjqhasrae.supabase.co`. The only change to that database is one paste. It creates `pidi_` tables and functions in `public` and does not touch bookkeeping tables, auth, storage, roles, or extensions.

There is no service role key, no Edge Function, and no signing key. Do not go looking for them.

## Apply in this order

**1. One line, then paste.** In `driver/v2/supabase/PIDI_SETUP.sql`, replace `PUT_8_DIGIT_ADMIN_PIN` with an 8-digit admin PIN. That is the only edit. Paste the file into the Supabase SQL editor and run it. Running it twice is safe. If you leave the placeholder, or the PIN is not 8 digits, the paste still finishes and the editor shows a notice. A PIN already stored is not replaced. If `extensions.crypt` is missing the file stops and does not turn anything on.

**2. Then the anon key.** Put it in `driver/v2/config.js` and commit it. The URL is already there. The URL and the anon key are public. Never commit a service role key or a signing JWK (this setup does not use them).

v2 stays on "Not connected yet" until that key is set and `pidi_ping()` answers. Opening `/driver/v2/` or `/driver/admin/` before that does not call the database.

**3. Then the admin screen.** Open `/driver/admin/` on your phone. Enter the admin PIN (it stays on that screen only, it is not saved on the phone). Set the kitchen PIN. Add each driver: name, phone, PIN. Remove a driver who is not out on a run. Kitchen and driver PINs are 4 to 8 digits. The driver signs in with their name (`Ari`) and their PIN. Do not commit these PINs.

Five wrong admin PINs lock admin checks for 5 minutes. There is one admin, so the lock is global. Five wrong kitchen PINs lock the kitchen the same way. Five wrong tries lock that driver only. The other drivers can still sign in. Until a lock ends, the right PIN is refused too: "Too many tries. Wait 5 minutes."

## What you still give the other tool

`driver/v2/CLAUDE_REALTIME_PROMPT.md` is the paste for the kitchen app and the customer checkout. Those folders are not edited here.

## Try a daytime order

Hours are 10:00 PM to 2:00 AM Aruba time. For a test in the afternoon, in the SQL editor:

```sql
update public.pidi_settings set value = 'flag' where key = 'hours_mode';
```

Set it back to `reject` when the test is over. `flag` keeps the order and marks it outside hours.

Kitchen: sign in with the kitchen PIN, Accept, Cooking, then Ready on each restaurant's bag. The order goes to a driver when every bag is ready. An online driver gets the offer for 45 seconds. The first Accept wins. A second order joins that run when it is ready, or due within 10 minutes, and the drop is under 3 km from the first. A run holds at most 2 orders. Pickup lists the bags per restaurant. Offers refresh when a driver opens the offer list, so no cron job is required.

One order can include several restaurants. The ƒ24 minimum is the food in the whole cart. Delivery is one fee: ƒ5 when every dish is from Dushi Wok, Taco Brava, Smash Shack, Nonna's Night In, or Oranje Snack. ƒ10 when any dish is from a partner restaurant. Those amounts are `fee_own` (500) and `fee_partner` (1000) in `pidi_settings`.

The customer link is `/driver/v2/status/#t=` plus the public token from `pidi_place_order`. A second order can be `&u=`.

## Local proof

```bash
python3 driver/v2/supabase/tests/run_local.py
```

Needs local Postgres. It does not call Supabase. It applies the file twice, checks a dummy bookkeeping table is unchanged, then runs the order as the `anon` role.
