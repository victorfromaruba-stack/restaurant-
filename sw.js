/* Order Aruba offline cache.
   Pages, code, styles and menus (HTML, JS, CSS, JSON): network first, so changes show up at once;
   the cached copy is only used when the phone is offline.
   Pictures and fonts: the cached copy shows straight away and is refreshed in the background,
   so a picture replaced at the same path shows up on the next visit. Videos are never cached.
   The chef app (ops/kitchen/) has its own cache. Change CACHE to drop everything stored. */
var CACHE = "orderaruba-v3";
var CORE = ["./", "index.html", "cart.html", "shared/order.css", "shared/hub.css", "shared/order-app.js", "shared/site.json", "shared/fonts/archivo.woff2"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf("orderaruba-") === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function isAsset(url) { return /\.(webp|jpe?g|png|svg|gif|ico|woff2?)$/i.test(url.pathname); }

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin || /\.mp4$/i.test(url.pathname)) return;
  if (isAsset(url)) {
    e.respondWith(caches.open(CACHE).then(function (cache) {
      return cache.match(req).then(function (hit) {
        var net = fetch(req).then(function (res) {
          if (res && res.ok) cache.put(req, res.clone());
          return res;
        });
        if (hit) { e.waitUntil(net.catch(function () {})); return hit; }
        return net;
      });
    }));
    return;
  }
  e.respondWith(fetch(req).then(function (res) {
    if (res && res.ok) {
      var copy = res.clone();
      e.waitUntil(caches.open(CACHE).then(function (c) { return c.put(req, copy); }));
    }
    return res;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: true }).then(function (hit) {
      return hit || (req.mode === "navigate" ? offlinePage() : Response.error());
    });
  }));
});

/* a page this phone never opened, while offline: say so plainly */
function offlinePage() {
  return new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<title>Offline · Order Aruba</title><body style="margin:0;padding:48px 24px;background:#0B1D3A;color:#FFF4DF;font:17px/1.5 system-ui,sans-serif">' +
    '<h1 style="margin:0 0 12px;font-size:28px">You\u2019re offline</h1><p>This page isn\u2019t saved on your phone yet. Check your connection and try again.</p>' +
    '<p><a href="' + self.registration.scope + '" style="color:#FFC93C;font-weight:700">Back to Order Aruba</a></p></body></html>',
    { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
