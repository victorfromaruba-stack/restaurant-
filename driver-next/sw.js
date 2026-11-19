/* Pidi driver PREVIEW service worker (driver-next/, 19 Nov 2026).
   Scope: driver-next/ only (a worker can't reach above its own folder). Its caches are called "next-driver-…",
   a name the live driver app ("pidi-driver-…"), the website ("pidi-site-…") and the kitchen ("kitchen-…") never
   read or delete, and it deletes only its own old "next-driver-" caches: the live apps load exactly what they did.
   Pages, code and the database library: the network first, this phone's copy without signal.
   Fonts and logos: this phone's copy first. A page never saved, without signal: a plain "No signal" page. */
var CACHE = "next-driver-v1";
var MINE = "next-driver-";
var FILES = ["./", "index.html", "run.html", "help.html", "driver.css", "config.js", "js/client.js", "js/home.js", "js/run.js",
  "manifest.webmanifest", "../driver/v2/config.js", "../shared/fonts/bigshoulders.woff2", "../shared/fonts/hanken.woff2",
  "../driver/brand/favicon.svg", "../driver/brand/apple-touch-icon.png"];

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(CACHE).then(function (cache) {
    return Promise.all(FILES.map(function (f) { return cache.add(f).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf(MINE) === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function noSignal() {
  return new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<meta name="color-scheme" content="dark light"><title>No signal</title><body style="margin:0;padding:32px 20px;background:#100E0C;color:#F5EDE0;font:19px/1.45 system-ui,sans-serif">' +
    '<h1 style="font:900 44px/1 Impact,\'Arial Narrow\',sans-serif;text-transform:uppercase;margin:0 0 12px">No signal</h1>' +
    '<p>The driver app needs signal the first time it opens on this phone. Try again when you have signal.</p>',
    { status: 503, headers: { "content-type": "text/html; charset=utf-8" } });
}

// what this worker answers: its own folder, the files it borrows (fonts, logos, the live settings file), the library
function mine(url) {
  if (url.origin === self.location.origin) {
    return url.pathname.indexOf("/driver-next/") !== -1 || /\/shared\/fonts\/|\/driver\/brand\/|\/driver\/v2\/config\.js$/.test(url.pathname);
  }
  return url.hostname === "cdn.jsdelivr.net";
}

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (!mine(url)) return;
  var asset = url.origin === self.location.origin && /\.(png|svg|woff2|webp|jpe?g)$/.test(url.pathname);
  event.respondWith(caches.open(CACHE).then(function (cache) {
    if (asset) {
      return cache.match(req).then(function (hit) {
        return hit || fetch(req).then(function (res) { if (res && res.ok) cache.put(req, res.clone()); return res; });
      });
    }
    return fetch(req).then(function (res) {
      if (res && res.ok) cache.put(req, res.clone());
      return res;
    }).catch(function () {
      return cache.match(req, { ignoreSearch: true }).then(function (hit) {
        if (hit) return hit;
        if (req.mode !== "navigate") return Response.error();
        return cache.match(new URL("index.html", self.registration.scope).href).then(function (home) { return home || noSignal(); });
      });
    });
  }));
});
