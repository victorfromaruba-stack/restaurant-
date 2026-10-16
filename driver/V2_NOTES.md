# Pidi driver, v2 notes

10 Oct 2026: `/driver/` now opens v2. The v1 pages only forward to `v2/`; `tests/flow.py` tests v1 and no longer applies. The staff screens are tested by `qa/check_staff.py` (fake database answers only).

9 Oct 2026, later: v2 uses the live bookkeeping database (`https://cdkopyphjvfxjqhasrae.supabase.co`). The only SQL file to paste is `/driver/v2/supabase/PIDI_SETUP.sql`. It creates `public.pidi_*` only. Do not run an older migration, do not deploy Edge Functions, and do not put a service role key or a signing JWK in the repo. The anon key does go in `/driver/v2/config.js` and is committed. Where this file disagrees with `/driver/v2/README.md`, the README wins.

9 Oct 2026: Victor changed the plan. WhatsApp ordering goes away once v2 is connected. The prepared system is in `/driver/v2/`. It is not live. v1 stays the driver app until a test order has gone through. Do not merge that work early.

No Supabase project was created, no account was opened, and nothing here costs money. Do not put a service-role key, a signing key, or a PIN in this repo. The repo is public.

## Why a backend is the next step

A run link is enough for one dispatcher and one driver on one phone. It cannot:

- show the chef and the driver the same order at the same time
- offer a run to whichever driver is free
- tell the customer "on the way" from the driver's tap
- keep the cash count when the driver changes phones
- wake a locked phone with a new offer

v1 still sends the ticket to +297 747 7794. v2 replaces that send with a database row. Do not switch v1 over until the project exists.

## Supabase

The rest of this section is the old sketch. Do not apply it. The live file is `/driver/v2/README.md` and `/driver/v2/supabase/PIDI_SETUP.sql`.

Use a new project in Victor's existing Supabase account, separate from Book Keeper. Free is enough to build. It pauses after about a week of no use and has no backups. Pro ($25/month) is the one to use once real orders run. That spend is Victor's decision.

Extensions: `postgis`, `pgcrypto`. Turn on row-level security for every table. Staff write through functions, not open UPDATE policies.

### Tables

Money is florin cents (`int`). Times are `timestamptz`. The service night is `(created_at at time zone 'America/Aruba' - interval '8 hours')::date`, so 12:30 AM belongs to the night before.

| Table | Holds |
|---|---|
| `pickup_points` | One row for Victor's pickup, plus one per partner later. Address, pin, geofence (75 m), hours as data, `show_pin_to_customers` false for his own pickup. |
| `restaurants` | `dushi-wok`, `taco-brava`, `smash-shack`, `nonnas-night-in`, `oranje-snack`, later partners. `owner` is `own` or `partner`. `mix` only for his five. Min 2400, fee 500. |
| `staff` | admin, kitchen, partner, driver. Name, phone, active flag. A driver has a vehicle line. Tied to `auth.users`. |
| `orders` | One row per order. `kitchen_status` and `delivery_status` move separately. Items, totals, `pay_method` of `cash` or `bank_transfer` only (no card column in the product, even if an old spec mentioned one). `pays_with_cents`, `transfer_seen`, customer name, phone, area, address, drop pin, order code from WhatsApp. |
| `order_events` | Who changed what, and when. |
| `runs` | One driver, one night, at most 2 orders. |
| `run_stops` | Sequence. A pickup comes before its own drop. |
| `offers` | One driver, 30 seconds, then the next. |
| `driver_positions` | Latest pin only. |
| `driver_track` | Breadcrumbs, kept 7 days. |
| `cash_drops` | Cash handed in during the night. |
| `cashups` | Float, blind count in florins and US dollars, variance. The expected total is written by the database at submit time, not sent to the phone before that. Bands: under ƒ9 log, ƒ9 to ƒ36 check within 24 hours, over ƒ36 check now. Two people confirm. |
| `alerts` | SOS, no GPS, overdue. |
| `settings` | Hours, fee, minimum, offer seconds, cash-drop limit. The US dollar rate stays empty until Victor names it. |

