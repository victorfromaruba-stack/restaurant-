/* Offline cache for the kitchen app.
   App files, data, site.json and the menus: the network when it answers within 3 seconds, else the copy saved
   on this phone (a weak kitchen signal never leaves a blank screen). The network answer still comes in behind
   it and updates that copy. Offline: the copy.
   Dish photos: cached copy first, refreshed in the background (redrawn pictures show up on the next visit).
   Only this app's own caches (names starting with "kitchen-") are ever deleted: the website and the driver
   app keep theirs. */
var CACHE = 'kitchen-v18';
var MINE = 'kitchen-';
var WAIT = 3000;
var CORE = ['./', 'index.html', 'kitchen.css', 'kitchen.js', 'menu-editor.js', 'books.js', 'live.js', '../../shared/pidi.js', 'kitchen-data.json',
  'manifest.webmanifest', 'icon.svg', '../../shared/fonts/archivo.woff2', '../../shared/site.json'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(CORE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf(MINE) === 0 && k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function isImage(url) { return /\.(webp|jpe?g|png|svg|gif)$/i.test(url.pathname); }
// what is kept for offline: this app, site.json, pidi.js, the fonts and every restaurant's menu.json
function keep(url) {
  var p = url.pathname;
  return p.indexOf('/ops/kitchen/') >= 0 || /\/shared\/(site\.json|pidi\.js|fonts\/)/.test(p) || /\/menu\.json$/.test(p);
}
function saved(req) {
  return caches.open(CACHE).then(function (c) { return c.match(req, { ignoreSearch: true }); });
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // "?fresh=…": the Orders screen reading the website itself, to send the menus to the order database. Never a
  // saved copy: the phone's own network answer or nothing.
  if (url.searchParams.has('fresh')) return;
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
  var net = fetch(req).then(function (res) {
    if (!res || !res.ok || !keep(url)) return res;
    var copy = res.clone();
    return caches.open(CACHE).then(function (c) { return c.put(req, copy); }).then(function () { return res; }, function () { return res; });
  });
  e.waitUntil(net.catch(function () {}));   // the copy keeps updating after a cached answer
  e.respondWith(new Promise(function (answer) {
    var done = false;
    function give(r) { if (!done) { done = true; clearTimeout(slow); answer(r); } }
    function fallback() {
      return saved(req).then(function (hit) {
        if (hit) return hit;
        return req.mode === 'navigate' ? saved('index.html').then(function (p) { return p || Response.error(); }) : Response.error();
      });
    }
    // slow network: the saved copy after 3 seconds; nothing saved yet: keep waiting for the network
    var slow = setTimeout(function () { saved(req).then(function (hit) { if (hit) give(hit); }); }, WAIT);
    net.then(function (res) {
      if (res && res.status >= 500) return saved(req).then(function (hit) { give(hit || res); });
      give(res);
    }, function () { fallback().then(give); });
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
