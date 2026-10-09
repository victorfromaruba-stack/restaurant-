# Paste this into Claude Code

You are wiring Order Aruba's kitchen app and the customer checkout to Pidi v2. The database and the driver app are already written. Do not redesign them. Do not create a Supabase project. Do not spend money. Do not deploy Edge Functions. Do not ask for a service role key.

The database is the live bookkeeping project, `https://cdkopyphjvfxjqhasrae.supabase.co`. Someone has already pasted `driver/v2/supabase/PIDI_SETUP.sql` (or is about to). Do not run any other SQL. Do not touch a table whose name does not start with `pidi_`.

Edit only `/ops/kitchen/` and the customer site (`shared/order-app.js` and a small script next to it). Do not edit `/driver/` except to put the project URL and the anon key in `driver/v2/config.js` and commit that file. Never commit a service role key or a signing JWK.

v1 (`/driver/index.html` and its scripts) stays the live driver app. The new driver UI is `/driver/v2/` and it stays on "Not connected yet" until `config.js` has an anon key and `pidi_ping()` returns `{"ok":true}`.

Payment is cash or bank transfer. Prices are florin cents (2895 = ƒ28.95). Each order is one restaurant: food minimum ƒ24, delivery ƒ5, added by the database. Hours are 10 PM to 2 AM America/Aruba. Do not write anything a customer can see that says the restaurants share a kitchen.

## API contract

Anon key only. Header `apikey` and `Authorization: Bearer <anon key>`. Body is JSON. Call `POST /rest/v1/rpc/<name>`.

There is no JWT. A kitchen or driver session is a random token returned by the login function. Pass it as `session`. A customer uses the `public_token` from `pidi_place_order`.

`pidi_ping()` → `{"ok":true}`

`pidi_place_order(payload jsonb)` → `{order_id, public_token, food_cents, fee_cents, total_cents, change_due_cents, restaurant}`

```json
{
  "restaurant": "dushi-wok",
  "name": "Maria",
  "phone": "2975990001",
  "area": "Noord",
  "address": "Weg naar Westpunt 12",
  "lat": "12.5696",
  "lng": "-70.0310",
  "note": "",
  "pay": "cash",
  "pays_with_cents": 5000,
  "client_token": "stable-id-for-this-tap",
  "items": [{ "name": "Chicken fried rice", "qty": 1, "price_cents": 2895 }]
}
```

`pay` is `cash` or `transfer`. The database sets the fee to 500. Cash must cover food plus fee. The same `client_token` returns the same order. Errors are plain sentences (minimum, hours, phone).

`pidi_order_status(token text)` → `{status, label, restaurant, topic}`

Labels: Received (new, accepted), Cooking (cooking, ready), On the way (assigned, picked_up), Delivered, Cancelled.

`pidi_kitchen_login(pin text)` → `{ok:true, token, expires_at, topic}` or `{ok:false, error}`. Five wrong PINs lock the kitchen for 5 minutes. The miss is returned, not raised, so the count is saved. Until the lock ends, the right PIN is refused too: "Too many tries. Wait 5 minutes."

`pidi_kitchen_feed(session text)` → `{topic, orders:[...]}`

`pidi_kitchen_accept(session text, order_id uuid)` moves `new` → `accepted`.

`pidi_kitchen_set_status(session text, order_id uuid, status text)` allows `cooking` only from `accepted`, and `ready` only from `cooking`. It cannot set delivered.

Offers go out when the kitchen marks Ready (`pidi_settings.dispatch_when` is `ready`; `accepted` is the other option). Drivers, pairing, and the 45 second timeout are already in the database.

Realtime is a public broadcast ping, not a row subscription. Topics come back from the login or the status call (`pidi:k:…`, `pidi:driver:<uuid>`, `pidi:order:<token>`). The payload is only `{"ping":"changed"}`. Subscribe with `private: false` and event `changed`, then refetch through the RPC. Also poll every 8 seconds. If broadcast never arrives, polling is enough.

## Customer checkout

Add `shared/pidi-v2.js` and load it from the pages that already load `order-app.js`. Fill the two constants from `driver/v2/config.js` (the same anon key). Map the cart's pay label: Cash → `cash`, Bank transfer → `transfer`.

One call per restaurant in the cart. Each call is its own order and its own ƒ5. Send the customer to the status page. For two orders, put the second token in `&u=`.

```javascript
/* Customer checkout → Pidi v2. One restaurant per call. The database adds ƒ5. */
var PidiOrder = (function () {
  var URL = "https://cdkopyphjvfxjqhasrae.supabase.co";
  var ANON = "";
  function rpc(name, args) {
    return fetch(URL + "/rest/v1/rpc/" + name, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        apikey: ANON,
        authorization: "Bearer " + ANON
      },
      body: JSON.stringify(args)
    }).then(function (res) {
      return res.json().then(function (body) {
        if (!res.ok) throw new Error((body && body.message) || "Try again.");
        return body;
      });
    });
  }
  function statusUrl(orders) {
    var path = location.pathname.indexOf("/restaurant-") === 0 ? "/restaurant-" : "";
    var url = location.origin + path + "/driver/v2/status/#t=" + encodeURIComponent(orders[0].public_token);
    if (orders[1]) url += "&u=" + encodeURIComponent(orders[1].public_token);
    return url;
  }
  function place(group) {
    return rpc("pidi_place_order", { payload: group });
  }
  return { place: place, statusUrl: statusUrl };
})();
```