Customers do not get accounts in v2. Anonymous calls only: place order, track by a secret token, rate, keep-alive. Tracking may show the driver pin only after Picked up, and it must not show the pickup pin for his five restaurants.

### Auth

Staff sign in with a name and a 6-digit PIN (Supabase Auth, made-up email, PIN as the password). Victor adds people from a small admin function that uses the service-role secret in Edge Function secrets, never in the repo. Five wrong PINs waits 5 minutes. "Switch off" sets `active` false and every policy checks it, so a lost phone loses access on the next request.

The v1 app has no sign-in on purpose. When this exists, the home screen gains a PIN step and the run link can become a short id.

### Realtime

Subscribe staff to `orders`, `offers`, `runs` and `alerts`. Postgres changes respect row-level security. High-rate GPS should use a private broadcast channel, not a row write on every tick. The customer tracking page should poll, not subscribe.

Suggested GPS while the app is open: idle 60 s, on the way to pickup 15 s, carrying an order 8 s, SOS 5 s. The web app still stops when the phone locks. That is the native app's job.

### What the driver app would call

`go_online`, `go_offline`, `answer_offer`, `stop_arrived`, `stop_done`, `deliver` (cash amount, and later a photo), `fail`, `push_positions`, `sos`. The phone keeps an IndexedDB queue and sends again when the signal returns. The server ignores a repeated id. v1 already saves the run locally, so the queue is the piece to add.

## Native iOS and Android

Wrap this `/driver/` folder with Capacitor (the web files stay the UI). Do not rewrite the screens in React for that step.

| | Android | iPhone |
|---|---|---|
| First install | Signed APK. The driver allows "install unknown apps" once. | TestFlight. Needs Victor's Apple Developer account, $99/year, not bought here. |
| Later | Play internal testing ($25 once, his spend) | App Store unlisted, so the link does not die after 90 days |
| Keys | Keystore stays out of the repo. GitHub Releases on a private repo, or EAS, hosts the APK. | Same. No signing material in `restaurant-`. |

`install/index.html` already explains Add to Home Screen. When the builds exist, point Android at the APK URL and iPhone at the TestFlight invite, and add an "Update available" check. Until then, do not show a dead download button.

Native-only, after the wrap:

- background location (Android foreground notice "Pidi: you're on a delivery", iOS Always)
- a push when a run is offered, including when the phone is locked
- the camera for a door photo

In-app turn-by-turn (Google Navigation SDK) is a later choice. Keep the Google Maps and Waze buttons either way. They are free and they already work.

## Live sync with the chef app and the customer site

Do not change `ops/kitchen/`, `shared/order-app.js` or `shared/site.json` until Victor asks. The shape of the join:

1. Customer taps Send. WhatsApp opens as it does now. A second call saves the order (same client id, so a double tap is one row).
2. Chef app shows the live queue: Accept, cooking, ready. Paste-from-WhatsApp still works and matches the `#code` so it is not saved twice.
3. Dispatch, or a simple "Send to driver" on the chef phone, creates a run of at most 2 orders and wakes the driver app. The link in v1 is the stand-in for that push.
4. Picked up and Delivered write `delivery_status`. The customer page can then say "On the way" and, only after pickup, show the driver on a map.
5. End of night reads the same cash rows the driver counted, then a CSV for the books. Bank transfers are not sent as cash. Book Keeper already has a sales intake. Read its contract before sending, and do not change Book Keeper without Victor's OK.

`transfer_seen` is ticked by Victor or the chef, not by the driver. Until it is ticked, the drop stays "Awaiting transfer" and no cash is collected. v1 already behaves that way from the link field `transfer`.

## Open items that block v2

1. Supabase project URL and publishable key, from Victor, kept as he decides. The service-role key stays in Edge secrets.
2. His pickup address, for the pin. Do not invent it.
3. Apple Developer account, and whether he wants the $25 Play account.
4. Driver pay (hourly or per trip) and how many drivers.
5. The US dollar rate, if the cash count should add dollars. Do not hardcode 1.80.
6. Partner terms before any restaurant besides the five goes live.
