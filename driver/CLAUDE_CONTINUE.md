# Pidi driver app, handoff

Plain HTML, CSS and JS in `/driver/`. No build step, no framework, no accounts, no backend. The customer site and the chef app are owned by another tool. Do not edit anything outside `/driver/` unless Victor asks.

Live: https://victorfromaruba-stack.github.io/restaurant-/driver/

Pidi Blue is `#2D3BE8`. Night background is Pidi Ink `#12143A`. The wordmark, icons and "X by Pidi" logos are the real files in `brand/`. Payment is cash or bank transfer only. Currency is the Aruban florin (ƒ). Rules in the app: ƒ24 food before the fee, ƒ5 delivery, at most 2 drops a run, delivery only, 10 PM to 2 AM. Order WhatsApp is +297 747 7794 (`2977477794`).

## 1. Screens

| Screen | File | What the driver sees |
|---|---|---|
| Home | `index.html` | No run yet, or Continue if one is open. Hours, cash or bank transfer, 2 drops. Links to install, the cash count, and Send a run. A run link opened here is sent on to `run.html`. |
| Run, intro | `run.html` | "Tonight's run". Names and areas. One button: Start pickup. A `test: true` run shows "TEST run. Not a real order." |
| Pickup | `run.html` | One step. Restaurant logos and item names, grouped into bags. Address and pin if the link has them, with Google Maps and Waze. One button: Picked up. |
| Drop | `run.html` | One drop at a time, up to 2. Name, area, money box, address, note, Google Maps, Waze, Call, WhatsApp, then the items. One button: Delivered. |
| Run done | `run.html` | Cash collected on this run. Button: Count the cash. |
| Cash count | `cash.html` | Sum of delivered cash drops for this service night, across every run on the phone. Transfer drops are listed as awaiting or paid, and they add ƒ0. Type the florins counted, then Compare. A match says "It matches." A gap under ƒ9 is "Small difference, noted." ƒ9 to ƒ36 is "Check within 24 hours." Over ƒ36 is "Check now." |
| Send a run | `dispatch.html` | Form for one pickup and one or two drops. Checks the ƒ24 food floor and adds ƒ5. "Send to driver on WhatsApp" opens `wa.me` with the run link. Default number is 2977477794. Copy and "Open this run on this phone" are there too. |
| Help | `help.html` | Hand over at the door. Call 911, police 100, WhatsApp the order number. |
| Install | `install/index.html` | iPhone: Safari, Share, Add to Home Screen. Android: Chrome menu, Install app. A computer shows a QR code of the install page. TestFlight and the Android file are not built yet. |

Buttons are at least 56px. One primary action sits in the bottom bar.

## 2. File map

| Path | Job |
|---|---|
| `index.html` `run.html` `cash.html` `dispatch.html` `help.html` | Screens |
| `install/index.html` `install/qr.svg` | Add to Home Screen, and the QR |
| `manifest.webmanifest` | PWA. `start_url` and `scope` are `./`, so they resolve to the `/driver/` folder (`/restaurant-/driver/` on GitHub Pages). `display` is `standalone`. |
| `sw.js` | Cache `pidi-driver-v1`. Registered with scope = the `/driver/` directory only. It ignores any URL whose path does not contain `/driver/`. Bump `CACHE` after a change that must replace an old copy. |
| `css/app.css` | The whole look, plus the self-hosted fonts |
| `js/words.js` | English screen words. Add `pap` / `nl` / `es` beside this object later. |
| `js/app.js` | Money, links, encode/decode, localStorage, service worker, maps and WhatsApp URLs |
| `js/home.js` `js/run.js` `js/cash.js` `js/dispatch.js` `js/install.js` | One file per screen |
| `brand/` | App icons, wordmark, favicons, Android adaptive icons, the five "by Pidi" logos |
| `fonts/` | Plus Jakarta Sans (body, has the ƒ) and Bricolage Grotesque (headings) |
| `tests/test_run.json` | The TEST order |
| `tests/flow.py` | Playwright flow on iPhone 13 and Pixel 7 |
| `TEST_RUN.txt` | The ready-made live link |
| `V2_NOTES.md` | Backend, native apps, live sync. Not built. |

