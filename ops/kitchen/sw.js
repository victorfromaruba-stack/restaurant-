/* Offline cache for the kitchen app.
   App files + data: network first (always fresh when online), cache when offline.
   Dish photos: cached copy first, refreshed in the background (redrawn pictures show up on the next visit). */
var CACHE = 'kitchen-v9';
var CORE = ['./', 'index.html', 'kitchen.css', 'kitchen.js', 'menu-editor.js', 'books.js', 'kitchen-data.json', 'manifest.webmanifest', 'icon.svg', '../../shared/fonts/archivo.woff2'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function isImage(url) { return /\.(webp|jpe?g|png|svg|gif)$/i.test(url.pathname); }

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (isImage(url)) {
    e.respondWith(caches.open(CACHE).then(function (cache) {
      return cache.match(req).then(function (hit) {
        var net = fetch(req).then(function (res) {
          if (res && res.ok) cache.put(req, res.clone());
          return res;
        }).catch(function () { return hit || Response.error(); });
        return hit || net;
      });
    }));
    return;
  }
  e.respondWith(fetch(req).then(function (res) {
    if (res && res.ok && url.pathname.indexOf('/ops/kitchen/') >= 0) {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put(req, copy); });
    }
    return res;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: true }).then(function (hit) {
      return hit || caches.match('index.html');
    });
  }));
});

// The page sends the list of dish photos once it has loaded, so they are there offline too.
self.addEventListener('message', function (e) {
  var d = e.data || {};
  if (d.type !== 'warm' || !Array.isArray(d.urls)) return;
  e.waitUntil(caches.open(CACHE).then(function (cache) {
    return Promise.all(d.urls.map(function (u) {
      return cache.match(u).then(function (hit) {
        if (hit) return null;
        return fetch(u).then(function (res) { if (res.ok) return cache.put(u, res); }).catch(function () { return null; });
      });
    }));
  }));
});
