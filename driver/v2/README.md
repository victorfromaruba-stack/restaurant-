# Pidi v2

Not live. The driver app people use today is still `/driver/` (v1). Do not merge this until a test order has gone through. Do not link v2 from v1.

This talks to the live bookkeeping database at `https://cdkopyphjvfxjqhasrae.supabase.co`. The only change to that database is one paste. It creates `pidi_` tables and functions in `public` and does not touch bookkeeping tables, auth, storage, roles, or extensions.

There is no service role key, no Edge Function, and no signing key. Do not go looking for them.

## Apply in this order

**1. SQL first.** In the Supabase SQL editor, paste `driver/v2/supabase/PIDI_SETUP.sql` and run it. It is one file. Running it twice is safe. If `extensions.crypt` is missing it stops and does not turn anything on.

**2. Then the PINs, in the same SQL editor.** Edit the numbers, then run this. It is not in the paste, so a blind paste cannot leave a known PIN in the database. Only the hash is stored.

```sql
insert into public.pidi_settings (key, value)
values ('admin_pin_hash', extensions.crypt('PUT_8_DIGIT_ADMIN_PIN', extensions.gen_salt('bf', 8)))
on conflict (key) do nothing;

select public.pidi_admin_set_kitchen_pin('PUT_8_DIGIT_ADMIN_PIN', 'PUT_KITCHEN_PIN');
select public.pidi_admin_add_driver('PUT_8_DIGIT_ADMIN_PIN', 'Ari', '2975550000', 'PUT_DRIVER_PIN');
```

The admin PIN is exactly 8 digits. Kitchen and driver PINs are 4 to 8 digits. The driver signs in with their name (`Ari`) and their PIN. Add each driver with another `pidi_admin_add_driver` line. Do not commit these PINs.

Five wrong admin PINs lock admin checks for 5 minutes. Until that ends, the right PIN is refused too: "Too many tries. Wait 5 minutes." There is one admin, so the lock is global.

**3. Then config.js.** Put the anon key in `driver/v2/config.js` and commit it. The URL is already there. The URL and the anon key are public. Never commit a service role key or a signing JWK (this setup does not use them).

v2 stays on the "not connected" screen until that key is set and `pidi_ping()` answers. Opening `/driver/v2/` before that does not call the database.

## What you still give the other tool

`driver/v2/CLAUDE_REALTIME_PROMPT.md` is the paste for the kitchen app and the customer checkout. Those folders are not edited here.

## Try a daytime order

Hours are 10:00 PM to 2:00 AM Aruba time. For a test in the afternoon, in the SQL editor:

```sql
update public.pidi_settings set value = 'flag' where key = 'hours_mode';
```

Set it back to `reject` when the test is over. `flag` keeps the order and marks it outside hours.

Kitchen: sign in with the kitchen PIN, Accept, Cooking, Ready. An online driver gets the offer for 45 seconds. The first Accept wins. A second order joins that run when it is ready, or due within 10 minutes, and the drop is under 3 km from the first. A run holds at most 2 orders. Offers refresh when a driver opens the offer list, so no cron job is required.

Each order has its own ƒ5 delivery and its own ƒ24 food minimum. Say if a mixed cart should stay one ƒ5.

The customer link is `/driver/v2/status/#t=` plus the public token from `pidi_place_order`. A second order can be `&u=`.

## Local proof

```bash
python3 driver/v2/supabase/tests/run_local.py
```

Needs local Postgres. It does not call Supabase. It applies the file twice, checks a dummy bookkeeping table is unchanged, then runs the order as the `anon` role.