Storage key: `localStorage["pidi.driver.v1"]`. Shape: `{ v, runs: { [id]: record } }`. A record keeps the payload, `step` (`intro`, `pickup`, `drop`, `done`), `dropIndex`, `pickedUpAt`, `deliveredAt[]`, `night`, `receivedAt`. Opening the same id with the same payload keeps the step. A changed payload replaces it. The service night is Aruba time (UTC−4) minus 8 hours, so 12:30 AM still counts as the night before. `Pidi.serviceNight()` does that.

Restaurants in `Pidi.RESTAURANTS`: `dushi-wok`, `taco-brava`, `smash-shack`, `nonnas-night-in`, `oranje-snack`. A drop may use another id plus `restaurantName` for a partner. There is no logo for that case. A grey name tile is shown instead.

## 3. Run links

The order rides in the URL hash so GitHub Pages never receives the address or the phone. `index.html` forwards a payload hash to `run.html`.

### Format

`run.html#` + body

| Body | Meaning |
|---|---|
| `1.` + base64url(UTF-8 JSON) | Normal. No padding. `+` `/` `=` become `-` `_` and are dropped. |
| `z.` + base64url(gzip of the UTF-8 JSON) | Used only when the plain body is 1,400 characters or longer and the phone has `CompressionStream`. The shorter of the two is kept. |

`Pidi.encodeRun(obj)` returns the body (no `#`). `Pidi.decodeBody(body)` returns the object. `Pidi.validate` rejects a bad shape in plain words. After a good decode, the long hash is replaced with `#run=<id>` so the phone is not left holding the payload. Refresh still works, because the run is in localStorage.

### JSON fields

Money is integer florin cents. Pins are strings, so `12.5696` is not turned into a float.

```json
{
  "v": 1,
  "id": "TEST-2",
  "test": true,
  "pickup": {
    "name": "TEST pickup",
    "address": "TEST, Caya G. F. Croes, Oranjestad",
    "lat": "12.5190",
    "lng": "-70.0370"
  },
  "drops": [
    {
      "name": "Maria TEST",
      "phone": "2975990001",
      "area": "Noord",
      "address": "TEST, Weg naar Westpunt 12, Noord",
      "lat": "12.5696",
      "lng": "-70.0310",
      "note": "TEST order. Green house.",
      "restaurant": "dushi-wok",
      "items": [{ "name": "Chicken fried rice", "qty": 1 }],
      "pay": "cash",
      "food": 2895,
      "fee": 500,
      "total": 3395,
      "paysWith": 5000
    }
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `v` | yes | Must be `1` |
| `id` | yes | Storage key. Not shown as a big code. Dispatcher makes `HHMM-AB` in Aruba time. |
| `test` | no | `true` shows the TEST banner |
| `pickup.name` `pickup.address` | name shown if set | Address and pin can be empty when the driver already knows the stop |
| `pickup.lat` `pickup.lng` | both or neither | Strings |
| `drops` | 1 or 2 | A third drop is refused |
| `drops[].name` `address` `restaurant` | yes | `restaurantName` when it is not one of the five |
| `drops[].phone` | for Call / WhatsApp | Digits, country code included (`297…`) |
| `drops[].area` `note` | no | |
| `drops[].items[]` | at least one | `{ name, qty }` |
| `drops[].pay` | yes | `cash` or `transfer` |
| `drops[].food` `fee` `total` | `total` required | Cents. Dispatcher sets `fee` to 500 and `total` to food + fee. Food must be at least 2400 before send. |
| `drops[].paysWith` | cash only | Cents they hand over. Change = paysWith − total. |
| `drops[].transfer` | transfer only | `awaiting` (default) or `paid`. No cash is collected. |

### Map, call, WhatsApp

With a pin (strings joined, not reformatted):

- Google Maps: `https://www.google.com/maps/dir/?api=1&destination=LAT,LNG&travelmode=driving`
- Waze: `https://waze.com/ul?ll=LAT,LNG&navigate=yes`

