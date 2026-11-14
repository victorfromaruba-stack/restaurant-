/* The app's offline cache (home page, every restaurant page, checkout and order status).
   Pages, code, styles and menus (HTML, JS, CSS, JSON): network first, so changes show up at once;
   the cached copy is only used when the phone is offline.
   Pictures and fonts: the cached copy shows straight away and is refreshed in the background,
   so a picture replaced at the same path shows up on the next visit. Videos are never cached.
   Only the customer pages are cached here. Change CACHE to drop everything stored. */
var CACHE = "pidi-site-v17";
var CORE = ["./", "index.html", "shared/order.css", "shared/hub.css", "shared/order-app.js", "shared/site.json", "shared/fonts/bigshoulders.woff2", "shared/fonts/hanken.woff2"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    // only this site's old caches (also the ones from before the rename): the chef app and the driver app keep their own
    return Promise.all(keys.filter(function (k) { return (k.indexOf("pidi-site-") === 0 || k.indexOf("orderaruba-") === 0) && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
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
      return res;
    }
    // the host had a bad moment (5xx): the copy on the phone, if there is one, else what the host said
    if (res && res.status >= 500) return caches.match(req, { ignoreSearch: true }).then(function (hit) { return hit || res; });
    return res;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: true }).then(function (hit) {
      return hit || (req.mode === "navigate" ? offlinePage(req.url) : Response.error());
    });
  }));
});

/* a page this phone never opened, while offline: say so plainly (the same look, dark or light) */
function offlinePage(url) {
  var safe = url.replace(/[<>"]/g, "");
  return new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light">' +
    '<title>Offline</title><style>:root{color-scheme:dark;--bg:#100E0C;--text:#F5EDE0;--muted:#B8AC9C;--plate:transparent;--plate-ink:#FFC93C}' +
    '@media (prefers-color-scheme:light){:root{color-scheme:light;--bg:#FFFBF4;--text:#17120D;--muted:#5F5547;--plate:#FFC93C;--plate-ink:#17120D}}' +
    'body{margin:0;padding:48px 24px;background:var(--bg);color:var(--text);font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
    '.m{display:inline-block;margin:0 0 32px;padding:4px 12px;border-radius:9px;background:var(--plate);color:var(--plate-ink);font:900 26px/1.2 "Arial Narrow",Impact,sans-serif;letter-spacing:.03em;text-transform:uppercase}' +
    'h1{margin:0 0 12px;font:900 56px/.9 "Arial Narrow",Impact,sans-serif;text-transform:uppercase}p{margin:0 0 12px;color:var(--muted)}' +
    'a{display:inline-flex;align-items:center;min-height:48px;margin-right:18px;color:var(--text);font-weight:700;text-underline-offset:3px}</style>' +
    '<body><span class="m">Pidi</span><h1>You\u2019re offline</h1><p>This page isn\u2019t saved on your phone yet. Check your connection and try again.</p>' +
    '<a href="' + safe + '">Try again</a><a href="' + self.registration.scope + '">Back to all restaurants</a></body></html>',
    { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
