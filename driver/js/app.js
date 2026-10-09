/* Shared helpers for the Pidi driver app. No framework. */
var Pidi = (function () {
  var STORE = "pidi.driver.v1";
  var ORDER_WHATSAPP = "2977477794";
  var FEE = 500;
  var MIN_FOOD = 2400;
  var MAX_URL = 1800;

  var RESTAURANTS = [
    { id: "dushi-wok", name: "Dushi Wok" },
    { id: "taco-brava", name: "Taco Brava" },
    { id: "smash-shack", name: "Smash Shack" },
    { id: "nonnas-night-in", name: "Nonna's Night In" },
    { id: "oranje-snack", name: "Oranje Snack" }
  ];

  /* Path of this app, with a trailing slash.
     On GitHub Pages that is /restaurant-/driver/ . Locally it is /driver/ .
     The service worker is registered only for this folder. */
  function rootPath() {
    var path = location.pathname;
    var mark = "/driver/";
    var i = path.indexOf(mark);
    if (i === -1) return "./";
    return path.slice(0, i + mark.length);
  }

  function money(cents) {
    var neg = cents < 0;
    var n = Math.abs(Math.round(Number(cents) || 0));
    var florin = Math.floor(n / 100);
    var c = n % 100;
    return (neg ? "-" : "") + "ƒ" + florin + "." + (c < 10 ? "0" : "") + c;
  }

  function parseFlorin(raw) {
    var s = String(raw || "").trim().replace(/ƒ/g, "").replace(/\s/g, "").replace(",", ".");
    if (!/^\d+(\.\d{0,2})?$/.test(s)) return null;
    var parts = s.split(".");
    var florin = parseInt(parts[0], 10);
    var cents = (parts[1] || "").padEnd(2, "0").slice(0, 2);
    return florin * 100 + parseInt(cents || "0", 10);
  }

  function digits(phone) {
    return String(phone || "").replace(/\D/g, "");
  }

  function restaurantName(id, fallback) {
    for (var i = 0; i < RESTAURANTS.length; i++) {
      if (RESTAURANTS[i].id === id) return RESTAURANTS[i].name;
    }
    return fallback || id || "Restaurant";
  }

  function logo(id) {
    for (var i = 0; i < RESTAURANTS.length; i++) {
      if (RESTAURANTS[i].id === id) return rootPath() + "brand/" + id + ".png";
    }
    return "";
  }

  function bytesToB64url(bytes) {
    var bin = "";
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function b64urlToBytes(s) {
    s = String(s).replace(/-/g, "+").replace(/_/g, "/");
    while (s.length % 4) s += "=";
    var bin = atob(s);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function encodeJson(obj) {
    var json = JSON.stringify(obj);
    return "1." + bytesToB64url(new TextEncoder().encode(json));
  }

  /* Pack with gzip when the plain link would be long. Returns the hash body, no #. */
  function encodeRun(obj) {
    var plain = encodeJson(obj);
    if (plain.length < 1400 || typeof CompressionStream === "undefined") {
      return Promise.resolve(plain);
    }
    var stream = new Blob([new TextEncoder().encode(JSON.stringify(obj))]).stream()
      .pipeThrough(new CompressionStream("gzip"));
    return new Response(stream).arrayBuffer().then(function (buf) {
      var packed = "z." + bytesToB64url(new Uint8Array(buf));
      return packed.length < plain.length ? packed : plain;
    });
  }

  function decodeBody(body) {
    if (!body || body.length < 3) throw new Error("short");
    var kind = body.slice(0, 2);
    var data = body.slice(2);
    if (kind === "1.") {
      return Promise.resolve(JSON.parse(new TextDecoder().decode(b64urlToBytes(data))));
    }
    if (kind === "z.") {
      if (typeof DecompressionStream === "undefined") throw new Error("gzip");
      var stream = new Blob([b64urlToBytes(data)]).stream().pipeThrough(new DecompressionStream("gzip"));
      return new Response(stream).arrayBuffer().then(function (buf) {
        return JSON.parse(new TextDecoder().decode(new Uint8Array(buf)));
      });
    }
    throw new Error("kind");
  }

  function validate(o) {
    if (!o || typeof o !== "object") return WORDS.damaged;
    if (o.v !== 1) return WORDS.oldLink;
    if (!o.id) return WORDS.damaged;
    if (!o.pickup) return WORDS.damaged;
    if (!Array.isArray(o.drops) || o.drops.length < 1) return WORDS.noDrops;
    if (o.drops.length > 2) return WORDS.tooMany;
    for (var i = 0; i < o.drops.length; i++) {
      var d = o.drops[i];
      if (!d || !d.name || !d.address) return WORDS.damaged;
      if (d.pay !== "cash" && d.pay !== "transfer") return WORDS.damaged;
      if (typeof d.total !== "number") return WORDS.damaged;
      if (d.pay === "cash" && typeof d.paysWith !== "number") return WORDS.damaged;
      if (!d.restaurant) return WORDS.damaged;
      if (!Array.isArray(d.items) || !d.items.length) return WORDS.damaged;
    }
    return "";
  }

  function hashBody() {
    var h = location.hash.charAt(0) === "#" ? location.hash.slice(1) : location.hash;
    try { h = decodeURIComponent(h); } catch (e) { /* keep raw */ }
    return h;
  }

  function isPayload(body) {
    return body.indexOf("1.") === 0 || body.indexOf("z.") === 0;
  }

  function readStore() {
    try {
      var s = JSON.parse(localStorage.getItem(STORE));
      if (s && s.runs) return s;
    } catch (e) { /* empty */ }
    return { v: 1, runs: {} };
  }

  function writeStore(s) {
    localStorage.setItem(STORE, JSON.stringify(s));
  }

  function stable(v) {
    if (Array.isArray(v)) return "[" + v.map(stable).join(",") + "]";
    if (v && typeof v === "object") {
      return "{" + Object.keys(v).sort().map(function (k) {
        return JSON.stringify(k) + ":" + stable(v[k]);
      }).join(",") + "}";
    }
    return JSON.stringify(v);
  }

  /* America/Aruba is UTC−4, no DST. The service night rolls at 8 AM,
     so 12:30 AM still belongs to the night before. */
  function serviceNight(now) {
    var t = now || new Date();
    var shifted = new Date(t.getTime() - 4 * 3600000 - 8 * 3600000);
    var y = shifted.getUTCFullYear();
    var m = String(shifted.getUTCMonth() + 1).padStart(2, "0");
    var d = String(shifted.getUTCDate()).padStart(2, "0");
    return y + "-" + m + "-" + d;
  }

  function intake(payload) {
    var err = validate(payload);
    if (err) return { error: err };
    var s = readStore();
    var prev = s.runs[payload.id];
    if (prev && stable(prev.payload) === stable(payload)) return { record: prev };
    var rec = {
      id: payload.id,
      night: serviceNight(),
      payload: payload,
      step: "intro",
      dropIndex: 0,
      pickedUpAt: null,
      deliveredAt: payload.drops.map(function () { return null; }),
      receivedAt: new Date().toISOString()
    };
    s.runs[payload.id] = rec;
    writeStore(s);
    return { record: rec };
  }

  function getRun(id) {
    return readStore().runs[id] || null;
  }

  function updateRun(id, fn) {
    var s = readStore();
    if (!s.runs[id]) return null;
    fn(s.runs[id]);
    writeStore(s);
    return s.runs[id];
  }

  function tonightRuns() {
    var night = serviceNight();
    var s = readStore();
    return Object.keys(s.runs).map(function (id) { return s.runs[id]; })
      .filter(function (r) { return r.night === night; });
  }

  function cashCollected(record) {
    var n = 0;
    if (!record || !record.payload) return 0;
    record.payload.drops.forEach(function (d, i) {
      if (d.pay === "cash" && record.deliveredAt && record.deliveredAt[i]) n += d.total;
    });
    return n;
  }

  function pin(stop) {
    if (stop && stop.lat && stop.lng) return String(stop.lat) + "," + String(stop.lng);
    return "";
  }

  function mapsHref(stop) {
    var p = pin(stop);
    if (p) return "https://www.google.com/maps/dir/?api=1&destination=" + p + "&travelmode=driving";
    var q = encodeURIComponent(((stop && stop.address) || "") + ", Aruba");
    return "https://www.google.com/maps/dir/?api=1&destination=" + q + "&travelmode=driving";
  }

  function wazeHref(stop) {
    var p = pin(stop);
    if (p) return "https://waze.com/ul?ll=" + p + "&navigate=yes";
    var q = encodeURIComponent(((stop && stop.address) || "") + ", Aruba");
    return "https://waze.com/ul?q=" + q + "&navigate=yes";
  }

  function telHref(phone) {
    var d = digits(phone);
    return d ? "tel:+" + d : "";
  }

  function waHref(phone, text) {
    var d = digits(phone);
    if (!d) return "";
    return "https://wa.me/" + d + "?text=" + encodeURIComponent(text || "");
  }

  function outsideText(drop) {
    var place = restaurantName(drop.restaurant, drop.restaurantName);
    return "Hi " + drop.name + ", your " + place + " order is outside.";
  }

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (attrs[k] == null || attrs[k] === false) return;
      if (k === "class") n.className = attrs[k];
      else if (k === "text") n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (kid) {
      if (kid == null) return;
      n.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    });
    return n;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function registerSW() {
    if (!("serviceWorker" in navigator)) return;
    var root = rootPath();
    if (root === "./") return;
    navigator.serviceWorker.register(root + "sw.js", { scope: root }).catch(function () {});
  }

  function watchSignal() {
    function paint() {
      var old = document.querySelector(".offline");
      if (navigator.onLine) {
        if (old) old.remove();
        return;
      }
      if (old) return;
      var bar = el("div", { class: "offline", text: WORDS.noSignal });
      document.body.insertBefore(bar, document.body.firstChild);
    }
    window.addEventListener("online", paint);
    window.addEventListener("offline", paint);
    paint();
  }

  function wake() {
    if (!navigator.wakeLock) return;
    navigator.wakeLock.request("screen").catch(function () {});
  }

  function runUrl(hashBodyText) {
    return location.origin + rootPath() + "run.html#" + hashBodyText;
  }

  function pageUrl(file) {
    return rootPath() + file;
  }

  return {
    FEE: FEE,
    MIN_FOOD: MIN_FOOD,
    MAX_URL: MAX_URL,
    ORDER_WHATSAPP: ORDER_WHATSAPP,
    RESTAURANTS: RESTAURANTS,
    rootPath: rootPath,
    money: money,
    parseFlorin: parseFlorin,
    digits: digits,
    restaurantName: restaurantName,
    logo: logo,
    encodeRun: encodeRun,
    encodeJson: encodeJson,
    decodeBody: decodeBody,
    validate: validate,
    hashBody: hashBody,
    isPayload: isPayload,
    intake: intake,
    getRun: getRun,
    updateRun: updateRun,
    tonightRuns: tonightRuns,
    cashCollected: cashCollected,
    serviceNight: serviceNight,
    mapsHref: mapsHref,
    wazeHref: wazeHref,
    telHref: telHref,
    waHref: waHref,
    outsideText: outsideText,
    el: el,
    clear: clear,
    registerSW: registerSW,
    watchSignal: watchSignal,
    wake: wake,
    runUrl: runUrl,
    pageUrl: pageUrl
  };
})();