Without a pin, the address plus `, Aruba` is URL-encoded as `destination` or Waze `q`.

- Call: `tel:+2975990001`
- WhatsApp: `https://wa.me/2975990001?text=Hi%20Maria%20TEST%2C%20your%20Dushi%20Wok%20order%20is%20outside.`

### Example

The full TEST link (2 drops, one cash with a pays-with amount, one awaiting transfer) is the first line of `TEST_RUN.txt`. It is 1,201 characters. Open it on a phone:

https://victorfromaruba-stack.github.io/restaurant-/driver/run.html#1.eyJ2IjoxLCJpZCI6IlRFU1QtMiIsInRlc3QiOnRydWUsInBpY2t1cCI6eyJuYW1lIjoiVEVTVCBwaWNrdXAiLCJhZGRyZXNzIjoiVEVTVCwgQ2F5YSBHLiBGLiBDcm9lcywgT3Jhbmplc3RhZCIsImxhdCI6IjEyLjUxOTAiLCJsbmciOiItNzAuMDM3MCJ9LCJkcm9wcyI6W3sibmFtZSI6Ik1hcmlhIFRFU1QiLCJwaG9uZSI6IjI5NzU5OTAwMDEiLCJhcmVhIjoiTm9vcmQiLCJhZGRyZXNzIjoiVEVTVCwgV2VnIG5hYXIgV2VzdHB1bnQgMTIsIE5vb3JkIiwibGF0IjoiMTIuNTY5NiIsImxuZyI6Ii03MC4wMzEwIiwibm90ZSI6IlRFU1Qgb3JkZXIuIEdyZWVuIGhvdXNlLiIsInJlc3RhdXJhbnQiOiJkdXNoaS13b2siLCJpdGVtcyI6W3sibmFtZSI6IkNoaWNrZW4gZnJpZWQgcmljZSIsInF0eSI6MX0seyJuYW1lIjoiU3dlZXQgJiBzb3VyIGNydW5jaCBjaGlja2VuIHdpdGggcmljZSIsInF0eSI6MX1dLCJwYXkiOiJjYXNoIiwiZm9vZCI6Mjg5NSwiZmVlIjo1MDAsInRvdGFsIjozMzk1LCJwYXlzV2l0aCI6NTAwMH0seyJuYW1lIjoiQ2FybG9zIFRFU1QiLCJwaG9uZSI6IjI5NzU5OTAwMDIiLCJhcmVhIjoiT3Jhbmplc3RhZCIsImFkZHJlc3MiOiJURVNULCBXaWxoZWxtaW5hc3RyYWF0IDgsIE9yYW5qZXN0YWQiLCJsYXQiOiIxMi41MDkyIiwibG5nIjoiLTcwLjAwODYiLCJub3RlIjoiVEVTVCBvcmRlci4iLCJyZXN0YXVyYW50IjoidGFjby1icmF2YSIsIml0ZW1zIjpbeyJuYW1lIjoiQmlycmlhIHRhY29zICgzKSB3aXRoIGNvbnNvbW3DqSIsInF0eSI6MX1dLCJwYXkiOiJ0cmFuc2ZlciIsImZvb2QiOjI3MDAsImZlZSI6NTAwLCJ0b3RhbCI6MzIwMCwidHJhbnNmZXIiOiJhd2FpdGluZyJ9XX0