Replace the WhatsApp `checkoutLink()` send with one `PidiOrder.place` per restaurant group:

```javascript
{
  restaurant: "dushi-wok",
  name: name,
  phone: phone,
  area: area,
  address: address,
  note: note,
  pay: pay === "Bank transfer" ? "transfer" : "cash",
  pays_with_cents: paysWithCents,
  client_token: orderNo + ":" + restaurantSlug,
  items: [{ name: line.n, qty: line.q, price_cents: line.p }]
}
```

On success, `location.href = PidiOrder.statusUrl(results)`. On failure, show the database message. Do not fall back to WhatsApp. The same `client_token` will not create a second order.

Keep the paste box in the kitchen until a real order has been saved this way.

## Kitchen feed

Add `ops/kitchen/live.js` and one button on the kitchen home that calls `PidiLive.open(document.getElementById("main"))`. Keep the chef's big type and 56px buttons. The words are Accept, Cooking, and Ready. Beep only when a new order id appears, not on every refresh.

```javascript
/* Kitchen feed. Polls every 8s. A broadcast ping refetches. No service role. */
var PidiLive = (function () {
  var URL = "https://cdkopyphjvfxjqhasrae.supabase.co";
  var ANON = "";
  var KEY = "pidi.kitchen.session";
  var seen = {};
  function rpc(name, args) {
    return fetch(URL + "/rest/v1/rpc/" + name, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        apikey: ANON,
        authorization: "Bearer " + ANON
      },
      body: JSON.stringify(args || {})
    }).then(function (res) {
      return res.json().then(function (body) {
        if (!res.ok) throw new Error((body && body.message) || "Try again.");
        return body;
      });
    });
  }
  function beep() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator();
      osc.frequency.value = 880;
      osc.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch (e) {}
  }
  function open(root) {
    var saved = sessionStorage.getItem(KEY);
    if (!saved) {
      root.innerHTML = '<h1>Kitchen</h1><input id="pidi-pin" inputmode="numeric" placeholder="PIN"><button type="button" id="pidi-in">Sign in</button>';
      document.getElementById("pidi-in").onclick = function () {
        rpc("pidi_kitchen_login", { pin: document.getElementById("pidi-pin").value }).then(function (data) {
          if (!data || data.ok === false || !data.token) {
            alert((data && data.error) || "That PIN does not match.");
            return;
          }
          sessionStorage.setItem(KEY, JSON.stringify(data));
          open(root);
        }).catch(function (err) { alert(err.message); });
      };
      return;
    }
    var session = JSON.parse(saved);
    function draw() {
      rpc("pidi_kitchen_feed", { session: session.token }).then(function (feed) {
        root.innerHTML = "";
        (feed.orders || []).forEach(function (order) {
          if (!seen[order.id]) { seen[order.id] = true; if (order.status === "new") beep(); }
          var block = document.createElement("section");
          var title = document.createElement("h1");
          title.textContent = order.restaurant + " · " + order.name;
          block.appendChild(title);
          (order.items || []).forEach(function (item) {
            var line = document.createElement("p");
            line.textContent = item.qty + " × " + item.name;
            block.appendChild(line);
          });
          function button(label, fn) {
            var b = document.createElement("button");
            b.type = "button";
            b.textContent = label;
            b.onclick = fn;
            block.appendChild(b);
          }
          if (order.status === "new") button("Accept", function () {
            rpc("pidi_kitchen_accept", { session: session.token, order_id: order.id }).then(draw);
          });
          if (order.status === "accepted") button("Cooking", function () {
            rpc("pidi_kitchen_set_status", { session: session.token, order_id: order.id, status: "cooking" }).then(draw);
          });
          if (order.status === "cooking") button("Ready", function () {
            rpc("pidi_kitchen_set_status", { session: session.token, order_id: order.id, status: "ready" }).then(draw);
          });
          root.appendChild(block);
        });
        if (feed.topic && window.supabase && !window.supabase.__pidiKitchen) {
          window.supabase.__pidiKitchen = true;
          window.supabase.channel(feed.topic, { config: { private: false } })
            .on("broadcast", { event: "changed" }, draw)
            .subscribe();
        }
      }).catch(function () {
        sessionStorage.removeItem(KEY);
      });
    }
    draw();
    setInterval(draw, 8000);
  }
  return { open: open };
})();
```

The broadcast subscribe needs `@supabase/supabase-js` on the page only if you want the ping. The 8 second poll works without it. Do not subscribe to `postgres_changes`. Do not weaken row security.
