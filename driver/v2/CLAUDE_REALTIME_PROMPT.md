# Paste this into Claude Code

You are wiring Order Aruba's kitchen app and customer checkout to Pidi v2. The database and the driver app are already written. Do not redesign them. Do not create a Supabase project. Do not spend money. Do not edit `/driver/` except `driver/v2/config.js` on a machine that is not committed.

Read `/driver/v2/README.md` and the migration `/driver/v2/supabase/migrations/20261009170000_pidi_v2.sql` before you change anything.

v1 (`/driver/index.html` and its scripts) stays the live driver app. Do not change its behaviour. The new driver UI is `/driver/v2/` and it is off until `config.js` exists.

The owner will give you the project URL and the publishable or anon key. The service role key stays in Edge Function secrets only. Never put it in the customer site or the kitchen app.

Payment is cash or bank transfer only. Currency is florin cents (2895 = ƒ28.95). Food minimum is ƒ24 before the fee. Delivery is ƒ5 once per checkout, even when the checkout has two restaurants. Hours are 10 PM to 2 AM America/Aruba. Do not write anything a customer can see that says the restaurants share a kitchen.

## API contract

Anon key, header `apikey` and `Authorization: Bearer <anon key>`.

`POST /rest/v1/rpc/place_checkout`

```json
{
  "payload": {
    "client_token": "a uuid you store for this checkout",
    "name": "Maria",
    "phone": "2975990001",
    "area": "Noord",
    "address": "Weg naar Westpunt 12",
    "lat": "12.5696",
    "lng": "-70.0310",
    "note": "",
    "pay": "cash",
    "pays_with_cents": 5000,
    "due_at": null,
    "test": false,
    "groups": [
      {
        "restaurant": "dushi-wok",
        "items": [{ "name": "Chicken fried rice", "qty": 1, "price_cents": 1600 }]
      },
      {
        "restaurant": "taco-brava",
        "items": [{ "name": "Birria tacos", "qty": 1, "price_cents": 1200 }]
      }
    ]
  }
}
```

`pay` is `cash` or `transfer`. For a transfer, omit `pays_with_cents`. One group is fine. Two is the maximum. The sum of the item prices must be at least 2400. The function adds the ƒ5 fee on the first group only.

Response:

```json
{
  "checkout_id": "uuid",
  "orders": [
    {
      "id": "uuid",
      "public_token": "48 hex chars",
      "ref": "2330-AB",
      "status": "new",
      "restaurant": "Dushi Wok",
      "restaurant_slug": "dushi-wok",
      "food_cents": 1600,
      "fee_cents": 500,
      "total_cents": 2100,
      "change_due_cents": 2900,
      "pay": "cash",
      "outside_hours": false
    }
  ]
}
```

Sending the same `client_token` again returns the same checkout. Do not open WhatsApp for the order.

One restaurant can also use `POST /rest/v1/rpc/place_order` with the same fields plus `restaurant` and `items` at the top, and no `groups`. That path still requires that restaurant's food to be at least ƒ24, and the fee is ƒ5.

Status for a customer, no login: `POST /rest/v1/rpc/order_by_token` with `{ "token": "<public_token>" }`.

```json
{ "id": "uuid", "status": "cooking", "label": "Cooking", "ref": "2330-AB", "restaurant": "Dushi Wok", "outside_hours": false }
```

Labels: Received, Cooking, On the way, Delivered, Cancelled.

Realtime: `POST /functions/v1/order-session` with `{ "token": "<public_token>" }` and header `apikey`. It returns `{ "token": "<jwt>" }`. Subscribe to `postgres_changes` on `public.orders` filtered by `public_token=eq.<token>`, with that JWT as the access token. Row security only returns that order.

Kitchen sign-in: `POST /functions/v1/kitchen-pin` with `{ "code", "pin" }`. Store the returned token for the shift (12 hours). Then:

`POST /rest/v1/rpc/kitchen_set_status`

```json
{ "order_id": "uuid", "next_status": "accepted" }
```

Allowed: new → accepted, accepted → cooking, cooking → ready, and cancelled until a driver has taken it. The database rejects any other jump.

Subscribe to inserts and updates on `public.orders` with the kitchen JWT.

Driver sign-in is already built at `/driver/v2/`. Do not rebuild it.

## Customer checkout

In `shared/order-app.js`, the send step is `checkoutLink()` / the WhatsApp open. Replace that send with the checkout below. Keep the screen the customer already filled in (name, address, area, pay, items, prices in cents). Stop opening `wa.me` for the order.

Add this file as `shared/pidi-v2.js` and load it from the pages that already load `order-app.js`. Fill `PIDI_URL` and `PIDI_ANON` from the keys the owner gives you. Do not commit the service role key.

```javascript
/* Customer checkout → Pidi v2. One ƒ5 fee for the whole cart. */
var PidiOrder = (function () {
  var URL = "https://YOUR_PROJECT.supabase.co";
  var ANON = "YOUR_PUBLISHABLE_OR_ANON_KEY";

  function post(path, body) {
    return fetch(URL + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: ANON,
        Authorization: "Bearer " + ANON
      },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error((data && (data.message || data.error)) || "Order was not saved");
        return data;
      });
    });
  }

  function place(cart) {
    var key = "orderaruba.checkout.v1";
    var token = sessionStorage.getItem(key);
    if (!token) {
      token = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
      sessionStorage.setItem(key, token);
    }
    return post("/rest/v1/rpc/place_checkout", {
      payload: {
        client_token: token,
        name: cart.name,
        phone: cart.phone,
        area: cart.area,
        address: cart.address,
        lat: cart.lat || null,
        lng: cart.lng || null,
        note: cart.note || "",
        pay: cart.pay === "Bank transfer" ? "transfer" : "cash",
        pays_with_cents: cart.pay === "Bank transfer" ? null : cart.paysWithCents,
        groups: cart.groups
      }
    });
  }

  function statusUrl(orders) {
    var hash = "#t=" + encodeURIComponent(orders[0].public_token);
    if (orders[1]) hash += "&u=" + encodeURIComponent(orders[1].public_token);
    return "https://victorfromaruba-stack.github.io/restaurant-/driver/v2/status/" + hash;
  }

  return { place: place, statusUrl: statusUrl };
})();
```

