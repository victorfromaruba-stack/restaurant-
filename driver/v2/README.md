# Pidi v2

This is the live order system. It is **not switched on**. The driver app people use today is still `/driver/` (v1). Nothing in v1 reads this folder.

Do not create a Supabase project from the repo, and do not put a service role key, a JWT secret, or a PIN in git. The free tier is enough.

## What you need to provide

1. **Project URL**, like `https://xxxx.supabase.co`.
2. **Publishable or anon key.** This one goes in `config.js` on the phone. It is not a secret in the same way, but it is still not the service role key.
3. **Service role key** (or the new secret key). Only as an Edge Function secret. Supabase injects `SUPABASE_SERVICE_ROLE_KEY` on hosted functions. Never put it in `config.js` or in the browser.
4. **A signing key** so a PIN can become a short login token:
   - On your computer: `supabase gen signing-key --algorithm ES256`
   - In the Supabase dashboard, import that key and rotate to it (JWT signing keys).
   - Set the same JSON, including the private `d` field, as the function secret `PIDI_SIGNING_JWK`.
   - If the project still uses the old shared JWT secret, you can set `SUPABASE_JWT_SECRET` instead. New projects should use the ES256 key.
5. **Driver PINs and a kitchen PIN.** You choose them. The SQL below stores only the hash.
6. **The pickup address and pin**, when you want drivers to navigate to pickup. Leave it blank until you have the real one. Do not invent it.

## 1. Create the database

In the Supabase SQL editor, paste and run:

`driver/v2/supabase/migrations/20261009170000_pidi_v2.sql`

Or, from the `driver/v2` folder, after `supabase link`:

```bash
supabase db push
```

That creates the restaurants (the five, `partner` false), orders, items, drivers, runs, offers, locations, row security, and the realtime publication. On hosted Supabase the `supabase_realtime` publication already exists and the migration adds `orders`, `runs`, `offers`, and `driver_locations`. A plain Postgres server prints a notice and skips that step.

## 2. Turn on realtime

In the dashboard, Database → Publications, confirm those four tables are in `supabase_realtime`. The migration adds them when the publication exists.

## 3. Offer timeout

An offer lasts 45 seconds (`settings.offer_seconds`). The database closes it and offers the run again.

- **pg_cron:** the migration schedules `pidi-dispatch-tick` every 15 seconds when the `cron` schema exists. Supabase Cron (pg_cron) is on the free tier and can run that often. If the extension is off, the migration skips the schedule and prints a notice. Turn it on under Database → Extensions, then run:

```sql
select cron.schedule('pidi-dispatch-tick', '15 seconds', 'select public.dispatch_tick()');
```

- **The phone also calls `dispatch_tick`** whenever a driver is online and asks for offers, and when a countdown hits zero. So a run is re-offered even if cron is off, as long as one driver app is open.

`accept_offer` refuses an offer after `expires_at` either way. Two drivers accepting at once: the run row only moves from `offered` to `active` once. The other driver gets "Another driver took this run."

## 4. How a run is built

`settings.dispatch_when` is `ready` (the default) or `accepted`.

- `ready`: the kitchen taps Ready, then drivers are offered the run.
- `accepted`: the offer goes out as soon as the kitchen taps Accept. The order can still move to Cooking and Ready until a driver takes it. When a driver takes it, the status becomes `assigned`.

Pairing, in `pidi.dispatch_tick`:

1. Take orders that are in the dispatch status and not already on a live run.
2. A second order joins when it is **ready, or due within 10 minutes** (`pair_minutes`), **and** nearby: the same area, **or** under 3 km between the drop pins (`pair_km`, haversine).
3. A run holds at most 2 orders. If a one-order run is still only offered, a later nearby order is added as stop 2 and the offer is refreshed.
4. Stop 1 is the drop closer to the pickup pin when `pickup_lat` and `pickup_lng` are set. Otherwise the earlier due time is stop 1. A late join stays stop 2.
5. Every online driver who is not already on a run gets the offer, except a driver who tapped "Not this one" for that run.

