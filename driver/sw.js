/* Pidi driver service worker.
   Scope is only the /driver/ folder (on GitHub Pages: /restaurant-/driver/).
   It must not control the customer site. Since 10 Oct 2026 /driver/ opens the v2 app (driver/v2/);
   the v1 pages only send a phone on to v2. */
var CACHE = "pidi-driver-v4";

var FILES = [
  "./",
  "index.html",
  "run.html",
  "cash.html",
  "dispatch.html",
  "help.html",
  "v2/",
  "v2/index.html",
  "v2/run.html",
  "v2/help.html",
  "v2/v2.css",
  "v2/config.js",
  "v2/js/client.js",
  "v2/js/home.js",
  "v2/js/run.js",
  "install/index.html",
  "install/qr.svg",
  "manifest.webmanifest",
  "css/app.css",
  "js/words.js",
  "js/app.js",
  "js/home.js",
  "js/run.js",
  "js/cash.js",
  "js/dispatch.js",
  "js/install.js",
  "brand/wordmark.svg",
  "brand/icon-192.png",
  "brand/icon-512.png",
  "brand/icon-1024.png",
  "brand/apple-touch-icon.png",
  "brand/favicon.svg",
  "brand/favicon-32.png",
  "brand/dushi-wok.png",
  "brand/taco-brava.png",
  "brand/smash-shack.png",
  "brand/nonnas-night-in.png",
  "brand/oranje-snack.png",
  "fonts/jakarta-500.woff2",
  "fonts/jakarta-500-ext.woff2",
  "fonts/jakarta-700.woff2",
  "fonts/jakarta-700-ext.woff2",
  "fonts/jakarta-800.woff2",
  "fonts/jakarta-800-ext.woff2",
  "fonts/bricolage-800.woff2"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return Promise.all(FILES.map(function (file) {
        return cache.add(file).catch(function () {});
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
        return caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

// The page a phone gets offline when not even the driver app's home screen is saved on it yet.
function offline() {
  return new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>No internet</title><body style="margin:0;padding:24px 16px;background:#111;color:#fff;font:20px/1.4 system-ui,sans-serif">' +
    '<h1 style="font-size:30px;margin:0 0 12px">No internet</h1><p>The driver app needs signal the first time. Try again when you have signal.</p>',
    { status: 503, headers: { "content-type": "text/html; charset=utf-8" } });
}

function underDriver(url) {
  return url.origin === self.location.origin && url.pathname.indexOf("/driver/") !== -1;
}

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (!underDriver(url)) return;

  var asset = /\.(png|svg|woff2|webp|jpg|jpeg)$/.test(url.pathname);
  event.respondWith(
    caches.open(CACHE).then(function (cache) {
      if (asset) {
        return cache.match(req).then(function (hit) {
          if (hit) return hit;
          return fetch(req).then(function (res) {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          });
        });
      }
      return fetch(req).then(function (res) {
        if (res && res.ok) cache.put(req, res.clone());
        return res;
      }).catch(function () {
        // Offline. "?…" doesn't make a different page, so it doesn't stop a cached copy from being used.
        // A page that was never cached goes to the v2 home screen by its full address. (Serving the old
        // index.html in its place looped: it forwards to "v2/" relative to the page that failed.)
        return cache.match(req, { ignoreSearch: true }).then(function (hit) {
          if (hit || req.mode !== "navigate") return hit || new Response("", { status: 504 });
          // "install/" is cached as "install/index.html"
          var page = /\/$/.test(url.pathname) ? cache.match(new URL("index.html", url).href) : Promise.resolve(null);
          return page.then(function (doc) {
            if (doc) return doc;
            var home = new URL("v2/" + url.search, self.registration.scope);
            // the v2 home itself was never cached: say so plainly, never send the phone round in a circle
            if (home.pathname === url.pathname) return offline();
            return Response.redirect(home.href, 302);
          });
        });
      });
    })
  );
});