`cart.groups` is one entry per restaurant in the cart:

```javascript
{ restaurant: "dushi-wok", items: [{ name: "Chicken fried rice", qty: 1, price_cents: 1295 }] }
```

Use the menu price in cents. The slug is the restaurant folder: `dushi-wok`, `taco-brava`, `smash-shack`, `nonnas-night-in`, `oranje-snack`.

On success, send the customer to `PidiOrder.statusUrl(result.orders)`. On failure, show the message from the database in plain words (minimum, hours, phone). Do not fall back to WhatsApp if the save fails. Let them retry. The same `client_token` will not create a second order.

The status page already exists at `/driver/v2/status/`. It polls `order_by_token` and, once `order-session` is deployed, also listens on realtime. You do not have to build another status page unless you want the same four words inside the restaurant page. If you do, use the same hash and the same RPC. Map:

| status | words |
|---|---|
| new, accepted | Received |
| cooking, ready | Cooking |
| assigned, picked_up | On the way |
| delivered | Delivered |
| cancelled | Cancelled |

## Kitchen feed

The chef app is `ops/kitchen/index.html` and `ops/kitchen/kitchen.js`. Do not remove the paste box until Victor says the live feed has taken a real order. Add a Live button that opens the screen below.

Create `ops/kitchen/live.js` and add `<script type="module" src="live.js"></script>` under the other scripts in `ops/kitchen/index.html`.

```javascript
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

const URL = "https://YOUR_PROJECT.supabase.co";
const ANON = "YOUR_PUBLISHABLE_OR_ANON_KEY";
const KEY = "kitchen.pidi.v1";

function beep() {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.frequency.value = 880;
  gain.gain.value = 0.08;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.15);
}

function client(token) {
  return createClient(URL, ANON, {
    auth: { persistSession: false, autoRefreshToken: false },
    accessToken: async () => token
  });
}

async function signIn(code, pin) {
  const res = await fetch(URL + "/functions/v1/kitchen-pin", {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: ANON },
    body: JSON.stringify({ code, pin })
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "That PIN does not match.");
  sessionStorage.setItem(KEY, body.token);
  return body.token;
}

function open(root) {
  const saved = sessionStorage.getItem(KEY);
  root.textContent = "";
  if (!saved) {
    const code = document.createElement("input");
    const pin = document.createElement("input");
    pin.type = "password";
    pin.inputMode = "numeric";
    const button = document.createElement("button");
    button.textContent = "Sign in";
    button.addEventListener("click", () => {
      signIn(code.value.trim().toLowerCase(), pin.value.trim()).then(() => open(root)).catch((err) => {
        root.appendChild(document.createTextNode(err.message));
      });
    });
    root.appendChild(code);
    root.appendChild(pin);
    root.appendChild(button);
    return;
  }
  const db = client(saved);
  const list = document.createElement("div");
  root.appendChild(list);
  const seen = new Set();

  function row(order) {
    const block = document.createElement("article");
    const title = document.createElement("h2");
    title.textContent = order.customer_name + " · " + order.status;
    block.appendChild(title);
    const next = { new: "accepted", accepted: "cooking", cooking: "ready" }[order.status];
    const label = { new: "Accept", accepted: "Cooking", cooking: "Ready" }[order.status];
    if (next) {
      const button = document.createElement("button");
      button.textContent = label;
      button.addEventListener("click", () => {
        db.rpc("kitchen_set_status", { order_id: order.id, next_status: next }).then(load);
      });
      block.appendChild(button);
    }
    return block;
  }

  function load() {
    db.from("orders").select("id,customer_name,status,ref,created_at").in("status", ["new", "accepted", "cooking", "ready"]).order("created_at")
      .then(({ data }) => {
        (data || []).forEach((order) => {
          if (order.status === "new" && !seen.has(order.id)) beep();
          seen.add(order.id);
        });
        list.textContent = "";
        (data || []).forEach((order) => list.appendChild(row(order)));
      });
  }

  db.channel("kitchen-orders")
    .on("postgres_changes", { event: "INSERT", schema: "public", table: "orders" }, load)
    .on("postgres_changes", { event: "UPDATE", schema: "public", table: "orders" }, load)
    .subscribe();
  load();
}

window.PidiLive = { open };
```

Wire one button on the kitchen home: `PidiLive.open(document.getElementById("main"))`. Keep the chef's big type and 56px buttons. The words on the buttons are Accept, Cooking, and Ready. Play the beep only when a new order arrives, not on every refresh.

Restaurant names on that screen should be the real names (join `restaurants` on `restaurant_id` if you show them). Do not show another restaurant's order as if it were the same business in the customer text. The kitchen is allowed to see every order. Drivers are not. Do not weaken the row security policies to make the feed easier.