## 5. Deploy the three functions

From `driver/v2`:

```bash
supabase functions deploy driver-pin
supabase functions deploy kitchen-pin
supabase functions deploy order-session
supabase secrets set PIDI_SIGNING_JWK='{"kty":"EC",...}'
```

`driver-pin` and `kitchen-pin` check the hashed PIN and return a 12 hour token. Five wrong PINs lock that code for 5 minutes. `order-session` turns the customer's public token into a 6 hour token so the status page can listen on realtime. The customer's token is the secret. It is a 48 character hex string.

## 6. Config on the phone

```bash
cp driver/v2/config.example.js driver/v2/config.js
```

Put the project URL and the publishable or anon key in `config.js`. `driver/v2/.gitignore` ignores `config.js`. Do not commit it.

## 7. Seed a driver and the kitchen

Replace the PINs before you run this. Codes are what they type. PINs are 4 to 8 digits.

```sql
insert into public.drivers (name, code, pin_hash)
values ('Ari', 'ari', extensions.crypt('2468', extensions.gen_salt('bf', 8)));

insert into public.staff (name, code, pin_hash)
values ('Kitchen', 'chef', extensions.crypt('9999', extensions.gen_salt('bf', 8)));
```

Pickup, when you have the real address:

```sql
update public.settings set value = 'The pickup name' where key = 'pickup_name';
update public.settings set value = 'The street' where key = 'pickup_address';
update public.settings set value = '12.5190' where key = 'pickup_lat';
update public.settings set value = '-70.0370' where key = 'pickup_lng';
```

## 8. Try it

Driver: open `/driver/v2/`, sign in, tap Go online.

A test order (food at least ƒ24, fee is added as ƒ5):

```sql
select public.place_order(jsonb_build_object(
  'restaurant', 'dushi-wok',
  'name', 'Maria TEST',
  'phone', '2975990001',
  'area', 'Noord',
  'address', 'TEST, Weg naar Westpunt 12',
  'lat', '12.5696',
  'lng', '-70.0310',
  'pay', 'cash',
  'pays_with_cents', 5000,
  'test', true,
  'items', jsonb_build_array(jsonb_build_object('name', 'Chicken fried rice', 'qty', 1, 'price_cents', 2895))
));
```

Hours are 10:00 PM to 2:00 AM in `America/Aruba`. Outside that, the insert is rejected. For a daytime test:

```sql
update public.settings set value = 'flag' where key = 'hours_mode';
```

`flag` keeps the order and sets `outside_hours`. `reject` (the default) blocks it.

Then in the kitchen snippet, Accept → Cooking → Ready. The online driver should see an offer with a countdown.

Status page, after you have `config.js`:

`/driver/v2/status/#t=THE_PUBLIC_TOKEN`

Labels: Received (new or accepted), Cooking (cooking or ready), On the way (assigned or picked up), Delivered, Cancelled.

## Money

Florin cents. Food minimum ƒ24 for one restaurant, or for the sum of a two-restaurant checkout. Delivery is ƒ5 once per checkout (`place_checkout`), on the first order. The second restaurant in that checkout has a ƒ0 fee. Cash stores `pays_with_cents`. `change_due_cents` is `pays_with` minus that order's total. A transfer is `awaiting` or `paid`, and cash to collect is none.

## Tests without a hosted project

```bash
python3 driver/v2/supabase/tests/run_local.py
```

Needs local Postgres. It does not call Supabase. It checks the minimum, the one-fee checkout, hours, pairing, accept-time dispatch, two drivers accepting at once, the 45 second re-offer, and row security (a customer token, a driver, the kitchen, and a stranger).

## Not done until you connect Supabase

The kitchen screen and the customer checkout are not edited here. Paste `CLAUDE_REALTIME_PROMPT.md` into the tool that owns those folders. v1 keeps using WhatsApp links until you say to switch.