Drop 1 collects ƒ33.95, pays with ƒ50.00, change ƒ16.05. Drop 2 is awaiting transfer, ƒ32.00 order, no cash. Both are marked TEST. Pins: Maria `12.5696,-70.0310`, Carlos `12.5092,-70.0086`.

### Size limits

- Dispatcher refuses a run URL longer than 1,800 characters (`Pidi.MAX_URL`). That leaves room for the WhatsApp text around it. `wa.me` messages should stay under about 4,000 characters.
- Plain `1.` links are preferred under 1,400 characters of hash body. Above that, gzip (`z.`) is tried.
- Keep notes and addresses short. Do not put photos in the link.
- Base64url is ASCII, so it survives WhatsApp and the hash. Do not put the payload in a `?query`, or the host logs the customer's phone and address.

`tests/flow.py` encodes `tests/test_run.json` the same way and checks `TEST_RUN.txt` still matches. Run:

```
python3 driver/tests/flow.py
PIDI_BASE=http://127.0.0.1:8765/driver/ python3 driver/tests/flow.py
```

Needs Playwright (`playwright` Python package and Chromium).

## 4. What is missing

v1 is one phone and a link. Nothing syncs. Details are in `V2_NOTES.md`. Short version:

1. **Supabase** (a new project in Victor's account, not Book Keeper). Tables for pickup points, restaurants, staff, orders, order events, runs, run stops, offers, driver positions, cash-ups. Auth is a 6-digit PIN for staff. Realtime for new runs and status. Row-level security so a driver only sees their own run. No service-role key in this public repo. Do not create the project or spend money until Victor says so.
2. **Native apps.** Capacitor can wrap this `/driver/` folder. Android: a signed APK, later Play internal testing. iPhone: TestFlight, which needs Victor's Apple Developer account ($99/year). Signing keys stay out of the repo. The install page should then point Android at the APK and iPhone at the TestFlight invite. Background GPS and a locked-screen offer need the native app. The web app cannot do that.
3. **Live sync** with the chef app (`ops/kitchen/`) and the customer site. Today the chef pastes WhatsApp and the customer sends WhatsApp. v2 writes one order row at Send, the chef accepts it, and the driver offer is the same row. Until that exists, keep using the run link.

Also not in v1: a second person at the cash count, a float, US dollar rate (Victor has not set one), masked phone numbers, in-app turn-by-turn, proof photos, customer PIN, SOS to a dispatch screen.

## 5. Prompt for the next session

Paste this:

```
You are continuing the Pidi driver app in /driver/ of victorfromaruba-stack/restaurant-. Read /driver/CLAUDE_CONTINUE.md and /driver/V2_NOTES.md first. The app is vanilla HTML/CSS/JS with no build step. Do not edit any file outside /driver/ unless Victor explicitly asks. Do not create accounts, Supabase projects, or store listings, and do not spend money.

Pidi is the name (capital P, rest lowercase). Pidi Blue is #2D3BE8. Payment is cash or bank transfer only. ƒ24 food minimum, ƒ5 delivery, at most 2 drops a run, delivery only, 10 PM to 2 AM. Order WhatsApp 2977477794. The five restaurants are Dushi Wok, Taco Brava, Smash Shack, Nonna's Night In and Oranje Snack. A partner pickup is allowed in the data (restaurantName) but has no logo yet.

The driver UI stays one step per screen, big buttons (56px), plain words, restaurant logos, no internal codes on screen. Run links are a base64url JSON hash documented in CLAUDE_CONTINUE.md. Keep tests/flow.py passing on the live URL with Playwright device profiles iPhone 13 and Pixel 7. Bump the CACHE name in sw.js when you change cached files. The service worker scope must stay the /driver/ folder only.

Victor's next real gap is a shared backend so the chef app and this driver app see the same order. Design it as in V2_NOTES.md, but wait for his Supabase URL and publishable key before wiring it. Native TestFlight and APK come after that, by wrapping /driver/ with Capacitor, keys kept out of the repo.
```
