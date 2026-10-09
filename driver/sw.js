/* Pidi driver service worker.
   Scope is only the /driver/ folder (on GitHub Pages: /restaurant-/driver/).
   It must not control the customer site. */
var CACHE = "pidi-driver-v1";

var FILES = [
  "./",
  "index.html",
  "run.html",
  "cash.html",
  "dispatch.html",
  "help.html",
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
        return cache.match(req).then(function (hit) {
          if (hit) return hit;
          if (req.mode === "navigate") return cache.match("index.html");
          return new Response("", { status: 504 });
        });
      });
    })
  );
});
