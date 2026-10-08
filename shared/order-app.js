/* Order Aruba — one ordering engine for the home page, every restaurant page and the cart page.
   Menus live in <restaurant>/menu.json. Shop settings (WhatsApp number, hours, areas, delivery fee,
   which restaurants are open) live in shared/site.json. Prices are in cents: 1295 = ƒ12.95.
   No framework, no build step. */
(function () {
  "use strict";

  var BODY = document.body;
  var ROOT = BODY.getAttribute("data-root") || "";
  var PAGE = BODY.getAttribute("data-page") || "hub";
  var HERE = BODY.getAttribute("data-brand") || null;
  var KEY = "orderaruba.cart.v2";
  var LAST_KEY = "orderaruba.last.v1";
  var OLD_KEY = "brandhub.crosscart.v1";
  var OLD_NAMES = { "Dushi Wok": "dushi-wok", "Taco Brava": "taco-brava", "Smash Shack": "smash-shack",
    "Nonna's Night In": "nonnas-night-in", "Nonna’s Night In": "nonnas-night-in", "Oranje Snack": "oranje-snack" };
  var MAX_QTY = 20;
  var OTHER = "Other area";
  var OTHER_NOTE = "Outside our usual area. We\u2019ll confirm on WhatsApp if we can reach you, and the fee.";
  var WA_URL_LIMIT = 1900;
  var DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  var DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var DAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var ALLERGEN_NAMES = { gluten: "gluten", egg: "egg", soy: "soy", dairy: "milk", shellfish: "shellfish", sesame: "sesame",
    peanut: "peanuts", mustard: "mustard", fish: "fish", nuts: "tree nuts", celery: "celery" };
  var FLAG_NAMES = { shrimp: "Contains shrimp", pork: "Contains pork", peanut: "Contains peanuts", spicy: "Spicy", vegetarian: "Vegetarian" };

  /* ---------------------------------------------------------------- helpers */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function money(c) { return "ƒ" + (Math.round(c) / 100).toFixed(2); }
  function shortMoney(c) { return "ƒ" + (c % 100 === 0 ? String(c / 100) : (c / 100).toFixed(2)); }
  function path(p) { return ROOT + p; }
  /* small square pictures for menu rows (build/thumbs.py makes them); drinks are small already */
  function thumb(img) { return String(img).replace(/([^/]+)$/, "thumbs/$1"); }   // same file name, in thumbs/
  function thumbImg(item, attrs) {
    if (item.kind === "drink") return '<img src="' + esc(path(item.img)) + '" alt="" width="360" height="360"' + attrs + ">";
    return '<img src="' + esc(path(thumb(item.img))) + '" data-full="' + esc(path(item.img)) + '" alt="" width="360" height="360"' + attrs + ">";
  }
  // a missing thumbnail falls back to the full picture instead of a broken image
  document.addEventListener("error", function (e) {
    var t = e.target, full = t && t.tagName === "IMG" && t.getAttribute("data-full");
    if (full) { t.removeAttribute("data-full"); t.src = full; }
  }, true);
  function el(html) { var t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }
  function clean(s) { return String(s || "").trim().replace(/\s+/g, " "); }
  function plural(n, one, many) { return n + " " + tr(n === 1 ? one : many); }

  /* ---------------------------------------------------------------- languages
     Screen text in English, Papiamento, Dutch or Spanish, picked from the phone's language or the switch
     at the bottom of each page. Translations live in shared/lang/<code>.json ({"English text": "translation"});
     anything missing shows in English. The WhatsApp ticket, menu names and descriptions stay in English. */
  var LANGS = ["en", "pap", "nl", "es"];
  var LANG_KEY = "orderaruba.lang.v1";
  var WORDS = {};
  function pickLang() {
    try { var saved = localStorage.getItem(LANG_KEY); if (LANGS.indexOf(saved) >= 0) return saved; } catch (e) { /* private mode */ }
    var list = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || "en"];
    for (var i = 0; i < list.length; i++) {
      var code = String(list[i]).toLowerCase().split("-")[0];
      if (code === "pa" && /aw|cw|bq/i.test(list[i])) code = "pap";
      if (LANGS.indexOf(code) >= 0) return code;
    }
    return "en";
  }
  var LANG = pickLang();
  function loadLang() {
    if (LANG === "en") return Promise.resolve();
    return getJSON("shared/lang/" + LANG + ".json").then(function (w) { WORDS = w || {}; }, function () { WORDS = {}; });
  }
  /* tr("Open until {time}", {time: "2 AM"}): the translation if there is one, else the English */
  function tr(text, vars) {
    var out = (LANG !== "en" && WORDS[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return vars[k] != null ? vars[k] : m; });
    return out;
  }
  /* times on screen: 10 PM in English, 22:00 in the other languages (the ticket always uses 10 PM) */
  function clock(m) {
    if (LANG === "en") return fmtTime(m);
    return String(Math.floor(m / 60) % 24).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  }
  /* the fixed words in the HTML files: data-t on an element (its text), data-t-attr="placeholder,aria-label" */
  function translatePage() {
    document.documentElement.lang = LANG;
    if (LANG === "en") return;
    $$("[data-t]").forEach(function (n) {
      if (!n.hasAttribute("data-t-en")) n.setAttribute("data-t-en", n.getAttribute("data-t") || n.textContent);
      n.textContent = tr(n.getAttribute("data-t-en"));
    });
    $$("[data-t-attr]").forEach(function (n) {
      n.getAttribute("data-t-attr").split(",").forEach(function (a) { if (n.hasAttribute(a)) n.setAttribute(a, tr(n.getAttribute(a))); });
    });
  }
  function langSwitch() {
    return '<div class="langs" role="group" aria-label="' + esc(tr("Language")) + '">' + LANGS.map(function (c) {
      return '<button type="button" lang="' + c + '" data-lang="' + c + '" aria-pressed="' + (c === LANG) + '">' + { en: "EN", pap: "PAP", nl: "NL", es: "ES" }[c] + "</button>";
    }).join("") + "</div>";
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-lang]");
    if (!b || b.getAttribute("data-lang") === LANG) return;
    try { localStorage.setItem(LANG_KEY, b.getAttribute("data-lang")); } catch (err) { /* private mode */ }
    location.reload();
  });

  var ICON = {
    bag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M5 8h14l-1.2 11.1a2 2 0 0 1-2 1.9H8.2a2 2 0 0 1-2-1.9L5 8Zm4 0V6.5a3 3 0 0 1 6 0V8"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" d="M12 5v14M5 12h14"/></svg>',
    minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" d="M5 12h14"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" d="M6 6l12 12M18 6 6 18"/></svg>',
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M15 5l-7 7 7 7"/></svg>',
    flame: '<svg viewBox="0 0 34 50" aria-hidden="true"><path fill="currentColor" d="M17,0 C21.2,11 34,19 34,32 C34,44 26,50 17,50 C8,50 0,44 0,32 C0,23 8,18 11,9 C13,17 15,20 18,22 C20,14 19,6 17,0 Z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.5v13l11-6.5z"/></svg>',
    share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M12 3v12M7.5 7.5 12 3l4.5 4.5M8 11H6.5A1.5 1.5 0 0 0 5 12.5v7A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5v-7a1.5 1.5 0 0 0-1.5-1.5H16"/></svg>',
    check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    wa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.83c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.13-.15.17-.25.25-.42.08-.16.04-.31-.02-.43-.06-.13-.56-1.35-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.29Z"/></svg>'
  };

  /* ---------------------------------------------------------------- data */
  var SITE = null;
  var MENU = {};          // id -> loaded menu (sync access)
  var pending = {};       // id -> promise
  function getJSON(p) {
    return fetch(path(p), { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(p + " " + r.status);
      return r.json();
    });
  }
  function loadSite() { return getJSON("shared/site.json").then(function (s) { SITE = s; return s; }); }
  function loadMenu(id) {
    if (MENU[id]) return Promise.resolve(MENU[id]);
    if (!pending[id]) {
      pending[id] = getJSON(id + "/menu.json").then(function (m) {
        m.byId = {};
        m.items.forEach(function (it) { m.byId[it.id] = it; });
        MENU[id] = m;
        refreshLines(id);
        return m;
      });
    }
    return pending[id];
  }
  function brandStatus(id) {
    var b = (SITE.brands || []).filter(function (x) { return x.id === id; })[0];
    return b ? b.status || "open" : "hidden";
  }
  function brandList(includeHidden) {
    return (SITE.brands || []).filter(function (b) { return includeHidden || b.status !== "hidden"; }).map(function (b) { return b.id; });
  }

  /* ---------------------------------------------------------------- hours */
  function arubaNow() {
    var n = new Date();
    return new Date(n.getTime() + (n.getTimezoneOffset() + (SITE.utcOffset || -4) * 60) * 60000);
  }
  function mins(hhmm) { var p = hhmm.split(":"); return (+p[0]) * 60 + (+p[1]); }
  function fmtTime(m) {
    var hh = Math.floor(m / 60) % 24, mm = m % 60, ap = hh >= 12 ? "PM" : "AM";
    hh = hh % 12 || 12;
    return hh + (mm ? ":" + String(mm).padStart(2, "0") : "") + " " + ap;
  }
  /* Hours can cross midnight: ["22:00","02:00"] = opens 10 PM, closes 2 AM the next morning. */
  function windowFor(dayIdx) {
    var h = SITE.hours[DAYS[(dayIdx + 7) % 7]];
    if (!h) return null;
    var o = mins(h[0]), c = mins(h[1]);
    if (c <= o) c += 24 * 60;
    return { o: o, c: c };
  }
  /* Last orders: site.json "lastOrder" (e.g. "01:30"). New orders stop then; the kitchen finishes what it has. */
  function cutFor(w) {
    if (!w) return w;
    var cut = w.c;
    if (SITE.lastOrder) {
      var lo = mins(SITE.lastOrder);
      if (lo <= w.o % 1440) lo += 1440;
      if (lo > w.o && lo < w.c) cut = lo;
    }
    return { o: w.o, c: w.c, cut: cut };
  }
  function kitchenStatus() {
    var t = arubaNow(), d = t.getDay(), now = t.getHours() * 60 + t.getMinutes();
    var wins = [];
    var y = cutFor(windowFor(d - 1)), w = cutFor(windowFor(d));
    if (y) wins.push({ o: y.o - 1440, c: y.c - 1440, cut: y.cut - 1440 });
    if (w) wins.push(w);
    for (var k = 0; k < wins.length; k++) {
      var x = wins[k];
      if (now >= x.o && now < x.cut) {
        var left = x.cut - now, hasCut = x.cut < x.c;
        var last = left <= 30 && hasCut;
        return { open: true, soon: left <= 30, lastOrder: hasCut ? clock(x.cut) : "",
          label: last ? tr("Last orders {time}", { time: clock(x.cut) }) : tr("Open until {time}", { time: clock(x.c) }),
          sub: last ? tr("Last orders {time}", { time: clock(x.cut) }) : tr("until {time}", { time: clock(x.c) }) };
      }
    }
    var finishing = wins.some(function (x) { return now >= x.cut && now < x.c; });
    var res = null;
    if (w && now < w.o) res = { label: tr(w.o >= 18 * 60 ? "Opens tonight {time}" : "Opens today {time}", { time: clock(w.o) }) };
    for (var i = 1; i <= 7 && !res; i++) {
      var n = windowFor(d + i);
      if (n) {
        res = { label: i === 1 ? tr(n.o >= 18 * 60 ? "Opens tomorrow night {time}" : "Opens tomorrow {time}", { time: clock(n.o) })
          : tr("Opens {day} {time}", { day: tr(DAY_NAMES[(d + i) % 7]), time: clock(n.o) }) };
      }
    }
    res = res || { label: tr("Closed") };
    res.open = false;
    res.finishing = finishing;
    return res;
  }
  function hoursLabel() {
    var vals = DAYS.map(function (d) { return SITE.hours[d] ? SITE.hours[d].join("-") : "x"; });
    var first = SITE.hours.mon;
    if (vals.every(function (v) { return v === vals[0]; }) && first) {
      var night = mins(first[1]) <= mins(first[0]) || mins(first[0]) >= 18 * 60;
      return tr(night ? "Every night" : "Every day") + ", " + clock(mins(first[0])) + "\u2013" + clock(mins(first[1]));
    }
    return DAYS.map(function (d, i) {
      var h = SITE.hours[d];
      return tr(DAY_SHORT[i]) + " " + (h ? clock(mins(h[0])) + "\u2013" + clock(mins(h[1])) : tr("closed"));
    }).join(", ");
  }

  /* ---------------------------------------------------------------- cart store */
  var memState = null;
  function blank() { return { v: 2, lines: [], mode: "delivery", area: "", addr: "", name: "", note: "", pay: "", no: "", sentAt: 0, updated: 0 }; }
  function readStore() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY));
      if (s && s.v === 2 && Array.isArray(s.lines)) return s;
    } catch (e) { return memState || blank(); }
    return migrate() || memState || blank();
  }
  function migrate() {
    try {
      var o = JSON.parse(localStorage.getItem(OLD_KEY));
      if (!o || !o.brands) return null;
      var s = blank();
      Object.keys(o.brands).forEach(function (n) {
        var b = OLD_NAMES[n], br = o.brands[n];
        if (!b || !br) return;
        Object.keys(br.cart || {}).forEach(function (id) {
          var q = parseInt(br.cart[id], 10) || 0, snap = (br.menuSnapshot || {})[id] || {};
          if (q > 0) s.lines.push({ k: lineKey(b, id, {}), b: b, id: id, q: Math.min(q, MAX_QTY), o: {}, d: [], n: snap.n || id, p: snap.p || 0 });
        });
      });
      ["mode", "name", "addr", "note"].forEach(function (k) { if (o[k]) s[k] = o[k]; });
      localStorage.removeItem(OLD_KEY);
      writeStore(s, true);
      return s;
    } catch (e) { return null; }
  }
  var listeners = [];
  function onChange(fn) { listeners.push(fn); }
  function emit() { listeners.forEach(function (fn) { try { fn(); } catch (e) { console.error(e); } }); }
  function writeStore(s, silent) {
    s.updated = Date.now();
    memState = s;
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode: keep in memory */ }
    if (!silent) emit();
  }
  var state = null;
  var SENT_KEEP = 3 * 3600 * 1000;   // a sent order stays on screen for 3 hours, then the bag is empty again
  function S() { if (!state) { state = readStore(); tidy(state); } return state; }
  /* drinks are one shared group: one Coke line, whichever restaurant it was added from */
  function isDrinkLine(l) { return l.dr || /^(ck|cz|sp)$/.test(l.id); }
  function tidy(s) {
    var seen = {}, changed = false;
    s.lines = s.lines.filter(function (l) {
      if (!isDrinkLine(l)) return true;
      l.dr = true;
      var k = "drink|" + l.id;
      if (seen[k]) { seen[k].q = Math.min(MAX_QTY, seen[k].q + l.q); changed = true; return false; }
      seen[k] = l; if (l.k !== k) { l.k = k; changed = true; }
      return true;
    });
    if (s.sentAt && Date.now() - s.sentAt > SENT_KEEP) { retire(s); changed = true; }
    if (changed) writeStore(s, true);
  }
  /* the sent order is already saved as "Order again"; empty the bag and forget its number */
  function retire(s) { s.lines = []; s.no = ""; s.sentAt = 0; s.note = ""; s.when = ""; }
  function commit() { writeStore(state); }
  window.addEventListener("storage", function (e) { if (e.key === KEY) { state = readStore(); emit(); } });

  function lineKey(b, id, o) {
    var parts = Object.keys(o || {}).sort().map(function (g) {
      var v = o[g];
      return g + "=" + (Array.isArray(v) ? v.slice().sort().join("+") : v);
    });
    return b + "|" + id + "|" + parts.join("&");
  }
  function normOpts(item, o) {
    var out = {};
    (item.options || []).forEach(function (g) {
      var v = o && o[g.id];
      if (g.type === "one") {
        var ok = g.choices.some(function (c) { return c.id === v; });
        out[g.id] = ok ? v : g["default"];
      } else {
        var arr = Array.isArray(v) ? v.filter(function (x) { return g.choices.some(function (c) { return c.id === x; }); }) : [];
        if (arr.length) out[g.id] = arr.sort();
      }
    });
    return out;
  }
  function unitPrice(item, o) {
    var p = item.price;
    (item.options || []).forEach(function (g) {
      var v = o[g.id];
      g.choices.forEach(function (c) {
        if (c.price && (v === c.id || (Array.isArray(v) && v.indexOf(c.id) >= 0))) p += c.price;
      });
    });
    return p;
  }
  function describe(item, o) {
    var out = [];
    (item.options || []).forEach(function (g) {
      var v = o[g.id];
      if (g.type === "one") {
        if (v && v !== g["default"]) {
          var c = g.choices.filter(function (x) { return x.id === v; })[0];
          if (c) out.push(g.label + ": " + c.label);
        }
      } else if (Array.isArray(v) && v.length) {
        var labels = g.choices.filter(function (c) { return v.indexOf(c.id) >= 0; }).map(function (c) { return c.label; });
        if (g.id === "leave") out = out.concat(labels);
        else out.push(g.label + ": " + labels.join(", "));
      }
    });
    return out;
  }
  function includesNames(menu, item) {
    return (item.includes || []).map(function (id) { return menu.byId[id] ? menu.byId[id].name : id; });
  }
  var freshStart = false;
  function addItem(b, id, opts, qty) {
    var menu = MENU[b], item = menu && menu.byId[id];
    if (!item || item.soldOut || brandStatus(b) !== "open") return null;
    var o = normOpts(item, opts || {});
    var drink = item.kind === "drink";
    var k = drink ? "drink|" + id : lineKey(b, id, o);
    var s = S();
    if (s.sentAt) { retire(s); freshStart = true; }
    var line = s.lines.filter(function (l) { return l.k === k; })[0];
    if (line) line.q = Math.min(MAX_QTY, line.q + (qty || 1));
    else {
      line = { k: k, b: b, id: id, q: Math.min(MAX_QTY, qty || 1), o: o, d: describe(item, o), n: item.name, p: unitPrice(item, o) };
      if (drink) line.dr = true;
      if (item.includes) line.inc = includesNames(menu, item);
      s.lines.push(line);
    }
    commit();
    return line;
  }
  /* toast text after an add; says so once when a new order started after a sent one */
  function addedMsg(text) {
    if (!freshStart) return text;
    freshStart = false;
    return tr("New order started.") + " " + text;
  }
  function setLineQty(k, q) {
    var s = S();
    s.lines = s.lines.filter(function (l) {
      if (l.k !== k) return true;
      l.q = Math.max(0, Math.min(MAX_QTY, q));
      return l.q > 0;
    });
    commit();
  }
  function refreshLines(b) {
    var s = S(), menu = MENU[b], changed = false;
    s.lines.forEach(function (l) {
      if (l.b !== b) return;
      var item = menu.byId[l.id];
      if (!item) { if (!l.gone) { l.gone = true; changed = true; } return; }
      var o = normOpts(item, l.o), p = unitPrice(item, o);
      if (l.n !== item.name || l.p !== p || l.gone) { l.n = item.name; l.p = p; l.gone = false; changed = true; }
      l.d = describe(item, o);
      if (item.includes) l.inc = includesNames(menu, item);
      l.soldOut = !!item.soldOut;
    });
    if (changed) commit();
  }
  function liveLines() { return S().lines.filter(function (l) { return !l.gone && l.q > 0; }); }
  function count() { return liveLines().reduce(function (n, l) { return n + l.q; }, 0); }
  function itemCount(b, id) { return liveLines().reduce(function (n, l) { return n + (l.b === b && l.id === id ? l.q : 0); }, 0); }
  function subtotal() { return liveLines().reduce(function (n, l) { return n + l.q * l.p; }, 0); }
  function fee() { return S().mode === "delivery" && count() > 0 ? SITE.deliveryFee : 0; }
  function total() { return subtotal() + fee(); }
  /* restaurants with food in the order (drinks don't count unless the order is only drinks) */
  function brandsInCart() {
    var lines = liveLines(), food = lines.filter(function (l) { return !isDrinkLine(l); });
    var use = food.length ? food : lines.slice(0, 1), seen = [];
    brandList(true).forEach(function (b) { if (use.some(function (l) { return l.b === b; })) seen.push(b); });
    use.forEach(function (l) { if (seen.indexOf(l.b) < 0) seen.push(l.b); });
    return seen;
  }
  function foodLines(b) { return liveLines().filter(function (l) { return l.b === b && !isDrinkLine(l); }); }
  function drinkLines() { return liveLines().filter(isDrinkLine); }
  /* menus needed to show the order: every restaurant with a line in it, drinks included */
  function menusInCart() {
    var ids = [];
    liveLines().forEach(function (l) { if (ids.indexOf(l.b) < 0) ids.push(l.b); });
    return ids;
  }
  function brandName(b) { return MENU[b] ? MENU[b].name : b.replace(/-/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); }); }
  /* Order number = Aruba time it was sent + 2 letters, e.g. 2314-K7. Readable on the phone, and
     two orders only share a number if they're sent in the same minute AND draw the same letters. */
  var NO_CHARS = "ACDEFGHJKLMNPRTUVWXY34679";
  function newOrderNo() {
    var t = arubaNow(), r = "";
    for (var i = 0; i < 2; i++) r += NO_CHARS.charAt(Math.floor(Math.random() * NO_CHARS.length));
    return String(t.getHours()).padStart(2, "0") + String(t.getMinutes()).padStart(2, "0") + "-" + r;
  }
  function orderNo() {
    var s = S();
    if (!s.no) { s.no = newOrderNo(); writeStore(s, true); }
    return s.no;
  }
  function clearOrder() {
    var s = S();
    retire(s);
    commit();
  }

  /* ---------------------------------------------------------------- order time: as soon as possible, or a slot tonight */
  function slotLabel(m) { m = m % 1440; return m === 0 ? "Midnight" : fmtTime(m); }
  function slotText(m) { m = m % 1440; return m === 0 ? tr("Midnight") : clock(m); }
  /* Time choices run from 30 min after opening (or 45 min from now) until last orders, never the closing minute itself. */
  function timeSlots() {
    var t = arubaNow(), d = t.getDay(), now = t.getHours() * 60 + t.getMinutes();
    var st = kitchenStatus(), win = null, prefix = "";
    function endOf(x, shift) { return (x.cut < x.c ? x.cut : x.c - 15) + shift; }
    var y = cutFor(windowFor(d - 1)), w = cutFor(windowFor(d));
    if (y && y.cut > 1440 && now < y.cut - 1440) win = { o: y.o - 1440, end: endOf(y, -1440) };
    else if (w && now < w.cut) win = { o: w.o, end: endOf(w, 0) };
    else { var n = cutFor(windowFor(d + 1)); if (n) { win = { o: n.o + 1440, end: endOf(n, 1440) }; prefix = "Tomorrow "; } }
    var slots = [];
    if (win) {
      var start = Math.ceil(Math.max(win.o + 30, now + 45) / 15) * 15;
      for (var m = start; m <= win.end; m += 15) slots.push({ v: prefix + slotLabel(m), d: (prefix ? tr("Tomorrow") + " " : "") + slotText(m) });
    }
    return { asap: st.open, slots: slots };
  }
  function validWhen() {
    var s = S(), ts = timeSlots();
    if (s.when && ts.slots.some(function (x) { return x.v === s.when; })) return s.when;
    return ts.asap ? "" : (ts.slots[0] ? ts.slots[0].v : "");
  }

  /* ---------------------------------------------------------------- WhatsApp ticket */
  function buildMessage() {
    var s = S(), lines = liveLines(), brands = brandsInCart(), out = [];
    var no = "#" + orderNo();
    if (brands.length === 1) out.push("*" + brandName(brands[0]) + " order* " + no);
    else out.push("*Kitchen order* " + no + " · " + brands.length + " restaurants");
    out.push(s.mode === "delivery" ? "Delivery · " + (s.area ? s.area + (s.area === OTHER ? " (please confirm)" : "") : "area not set") : "Pickup");
    out.push("Time: " + (validWhen() || "As soon as possible"));
    if (!kitchenStatus().open) out.push("Pre-order: sent while you were closed");
    out.push("");
    function put(l) {
      out.push(l.q + " × " + l.n + " — " + money(l.q * l.p));
      if (l.inc && l.inc.length) out.push("   Includes: " + l.inc.join(", "));
      if (l.d && l.d.length) out.push("   " + l.d.join(" · "));
    }
    var drinks = drinkLines(), onlyDrinks = drinks.length === lines.length;
    brands.forEach(function (b) {
      if (brands.length > 1) out.push("*" + brandName(b) + "*");
      (onlyDrinks ? [] : foodLines(b)).forEach(put);
    });
    if (drinks.length) {
      if (brands.length > 1) out.push("*Drinks*");
      drinks.forEach(put);
    }
    out.push("");
    out.push("Subtotal " + money(subtotal()));
    out.push(s.mode === "delivery" ? "Delivery " + money(fee()) : "Pickup " + money(0));
    out.push("*Total " + money(total()) + "*");
    if (payOptions().length) out.push("Pay: " + (payOptions().indexOf(s.pay) >= 0 ? s.pay : "-"));
    out.push("");
    out.push("Name: " + (clean(s.name) || "-"));
    if (s.mode === "delivery") out.push("Address: " + (clean(s.addr) || "-"));
    if (clean(s.note)) out.push("Note: " + clean(s.note));
    return out.join("\n");
  }
  /* how to pay: site.json "payment", e.g. "Pay the driver in cash (florin or US$) or by card." Empty = say nothing. */
  /* site.json "payWith": the ways to pay the customer taps at checkout (it goes on the ticket as "Pay: Cash"),
     with the "payment" sentence under them. Without it, the sentence is shown above Send instead. */
  function payOptions() { return Array.isArray(SITE.payWith) ? SITE.payWith : []; }
  function payLine() { return SITE.payment && !payOptions().length ? clean(tr(SITE.payment)) + " " : ""; }
  function waLink(text) { return "https://wa.me/" + SITE.whatsapp + "?text=" + encodeURIComponent(text); }
  function checkoutLink() {
    var full = buildMessage(), u = waLink(full);
    if (u.length <= WA_URL_LIMIT) return { url: u, full: full, short: false };
    var first = full.split("\n")[0];
    return { url: waLink(first + "\nMy full order is copied — pasting it here."), full: full, short: true };
  }

  /* ---------------------------------------------------------------- toast */
  var toastT;
  function toast(msg) {
    var t = $("#oa-toast");
    if (!t) { t = el('<div id="oa-toast" class="oa-toast" role="status" aria-live="polite" hidden></div>'); BODY.appendChild(t); }
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(function () { t.hidden = true; }, 2600);
  }
  /* the bag gives a small bounce (and a tiny buzz on Android) when something goes in */
  function bump() {
    $$(".bag, #oa-bar .bar__btn").forEach(function (b) { b.classList.remove("bump"); void b.offsetWidth; b.classList.add("bump"); });
    try { if (navigator.vibrate && !matchMedia("(prefers-reduced-motion: reduce)").matches) navigator.vibrate(8); } catch (e) { /* not supported */ }
  }
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }
  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
    BODY.appendChild(ta); ta.select(); ta.setSelectionRange(0, text.length);
    var ok = false; try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove(); return ok;
  }

  /* ---------------------------------------------------------------- sheets (dialogs) */
  var openSheets = [];
  function openSheet(node, opts) {
    opts = opts || {};
    var wrap = el('<div class="oa-sheet" role="presentation"><div class="oa-sheet__scrim" data-close></div>' +
      '<div class="oa-sheet__panel" role="dialog" aria-modal="true"></div></div>');
    var panel = $(".oa-sheet__panel", wrap);
    if (opts.label) panel.setAttribute("aria-label", opts.label);
    if (opts.cls) panel.classList.add(opts.cls);
    panel.appendChild(node);
    BODY.appendChild(wrap);
    var rec = { wrap: wrap, last: document.activeElement, onClose: opts.onClose };
    openSheets.push(rec);
    BODY.classList.add("oa-lock");
    paintBar();
    requestAnimationFrame(function () { wrap.classList.add("is-open"); });
    wrap.addEventListener("click", function (e) { if (e.target.closest("[data-close]")) closeSheet(rec); });
    setTimeout(function () { var f = $("[data-autofocus]", panel) || $(".x", panel); if (f) f.focus({ preventScroll: true }); }, 60);
    return rec;
  }
  function closeSheet(rec) {
    rec = rec || openSheets[openSheets.length - 1];
    if (!rec) return;
    openSheets = openSheets.filter(function (r) { return r !== rec; });
    rec.wrap.classList.remove("is-open");
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTimeout(function () { rec.wrap.remove(); }, reduce ? 0 : 220);
    if (!openSheets.length) BODY.classList.remove("oa-lock");
    if (rec.onClose) rec.onClose();
    if (rec.last && rec.last.focus) rec.last.focus({ preventScroll: true });
    paintBar();
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && openSheets.length) closeSheet();
    if (e.key === "Tab" && openSheets.length) {
      var panel = $(".oa-sheet__panel", openSheets[openSheets.length - 1].wrap);
      var f = $$("a[href],button:not([disabled]),input,textarea,[tabindex]:not([tabindex='-1'])", panel).filter(function (n) { return n.offsetParent !== null; });
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  });

  /* ---------------------------------------------------------------- small UI helpers */
  function flagText(item) {
    return (item.flags || []).map(function (f) { return '<span class="fl fl--' + esc(f) + '">' + esc(tr(FLAG_NAMES[f] || f)) + "</span>"; }).join("");
  }
  /* What the recipe contains, plus the honest part: one kitchen cooks everything, so traces are possible. */
  function allergenLine(item) {
    if (item.kind === "drink") return "";
    var base = !item.allergens || !item.allergens.length ? tr("No major allergens in the recipe.") :
      tr("Contains {list}.", { list: item.allergens.map(function (a) { return tr(ALLERGEN_NAMES[a] || a); }).join(", ") });
    return base + " " + tr(item.fried
      ? "Everything is cooked in one kitchen and fried in shared oil, so traces of gluten, egg, milk, soy, sesame, peanuts or shellfish are possible."
      : "Everything is cooked in one kitchen, so traces of gluten, egg, milk, soy, sesame, peanuts or shellfish are possible.");
  }
  function fromPrice(m) {
    var mains = m.items.filter(function (i) { return i.kind !== "drink" && i.kind !== "side" && i.style !== "bundle"; });
    return mains.length ? Math.min.apply(null, mains.map(function (i) { return i.price; })) : 0;
  }
  function inkFor(hex) {
    var h = String(hex || "").replace("#", "");
    if (h.length !== 6) return "#FFFFFF";
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 ? "#0B1D3A" : "#FFFFFF";
  }
  function setAccent(hex) {
    if (!hex) return;
    BODY.style.setProperty("--accent", hex);
    BODY.style.setProperty("--accent-ink", inkFor(hex));
  }
  function itemFrom(node) {
    var host = node.closest("[data-b][data-id]");
    return host ? { b: host.getAttribute("data-b"), id: host.getAttribute("data-id") } : null;
  }
  function plusBtn(item, orderable) {
    return orderable ? '<button type="button" class="plus" data-quick aria-label="' + esc(tr("Add {name}", { name: item.name })) + '">' + ICON.plus + "</button>" : "";
  }
  function qtyBadge(n) { return '<span class="qtybadge"' + (n ? "" : " hidden") + ">" + n + "</span>"; }

  /* a menu row: words on the left, picture with a + on the right */
  function rowHTML(b, item, opts) {
    opts = opts || {};
    var m = MENU[b], n = itemCount(b, item.id), orderable = brandStatus(b) === "open" && !item.soldOut;
    return '<article class="row' + (item.soldOut ? " is-out" : "") + '" data-b="' + esc(b) + '" data-id="' + esc(item.id) + '">' +
      '<button type="button" class="row__open" data-open aria-label="' + esc(item.name) + ", " + money(item.price) + '"></button>' +
      '<div class="row__text">' +
        (opts.brand ? '<p class="row__brand">' + esc(m.name) + "</p>" : "") +
        '<h3 class="row__name">' + esc(item.name) + "</h3>" +
        '<p class="row__price">' + money(item.price) + (item.soldOut ? ' <span class="row__out">' + esc(tr("Sold out today")) + "</span>" : "") + "</p>" +
        (item.desc && item.kind !== "drink" ? '<p class="row__desc">' + esc(item.desc) + "</p>" : "") +
        (item.flags && item.flags.length ? '<p class="row__flags">' + flagText(item) + "</p>" : "") +
      "</div>" +
      '<div class="row__media' + (item.kind === "drink" ? " is-drink" : "") + '">' + thumbImg(item, ' loading="lazy" decoding="async"') +
        qtyBadge(n) + plusBtn(item, orderable) + "</div></article>";
  }
  /* a big picture card for featured dishes */
  function featHTML(b, item, opts) {
    opts = opts || {};
    var m = MENU[b], n = itemCount(b, item.id), orderable = brandStatus(b) === "open" && !item.soldOut;
    var tag = item.soldOut ? tr("Sold out today") : opts.brand ? m.name : item.includes ? includesNames(m, item).join(", ") : "";
    return '<article class="feat' + (item.soldOut ? " is-out" : "") + '" data-b="' + esc(b) + '" data-id="' + esc(item.id) + '">' +
      '<button type="button" class="feat__open" data-open aria-label="' + esc(item.name) + ", " + money(item.price) + (item.soldOut ? ", " + esc(tr("Sold out today")) : "") + '"></button>' +
      '<div class="feat__media"><img src="' + esc(path(item.img)) + '" alt="" width="780" height="446" loading="' + (opts.eager ? "eager" : "lazy") + '"' + (opts.eager ? ' fetchpriority="high"' : "") + ' decoding="async">' + qtyBadge(n) + plusBtn(item, orderable) + "</div>" +
      '<h3 class="feat__name">' + esc(item.name) + "</h3>" +
      '<p class="feat__meta"><span>' + money(item.price) + "</span>" + (tag ? "<span>" + esc(tag) + "</span>" : "") + "</p></article>";
  }
  function repaintCards() {
    if (PAGE === "hub" && typeof paintAgain === "function" && MENU && Object.keys(MENU).length) paintAgain();
    $$("[data-b][data-id]").forEach(function (c) {
      var n = itemCount(c.getAttribute("data-b"), c.getAttribute("data-id"));
      var badge = $(".qtybadge", c);
      if (badge) { badge.textContent = n; badge.hidden = n === 0; }
    });
    paintDeliver();
  }
  function quickAdd(btn) {
    var it = itemFrom(btn);
    if (!it) return;
    var line = addItem(it.b, it.id, {}, 1);
    if (line) {
      toast(addedMsg(tr("{name} added", { name: line.n })));
      bump();
      btn.classList.remove("pop"); void btn.offsetWidth; btn.classList.add("pop");
    }
  }
  document.addEventListener("click", function (e) {
    var q = e.target.closest("[data-quick]");
    if (q) { e.preventDefault(); quickAdd(q); return; }
    var o = e.target.closest("[data-open]");
    if (o) { var it = itemFrom(o); if (it) openDish(it.b, it.id); return; }
    if (e.target.closest("[data-oa-deliver]")) { openDeliver(); }
  });

  /* ---------------------------------------------------------------- dish sheet (tap modifiers) */
  function openDish(b, id) {
    var menu = MENU[b], item = menu && menu.byId[id];
    if (!item) return;
    var orderable = brandStatus(b) === "open" && !item.soldOut;
    var o = normOpts(item, {}), qty = 1;
    var groups = (item.options || []).map(function (g) {
      var type = g.type === "one" ? "radio" : "checkbox";
      return '<fieldset class="opt"><legend>' + esc(g.label) + (g.type === "one" ? "" : " <span>" + esc(tr("optional")) + "</span>") + '</legend><div class="chips">' +
        g.choices.map(function (c) {
          var on = g.type === "one" ? o[g.id] === c.id : false;
          return '<label class="chip"><input type="' + type + '" name="g-' + esc(g.id) + '" value="' + esc(c.id) + '"' + (on ? " checked" : "") + ">" +
            "<span>" + esc(c.label) + (c.price ? " +" + shortMoney(c.price) : "") + "</span></label>";
        }).join("") + "</div></fieldset>";
    }).join("");
    var pairs = (item.kind === "side" || item.kind === "drink") ? [] :
      menu.items.filter(function (i) { return (i.kind === "side" || i.kind === "drink") && !i.soldOut; }).slice(0, 5);
    var pairHTML = pairs.length && orderable ? '<fieldset class="opt"><legend>' + esc(tr("Goes well with")) + " <span>" + esc(tr("optional")) + '</span></legend><div class="chips">' +
      pairs.map(function (i) {
        return '<label class="chip"><input type="checkbox" name="pair" value="' + esc(i.id) + '"><span>' + esc(i.name.replace(/ \(can\)$/, "")) + " +" + shortMoney(i.price) + "</span></label>";
      }).join("") + "</div></fieldset>" : "";
    var inc = item.includes ? '<ul class="dish__inc">' + includesNames(menu, item).map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>" : "";
    var node = el(
      '<div class="dish' + (item.kind === "drink" ? " dish--drink" : "") + '" style="--accent:' + esc(menu.color) + ";--accent-ink:" + inkFor(menu.color) + '">' +
        '<button type="button" class="x x--float" data-close aria-label="' + esc(tr("Close")) + '">' + ICON.close + "</button>" +
        '<button type="button" class="x x--float x--share" data-share aria-label="' + esc(tr("Share this dish")) + '">' + ICON.share + "</button>" +
        '<div class="dish__media"><img src="' + esc(path(item.img)) + '" alt="' + esc(item.name) + '" decoding="async"></div>' +
        '<div class="dish__body">' +
          (PAGE !== "brand" ? '<p class="dish__brand">' + esc(menu.name) + "</p>" : "") +
          '<h2 class="dish__name" tabindex="-1" data-autofocus>' + esc(item.name) + "</h2>" +
          '<p class="dish__price">' + money(item.price) + "</p>" +
          '<p class="dish__desc">' + esc(item.desc) + "</p>" + inc +
          (item.flags && item.flags.length ? '<p class="row__flags">' + flagText(item) + "</p>" : "") +
          (allergenLine(item) ? '<p class="dish__allergens">' + esc(allergenLine(item) + " " + tr("Allergies? Add a note at checkout.")) + "</p>" : "") +
          groups + pairHTML +
        "</div>" +
        '<div class="dish__foot">' +
          '<div class="qty qty--lg"><button type="button" class="qty__b" data-q="-1" aria-label="' + esc(tr("One less")) + '">' + ICON.minus + '</button><span class="qty__n" aria-live="polite">1</span><button type="button" class="qty__b" data-q="1" aria-label="' + esc(tr("One more")) + '">' + ICON.plus + "</button></div>" +
          '<button type="button" class="btn btn--accent dish__add"' + (orderable ? "" : " disabled") + "></button>" +
        "</div>" +
      "</div>");
    function pickedPairs() {
      return $$('input[name="pair"]', node).filter(function (i) { return i.checked; }).map(function (i) { return menu.byId[i.value]; }).filter(Boolean);
    }
    function readOpts() {
      var out = {};
      (item.options || []).forEach(function (g) {
        var inputs = $$('input[name="g-' + g.id + '"]', node);
        if (g.type === "one") { var c = inputs.filter(function (i) { return i.checked; })[0]; out[g.id] = c ? c.value : g["default"]; }
        else out[g.id] = inputs.filter(function (i) { return i.checked; }).map(function (i) { return i.value; });
      });
      return normOpts(item, out);
    }
    function paint() {
      o = readOpts();
      $(".qty__n", node).textContent = qty;
      var btn = $(".dish__add", node);
      if (!orderable) btn.textContent = tr(item.soldOut ? "Sold out today" : "Opening soon");
      else {
        var extra = pickedPairs(), n = qty + extra.length;
        btn.innerHTML = "<span>" + esc(n > 1 ? tr("Add {n} items", { n: n }) : tr("Add")) + "</span><span>" + money(unitPrice(item, o) * qty + extra.reduce(function (t, i) { return t + i.price; }, 0)) + "</span>";
      }
    }
    node.addEventListener("change", paint);
    node.addEventListener("click", function (e) {
      var q = e.target.closest("[data-q]");
      if (q) { qty = Math.max(1, Math.min(MAX_QTY, qty + (+q.getAttribute("data-q")))); paint(); }
      if (e.target.closest("[data-share]")) shareDish(b, item);
    });
    var rec = openSheet(node, { label: item.name, cls: "sheet__panel--dish" });
    $(".dish__add", node).addEventListener("click", function () {
      if (!orderable) return;
      var extra = pickedPairs();
      addItem(b, id, readOpts(), qty);
      extra.forEach(function (i) { addItem(b, i.id, {}, 1); });
      closeSheet(rec);
      toast(addedMsg(tr("{name} added", { name: qty + " × " + item.name + (extra.length ? " + " + plural(extra.length, "extra", "extras") : "") })));
      bump();
    });
    paint();
  }

  /* ---------------------------------------------------------------- delivery or pickup, chosen up front */
  function deliverLabel() {
    var s = S();
    if (s.mode === "pickup") return tr("Pickup");
    return s.area === OTHER ? tr(OTHER) : s.area || tr("Delivery");
  }
  function paintDeliver() { $$("[data-oa-deliver] .deliver__t").forEach(function (t) { t.textContent = deliverLabel(); }); }
  function openDeliver() {
    var s = S(), areas = (SITE.areas || []).concat([OTHER]);
    var node = el('<div class="dl">' +
      '<div class="sheet__head"><h2>' + esc(tr("Delivery or pickup")) + '</h2><button type="button" class="x" data-close aria-label="' + esc(tr("Close")) + '">' + ICON.close + "</button></div>" +
      '<fieldset class="seg"><legend class="sr">' + esc(tr("Delivery or pickup")) + "</legend>" +
        '<label><input type="radio" name="dl-mode" value="delivery"' + (s.mode !== "pickup" ? " checked" : "") + "><span><b>" + esc(tr("Delivery")) + "</b><small>" + esc(tr("{fee} per order", { fee: shortMoney(SITE.deliveryFee) })) + "</small></span></label>" +
        '<label><input type="radio" name="dl-mode" value="pickup"' + (s.mode === "pickup" ? " checked" : "") + "><span><b>" + esc(tr("Pickup")) + "</b><small>" + esc(tr("Free")) + "</small></span></label>" +
      "</fieldset>" +
      '<fieldset class="dl__areas"' + (s.mode === "pickup" ? " hidden" : "") + "><legend>" + esc(tr("Area")) + '</legend><div class="chips">' +
        areas.map(function (a) { return '<label class="chip"><input type="radio" name="dl-area" value="' + esc(a) + '"' + (s.area === a ? " checked" : "") + "><span>" + esc(tr(a)) + "</span></label>"; }).join("") +
      '</div><p class="note note--warn dl__other"' + (s.area === OTHER && s.mode !== "pickup" ? "" : " hidden") + ">" + esc(tr(OTHER_NOTE)) + "</p></fieldset>" +
      '<button type="button" class="btn btn--accent dl__done" data-close>' + esc(tr("Done")) + "</button></div>");
    node.addEventListener("change", function (e) {
      var t = e.target;
      if (t.name === "dl-mode") { S().mode = t.value; $(".dl__areas", node).hidden = t.value === "pickup"; commit(); }
      if (t.name === "dl-area") { S().area = t.value; $(".dl__other", node).hidden = t.value !== OTHER; commit(); }
      paintDeliver();
    });
    openSheet(node, { label: tr("Delivery or pickup") });
  }

  /* ---------------------------------------------------------------- order (checkout) */
  function orderNode(mode) {
    var node = el('<div class="order' + (mode === "page" ? " order--page" : "") + '"></div>');
    node._mode = mode;
    renderOrder(node);
    node.addEventListener("click", function (e) {
      var q = e.target.closest("[data-line]");
      if (q) {
        var k = q.getAttribute("data-line"), l = S().lines.filter(function (x) { return x.k === k; })[0];
        if (l) setLineQty(k, l.q + (+q.getAttribute("data-d")));
        return;
      }
      var a = e.target.closest("[data-add]");
      if (a) {
        var p = a.getAttribute("data-add").split("|");
        var line = addItem(p[0], p[1], {}, 1);
        if (line) { toast(addedMsg(tr("{name} added", { name: line.n }))); bump(); }
        return;
      }
      if (e.target.closest("[data-copy]")) {
        if (!validate(node)) return;
        copyText(buildMessage()).then(function (ok) { toast(tr(ok ? "Copied. Paste it in WhatsApp." : "Copy didn’t work here.")); });
        return;
      }
      if (e.target.closest("[data-new]")) { clearOrder(); toast(tr("New order started")); if (node._mode === "sheet") closeSheet(); return; }
      if (e.target.closest("[data-edit]")) { S().sentAt = 0; commit(); return; }
    });
    node.addEventListener("input", function (e) {
      var f = e.target.getAttribute("data-f");
      if (!f) return;
      S()[f] = e.target.value;
      writeStore(S(), true);
      var field = e.target.closest(".field");
      if (field && field.classList.contains("is-bad") && e.target.value.trim()) field.classList.remove("is-bad");
      updateSend(node);
      var pre = $(".ticket pre", node); if (pre) pre.textContent = buildMessage();
      paintBar();
    });
    node.addEventListener("change", function (e) {
      var t = e.target;
      if (t.name === "oa-mode") { S().mode = t.value; commit(); }
      if (t.name === "oa-area") { S().area = t.value; var fa = t.closest(".field"); if (fa) fa.classList.remove("is-bad"); commit(); }
      if (t.name === "oa-pay") { S().pay = t.value; var fp = t.closest(".field"); if (fp) fp.classList.remove("is-bad"); commit(); }
    });
    return node;
  }
  /* cheap add-ons from the other restaurants: the whole point of one kitchen is one delivery */
  var CROSS = [["dushi-wok", "er"], ["nonnas-night-in", "gb"], ["taco-brava", "cs"], ["smash-shack", "fs"], ["oranje-snack", "bb"]];
  function suggItem(b, i, opts) {
    return '<button type="button" class="sugg__i' + (i.kind === "drink" ? " is-drink" : "") + '" data-add="' + esc(b + "|" + i.id) + '" aria-label="' + esc(tr("Add {name}", { name: i.name }) + ", " + money(i.price)) + '">' +
      '<span class="sugg__img">' + thumbImg(i, ' loading="lazy" decoding="async"') + "<i>" + ICON.plus + "</i></span>" +
      '<span class="sugg__n">' + esc(i.name.replace(/ \(can\)$/, "")) + '</span><span class="sugg__p">' + money(i.price) + "</span>" +
      (opts && opts.brand ? '<span class="sugg__b">' + esc(MENU[b].name) + "</span>" : "") + "</button>";
  }
  function suggestions() {
    var lines = liveLines(), brands = brandsInCart();
    if (!brands.length) return "";
    var host = brands.indexOf(HERE) >= 0 ? HERE : brands[0];
    var menu = MENU[host], out = "";
    var hasDrink = drinkLines().length > 0;
    var hasSide = lines.some(function (l) { var m = MENU[l.b], it = m && m.byId[l.id]; return l.b === host && it && it.kind === "side"; });
    if (menu && brandStatus(host) === "open") {
      var picks = [];
      if (!hasSide) picks = picks.concat(menu.items.filter(function (i) { return i.kind === "side" && !i.soldOut; }).slice(0, 2));
      if (!hasDrink) picks = picks.concat(menu.items.filter(function (i) { return i.kind === "drink" && !i.soldOut; }));
      if (picks.length) out += '<section class="sugg" aria-label="' + esc(tr("Add to your order")) + '"><h3>' + esc(tr(!hasDrink && !hasSide ? "Add a side or drink" : !hasDrink ? "Add a drink" : "Add a side")) + "</h3>" +
        '<div class="sugg__row">' + picks.map(function (i) { return suggItem(host, i); }).join("") + "</div></section>";
    }
    var other = CROSS.filter(function (c) {
      var m = MENU[c[0]], i = m && m.byId[c[1]];
      return i && !i.soldOut && brandStatus(c[0]) === "open" && brands.indexOf(c[0]) < 0;
    }).slice(0, 4);
    if (other.length) {
      out += '<section class="sugg sugg--x" aria-label="' + esc(tr("From our other restaurants")) + '"><h3>' + esc(tr("From our other restaurants")) +
        (S().mode === "delivery" ? " <span>" + esc(tr("Still one {fee} delivery", { fee: shortMoney(SITE.deliveryFee) })) + "</span>" : "") + "</h3>" +
        '<div class="sugg__row">' + other.map(function (c) { return suggItem(c[0], MENU[c[0]].byId[c[1]], { brand: true }); }).join("") + "</div></section>";
    }
    return out;
  }
  function crossMenus() { return CROSS.map(function (c) { return c[0]; }).filter(function (b) { return brandStatus(b) === "open"; }); }
  /* keep keyboard focus on the same control after the order re-renders */
  function focusKey(n) {
    if (!n) return null;
    if (n.id) return "#" + n.id;
    if (n.getAttribute("data-line")) return '[data-line="' + n.getAttribute("data-line") + '"][data-d="' + n.getAttribute("data-d") + '"]';
    if (n.name && n.type === "radio") return 'input[name="' + n.name + '"][value="' + n.value + '"]';
    if (n.getAttribute("data-add")) return '[data-add="' + n.getAttribute("data-add") + '"]';
    return null;
  }
  function restoreFocus(node, key, fallback) {
    var f = null;
    try { f = key && node.querySelector(key); } catch (e) { f = null; }
    f = f || (fallback && node.querySelector(fallback));
    if (f) f.focus({ preventScroll: true });
  }
  function renderOrder(node) {
    var s = S(), lines = liveLines(), brands = brandsInCart(), st = kitchenStatus();
    var had = document.activeElement && node.contains(document.activeElement) && document.activeElement !== node;
    var fKey = had ? focusKey(document.activeElement) : null;
    var html = "";
    var head = node._mode === "sheet"
      ? '<div class="sheet__head"><h2>' + esc(tr("Your order")) + '</h2><button type="button" class="x" data-close aria-label="' + esc(tr("Close")) + '">' + ICON.close + "</button></div>"
      : "";
    // the cart page has its own "Your order" title: hide it while the order is empty, so the two don't stack
    var pageTitle = node._mode === "page" ? $(".cart > h1") : null;
    if (pageTitle) pageTitle.hidden = !lines.length;
    if (!lines.length) {
      node.innerHTML = head + '<div class="empty"><p class="empty__t">' + esc(tr("Your order is empty")) + "</p><p>" + esc(tr("Tap + on any dish.")) + "</p>" +
        (PAGE === "brand" && node._mode === "sheet" ? '<button type="button" class="btn btn--accent" data-close>' + esc(tr("Back to the menu")) + "</button>" : '<a class="btn btn--accent" href="' + path("index.html") + '">' + esc(tr("Browse restaurants")) + "</a>") + "</div>";
      if (had) restoreFocus(node, null, ".x, .btn");
      return;
    }
    if (s.sentAt) {
      node.innerHTML = head + '<div class="sent"><div class="sent__icon">' + ICON.wa + "</div>" +
        '<p class="sent__k">' + esc(tr("Order #{no}", { no: s.no })) + "</p>" +
        "<h3>" + esc(tr("One more step: press Send in WhatsApp")) + "</h3>" +
        "<p>" + tr("Your order is typed out in the chat. Once you press <b>Send</b>, we reply on WhatsApp to confirm it.") + "</p>" +
        '<a class="btn btn--wa" data-send href="#" target="_blank" rel="noopener">' + ICON.wa + "<span>" + esc(tr("Open WhatsApp again")) + "</span></a>" +
        '<button type="button" class="btn btn--line" data-new>' + esc(tr("Start a new order")) + "</button>" +
        '<button type="button" class="link" data-edit>' + esc(tr("Edit this order")) + "</button></div>";
      wireSend(node);
      if (had) restoreFocus(node, null, "[data-send]");
      return;
    }
    html += head;
    if (!st.open) html += '<p class="note note--warn">' + esc(tr(st.finishing ? "Last orders have passed for tonight." : "We\u2019re closed.") + " " + st.label + ". " + tr("Order now for later and we confirm when we open.")) + "</p>";
    var drinks = drinkLines(), groups = [];
    brands.forEach(function (b) { var f = foodLines(b); if (f.length) groups.push({ t: brandName(b), lines: f }); });
    if (drinks.length) groups.push({ t: tr("Drinks"), lines: drinks });
    groups.forEach(function (g) {
      if (groups.length > 1) html += '<h3 class="lines__brand">' + esc(g.t) + "</h3>";
      html += '<ul class="lines">' + g.lines.map(function (l) {
        var extra = (l.inc && l.inc.length ? l.inc.join(", ") : "") + (l.inc && l.d && l.d.length ? " · " : "") + (l.d || []).join(" · ");
        var it = MENU[l.b] && MENU[l.b].byId[l.id];   // a small picture per line, so the order can be checked at a glance
        return '<li class="line">' + (it ? thumbImg(it, ' class="line__pic' + (it.kind === "drink" ? " line__pic--can" : "") + '" loading="lazy" decoding="async"') : "") +
          '<div class="line__main"><p class="line__n">' + esc(l.n) + "</p>" +
          (extra ? '<p class="line__d">' + esc(extra) + "</p>" : "") +
          (l.soldOut ? '<p class="line__d line__d--warn">' + esc(tr("Sold out today. Please remove.")) + "</p>" : "") +
          '<p class="line__t">' + money(l.p * l.q) + "</p></div>" +
          '<div class="qty"><button type="button" class="qty__b" data-line="' + esc(l.k) + '" data-d="-1" aria-label="' + esc(tr(l.q === 1 ? "Remove {name}" : "One less {name}", { name: l.n })) + '">' + ICON.minus + "</button>" +
          '<span class="qty__n">' + l.q + "</span>" +
          '<button type="button" class="qty__b" data-line="' + esc(l.k) + '" data-d="1" aria-label="' + esc(tr("One more {name}", { name: l.n })) + '">' + ICON.plus + "</button></div></li>";
      }).join("") + "</ul>";
    });
    html += suggestions();
    var areas = (SITE.areas || []).concat([OTHER]);
    html += '<form class="form" novalidate onsubmit="return false">' +
      '<fieldset class="seg"><legend class="sr">' + esc(tr("Delivery or pickup")) + "</legend>" +
        '<label><input type="radio" name="oa-mode" value="delivery"' + (s.mode === "delivery" ? " checked" : "") + "><span><b>" + esc(tr("Delivery")) + "</b><small>" + esc(tr("{fee} per order", { fee: shortMoney(SITE.deliveryFee) })) + "</small></span></label>" +
        '<label><input type="radio" name="oa-mode" value="pickup"' + (s.mode === "pickup" ? " checked" : "") + "><span><b>" + esc(tr("Pickup")) + "</b><small>" + esc(tr("Free")) + "</small></span></label>" +
      "</fieldset>";
    var ts = timeSlots(), when = validWhen();
    var whenOpts = (ts.asap ? ['<option value=""' + (when === "" ? " selected" : "") + ">" + esc(tr("As soon as possible ({eta})", { eta: SITE.eta || "" })) + "</option>"] : [])
      .concat(ts.slots.map(function (x) { return '<option value="' + esc(x.v) + '"' + (x.v === when ? " selected" : "") + ">" + esc(x.d) + "</option>"; }));
    html += '<label class="field"><span class="field__l">' + esc(tr(ts.asap ? "When" : "Tonight at")) + '</span><span class="select"><select id="oa-when" data-f="when">' + whenOpts.join("") + "</select></span></label>";
    if (s.mode === "delivery") {
      html += '<fieldset class="field field--areas" id="oa-f-area"><legend>' + esc(tr("Area")) + '</legend><div class="chips">' +
        areas.map(function (a) {
          return '<label class="chip"><input type="radio" name="oa-area" value="' + esc(a) + '"' + (s.area === a ? " checked" : "") + "><span>" + esc(tr(a)) + "</span></label>";
        }).join("") + '</div><p class="field__err">' + esc(tr("Pick your area.")) + "</p>" +
        (s.area === OTHER ? '<p class="note note--warn">' + esc(tr(OTHER_NOTE)) + "</p>" : "") + "</fieldset>" +
        '<label class="field" id="oa-f-addr"><span class="field__l">' + esc(tr("Address or landmark")) + "</span>" +
        '<textarea id="oa-addr" data-f="addr" rows="2" maxlength="160" autocomplete="street-address" aria-describedby="oa-addr-help">' + esc(s.addr) + "</textarea>" +
        '<span class="field__help" id="oa-addr-help">' + esc(tr("Street and house number, or a landmark. House colour helps the driver.")) + "</span>" +
        '<span class="field__err">' + esc(tr("Add an address for the driver.")) + "</span></label>";
    } else {
      html += '<p class="note">' + esc(tr("We send the pickup address and time on WhatsApp.")) + "</p>";
    }
    html += '<label class="field" id="oa-f-name"><span class="field__l">' + esc(tr("Name")) + "</span>" +
      '<input id="oa-name" data-f="name" type="text" maxlength="40" autocomplete="name" value="' + esc(s.name) + '">' +
      '<span class="field__err">' + esc(tr("Add your name.")) + "</span></label>" +
      '<label class="field"><span class="field__l">' + esc(tr("Note")) + " <em>" + esc(tr("optional")) + "</em></span>" +
      '<textarea id="oa-note" data-f="note" rows="2" maxlength="160" placeholder="' + esc(tr("Allergies, gate code")) + '">' + esc(s.note) + "</textarea></label>" +
      (payOptions().length ? '<fieldset class="field field--areas" id="oa-f-pay"><legend>' + esc(tr("How will you pay?")) + '</legend><div class="chips">' +
        payOptions().map(function (p) {
          return '<label class="chip"><input type="radio" name="oa-pay" value="' + esc(p) + '"' + (s.pay === p ? " checked" : "") + "><span>" + esc(tr(p)) + "</span></label>";
        }).join("") + "</div>" + (SITE.payment ? '<p class="field__help">' + esc(clean(tr(SITE.payment))) + "</p>" : "") +
        '<p class="field__err">' + esc(tr("Pick how you\u2019ll pay.")) + "</p></fieldset>" : "") +
      "</form>";
    html += '<dl class="sum"><div><dt>' + esc(tr("Food")) + "</dt><dd>" + money(subtotal()) + "</dd></div>" +
      "<div><dt>" + esc(tr(s.mode === "delivery" ? "Delivery" : "Pickup")) + "</dt><dd>" + (s.mode === "delivery" ? money(fee()) : esc(tr("Free"))) + "</dd></div>" +
      '<div class="sum__total"><dt>' + esc(tr("Total")) + "</dt><dd>" + money(total()) + "</dd></div></dl>";
    html += '<details class="ticket"><summary>' + esc(tr("Preview the message")) + "</summary><pre>" + esc(buildMessage()) + "</pre></details>";
    html += '<p class="order__hint">' + esc(payLine()) + tr("Opens WhatsApp with your order typed out. Press <b>Send</b> there.") +
      (SITE.whatsapp ? " " + esc(tr("It goes to our kitchen\u2019s WhatsApp, {number}.", { number: waNumber() })) : "") + "</p>" +
      '<button type="button" class="link" data-copy>' + esc(tr("Copy the order instead")) + "</button>" +
      '<div class="order__send"><a class="btn btn--wa" data-send href="#" target="_blank" rel="noopener">' + ICON.wa +
      '<span class="lg">' + esc(tr("Send on WhatsApp")) + '</span><span class="sm">' + esc(tr("Send order")) + '</span><span class="btn__total">' + money(total()) + "</span></a></div>";
    node.innerHTML = html;
    wireSend(node);
    if (had) restoreFocus(node, fKey, ".qty__b, .x, [data-send]");
  }
  function validate(node) {
    var s = S(), first = null;
    function mark(id, bad) {
      var f = document.getElementById(id);
      if (!f) return;
      f.classList.toggle("is-bad", bad);
      if (bad && !first) first = f;
    }
    if (s.mode === "delivery") {
      mark("oa-f-area", !s.area);
      mark("oa-f-addr", !clean(s.addr));
    }
    mark("oa-f-name", !clean(s.name));
    if (payOptions().length) mark("oa-f-pay", payOptions().indexOf(s.pay) < 0);
    if (first) {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
      var inp = $("input,textarea", first); if (inp && inp.type !== "radio") inp.focus({ preventScroll: true });
      toast(tr("Fill in the missing details"));
      return false;
    }
    return true;
  }
  function updateSend(node) {
    var a = $("[data-send]", node);
    if (a && liveLines().length) a.href = checkoutLink().url;
  }
  function wireSend(node) {
    var a = $("[data-send]", node);
    if (!a) return;
    updateSend(node);
    a.addEventListener("click", function (e) {
      if (!liveLines().length) { e.preventDefault(); return; }
      if (!S().sentAt && !validate(node)) { e.preventDefault(); return; }
      if (liveLines().some(function (l) { return l.soldOut; })) { e.preventDefault(); toast(tr("Remove the sold-out dish first")); return; }
      if (!S().sentAt) { S().no = newOrderNo(); writeStore(S(), true); }   // number = the minute it's sent
      var link = checkoutLink();
      a.href = link.url;
      if (link.short) copyText(link.full).then(function (ok) { toast(tr(ok ? "Long order: it’s copied. Paste it in the chat." : "Tap “Copy the order instead” and paste it in WhatsApp.")); });
      if (!S().sentAt) {
        try { localStorage.setItem(LAST_KEY, JSON.stringify({ at: Date.now(), lines: liveLines().map(function (l) { return { b: l.b, id: l.id, q: l.q, o: l.o }; }) })); } catch (err) { /* private mode */ }
      }
      setTimeout(function () { var s = S(); s.sentAt = Date.now(); commit(); }, 400);
    });
  }

  /* ---------------------------------------------------------------- sticky bar */
  function ensureBar() {
    var bar = $("#oa-bar");
    if (bar || PAGE === "cart") return bar;
    bar = el('<div class="bar" id="oa-bar" hidden><button type="button" class="bar__btn"><span class="bar__count"></span><span class="bar__label"></span><span class="bar__total"></span></button></div>');
    BODY.appendChild(bar);
    $("button", bar).addEventListener("click", openOrder);
    return bar;
  }
  function paintBar() {
    var n = count(), bar = ensureBar();
    $$("[data-oa-count]").forEach(function (c) { c.textContent = n; c.hidden = n === 0; });
    if (!bar) return;
    bar.hidden = !(n > 0 && !openSheets.length);
    BODY.classList.toggle("has-bar", n > 0);
    if (!n) return;
    var stale = Date.now() - (S().updated || 0) > 2 * 3600 * 1000;
    $(".bar__count", bar).textContent = n;
    $(".bar__label", bar).textContent = tr(S().sentAt ? "Sent: see order" : stale ? "Continue order" : "View order");
    // food only here; delivery is added at checkout, once the customer has picked delivery or pickup
    $(".bar__total", bar).textContent = money(subtotal());
    $("button", bar).setAttribute("aria-label", tr("View order: {items}, {total} before delivery", { items: plural(n, "item", "items"), total: money(subtotal()) }));
  }
  var orderSheet = null;
  function openOrder() {
    if (orderSheet) return;
    var node = orderNode("sheet");
    Promise.all(menusInCart().concat(crossMenus()).map(function (b) { return loadMenu(b).catch(function () {}); })).then(function () { renderOrder(node); });
    orderSheet = openSheet(node, { label: tr("Your order"), cls: "sheet__panel--order", onClose: function () { orderSheet = null; } });
    orderSheet.node = node;
  }

  /* ---------------------------------------------------------------- shared bits */
  /* "10 PM–2 AM" + "Every night" when every day is the same; otherwise today's hours */
  function hoursShort() {
    var vals = DAYS.map(function (d) { return SITE.hours[d] ? SITE.hours[d].join("-") : "x"; });
    var same = vals.every(function (v) { return v === vals[0]; }) && SITE.hours.mon;
    var h = same ? SITE.hours.mon : SITE.hours[DAYS[arubaNow().getDay()]];
    if (!h) return { t: tr("Closed"), d: tr("Today") };
    var night = mins(h[1]) <= mins(h[0]) || mins(h[0]) >= 18 * 60;
    return { t: clock(mins(h[0])) + "–" + clock(mins(h[1])), d: tr(same ? (night ? "Every night" : "Every day") : "Today") };
  }
  function setHTML(sel, html) { $$(sel).forEach(function (n) { if (n._html !== html) { n._html = html; n.innerHTML = html; } }); }
  function fillCommon() {
    var hs = hoursShort();
    $$("[data-oa-hours]").forEach(function (n) { n.textContent = hoursLabel(); });
    $$("[data-oa-hours-t]").forEach(function (n) { n.textContent = hs.t; });
    $$("[data-oa-hours-d]").forEach(function (n) { n.textContent = hs.d + (SITE.lastOrder ? " · " + tr("last orders {time}", { time: clock(mins(SITE.lastOrder)) }) : ""); });
    $$("[data-oa-pay]").forEach(function (n) { n.textContent = SITE.payment ? clean(tr(SITE.payment)) : ""; n.hidden = !SITE.payment; });
    $$("[data-oa-fee]").forEach(function (n) { n.textContent = shortMoney(SITE.deliveryFee); });
    $$("[data-oa-fee-t]").forEach(function (n) { n.textContent = tr(n.getAttribute("data-oa-fee-t"), { fee: shortMoney(SITE.deliveryFee) }); });
    setHTML("[data-oa-hero]", esc(tr("Mix dishes from all five restaurants.")) + " <b>" + esc(tr("You pay {fee} delivery once.", { fee: shortMoney(SITE.deliveryFee) })) + "</b>");
    setHTML("[data-oa-deliver-to]", deliverToHTML());
    setHTML("[data-oa-contact]", contactHTML());
    $$("[data-oa-eta]").forEach(function (n) { n.textContent = SITE.eta || ""; });
    $$("[data-oa-areas]").forEach(function (n) { n.textContent = listAnd(SITE.areas || []); });
    $$("[data-oa-ask]").forEach(function (a) { a.href = waLink("Hi! Do you deliver to my area? I’m in "); });
    setHTML("[data-oa-how]", howSteps());
    var ar = SITE.areas || [];
    setHTML("[data-oa-facts]", [SITE.eta ? tr("Delivery in {eta}", { eta: SITE.eta }) : "", ar.length > 1 ? tr("{from} to {to}", { from: ar[0], to: ar[ar.length - 1] }) : ar.join(""),
      ""].filter(Boolean).map(function (t) { return "<li>" + esc(t) + "</li>"; }).join(""));
    setHTML("[data-oa-how-note]", esc(howNote()));
    paintSign(false);
  }
  function deliverToHTML() {
    return esc(tr("We deliver to {areas}.", { areas: listAnd(SITE.areas || []) })) + " " + esc(tr("Elsewhere?")) +
      ' <a data-oa-ask href="' + esc(waLink("Hi! Do you deliver to my area? I’m in ")) + '" target="_blank" rel="noopener">' + esc(tr("Ask us")) + "</a>.";
  }
  /* the kitchen's real WhatsApp number, written out, so people can see who they're ordering from */
  function waNumber() {
    var w = String(SITE.whatsapp || "");
    return w.length === 10 && w.indexOf("297") === 0 ? "+297 " + w.slice(3, 6) + " " + w.slice(6) : "+" + w;
  }
  function contactHTML() {
    if (!SITE.whatsapp) return "";
    var parts = tr("Questions? WhatsApp us on {number}.", { number: "\u0000" }).split("\u0000");
    return esc(parts[0]) + '<a href="' + esc(waLink("Hi! ")) + '" target="_blank" rel="noopener">' + esc(waNumber()) + "</a>" + esc(parts[1] || "");
  }
  function howSteps() {
    var steps = [
      [tr("Pick your dishes"), tr("From any of the five restaurants, in one order.")],
      [tr("Send it on WhatsApp"), tr("WhatsApp opens with your order already written out. Just press send.")],
      [tr("We reply to confirm"), clean((SITE.eta ? tr("Delivery takes about {eta}.", { eta: SITE.eta }) : "") + " " + (SITE.payment ? tr(SITE.payment) : ""))]
    ];
    return steps.map(function (s) { return "<li><b>" + esc(s[0]) + ".</b> <span>" + esc(s[1]) + "</span></li>"; }).join("");
  }
  function howNote() {
    var vals = DAYS.map(function (d) { return SITE.hours[d] ? SITE.hours[d].join("-") : "x"; });
    var h = SITE.hours.mon, same = h && vals.every(function (v) { return v === vals[0]; }), today = SITE.hours[DAYS[arubaNow().getDay()]];
    var hours = same ? tr("Open every night from {open} to {close}.", { open: clock(mins(h[0])), close: clock(mins(h[1])) })
      : today ? tr("Open today {hours}.", { hours: clock(mins(today[0])) + "–" + clock(mins(today[1])) }) : tr("Closed today.");
    return [tr("{fee} delivery per order, however many restaurants you pick from.", { fee: shortMoney(SITE.deliveryFee) }),
      tr("Pickup is free."), tr("We send the pickup address and time on WhatsApp."), hours,
      SITE.lastOrder ? tr("Last orders at {time}.", { time: clock(mins(SITE.lastOrder)) }) : ""].join(" ").trim();
  }
  function setupIAB() {
    var ua = navigator.userAgent || "";
    var iab = /(Instagram|FBAN|FBAV|FB_IAB|musical_ly|BytedanceWebview|Snapchat|Line\/)/i.test(ua);
    if (!iab) return;
    var app = /Instagram/i.test(ua) ? "Instagram" : /FBAN|FBAV|FB_IAB/i.test(ua) ? "Facebook" : /musical_ly|Bytedance/i.test(ua) ? "TikTok" : /Snapchat/i.test(ua) ? "Snapchat" : "this app";
    var box = el('<div class="iab"><p>' + tr("In {app}? If WhatsApp doesn’t open, tap <b>•••</b> → <b>Open in browser</b>.", { app: esc(app === "this app" ? tr("this app") : app) }) + "</p>" +
      '<button type="button" class="link">' + esc(tr("Copy link")) + "</button></div>");
    var host = $("main") || BODY;
    host.insertBefore(box, host.firstChild);
    $("button", box).addEventListener("click", function () {
      copyText(shareUrl()).then(function (ok) { toast(tr(ok ? "Link copied with your order" : "Use ••• then Open in browser")); });
    });
  }
  /* a link that opens this dish on its restaurant's page (restaurant/#d=<id>), for sending to a friend */
  function shareDish(b, item) {
    var url = new URL(path(b + "/"), location.href).href + "#d=" + encodeURIComponent(item.id);
    var text = item.name + " \u00b7 " + MENU[b].name + " \u00b7 " + money(item.price);
    if (navigator.share) { navigator.share({ title: item.name, text: text, url: url }).catch(function () { /* closed the share screen */ }); return; }
    copyText(text + "\n" + url).then(function (ok) {
      if (ok) toast(tr("Link copied"));
      else window.open("https://wa.me/?text=" + encodeURIComponent(text + "\n" + url), "_blank", "noopener");
    });
  }
  /* restaurant/#d=<id>: open that dish once the page is drawn, then tidy the address so a refresh doesn't reopen it */
  function openFromHash() {
    var m = /[#&]d=([^&]+)/.exec(location.hash), id = m && decodeURIComponent(m[1]);
    if (!id || !MENU[HERE] || !MENU[HERE].byId[id]) return;
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* ignore */ }
    openDish(HERE, id);
  }
  function shareUrl() {
    var pack = liveLines().map(function (l) { return [l.b, l.id, l.q, l.o]; });
    var u = location.href.split("#")[0];
    if (!pack.length) return u;
    try { return u + "#c=" + btoa(unescape(encodeURIComponent(JSON.stringify(pack)))).replace(/=+$/, ""); } catch (e) { return u; }
  }
  function importHash() {
    var m = /[#&]c=([^&]+)/.exec(location.hash);
    if (!m) return Promise.resolve();
    var pack;
    try { pack = JSON.parse(decodeURIComponent(escape(atob(m[1])))); } catch (e) { pack = null; }
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* ignore */ }
    if (!Array.isArray(pack)) return Promise.resolve();
    var ids = []; pack.forEach(function (p) { if (ids.indexOf(p[0]) < 0) ids.push(p[0]); });
    return Promise.all(ids.map(function (b) { return loadMenu(b).catch(function () {}); })).then(function () {
      if (liveLines().length) return;
      pack.forEach(function (p) { addItem(p[0], p[1], p[3] || {}, p[2]); });
    });
  }
  function listAnd(arr) { return arr.length < 2 ? arr.join("") : arr.slice(0, -1).join(", ") + " " + tr("and") + " " + arr[arr.length - 1]; }
  function paintSign(first) {
    var sign = $("[data-oa-sign]");
    if (!sign) return;
    var st = kitchenStatus();
    var html = st.open ? "<b>" + esc(tr("Open")) + "</b><span>" + esc(st.sub) + "</span>" : "<b>" + esc(tr("Closed")) + "</b><span>" + esc(st.label) + "</span>";
    if (sign._html === html) return;   // only touch it when it changes, so screen readers don't repeat it every minute
    sign._html = html;
    sign.innerHTML = html;
    sign.classList.toggle("is-on", st.open);
    sign.classList.toggle("is-last", !!(st.open && st.soon && st.lastOrder));
    if (first && st.open) sign.classList.add("flick");
  }

  /* ---------------------------------------------------------------- restaurant page */
  function renderBrand() {
    var b = HERE, menu = MENU[b], status = brandStatus(b), st = kitchenStatus();
    document.title = menu.name + " · Order Aruba";
    setAccent(menu.color);
    var main = $("#oa-main");
    var feat = menu.items.filter(function (i) { return i.style === "signature" || i.style === "bundle"; });
    // one dish alone in a sideways rail leaves most of the first screen empty: then it just leads its section
    var rail = feat.length >= 2 ? feat : [];
    var railIds = rail.map(function (i) { return i.id; });
    var secs = menu.sections.map(function (s) {
      var items = menu.items.filter(function (i) { return i.section === s.id && railIds.indexOf(i.id) < 0; });
      return { id: s.id, title: s.title, items: items.filter(function (i) { return i.style === "signature"; }).concat(items.filter(function (i) { return i.style !== "signature"; })) };
    }).filter(function (s) { return s.items.length; });
    // without a rail, a section that only holds the house dish ("Signature") isn't a section: that dish leads the next one
    secs = secs.reduce(function (out, s, n) {
      var lead = out.carry || [];
      if (!rail.length && s.items.every(function (i) { return i.style; }) && n < secs.length - 1) { out.carry = lead.concat(s.items); return out; }
      out.list.push({ id: s.id, title: s.title, items: lead.concat(s.items) }); out.carry = null; return out;
    }, { list: [], carry: null }).list;
    // cover: not a featured dish and not one inside a bundle picture, so no dish shows twice on the first screen; real photo first
    var featIds = feat.map(function (i) { return i.id; }), inside = [];
    feat.forEach(function (i) { (i.includes || []).forEach(function (x) { inside.push(x); }); });
    var pool = menu.items.filter(function (i) { return i.kind !== "drink" && i.kind !== "side" && featIds.indexOf(i.id) < 0 && inside.indexOf(i.id) < 0; });
    var pick = (menu.cover && menu.byId[menu.cover]) || pool.filter(function (i) { return i.img.indexOf("/art/") < 0 && !i.soldOut; })[0] || pool[0] || feat[0] || menu.items[0];
    var cover = pick.img;
    var html = '<div class="cover">' + coverMedia(menu, cover) + "</div>" +
      '<header class="store">' +
        '<img class="store__mark" src="' + esc(path(menu.mark)) + '" alt="" width="76" height="76">' +
        '<h1 class="store__name" id="store-name">' + esc(menu.name) + "</h1>" +
        '<p class="store__tag">' + esc(menu.tagline) + "</p>" +
        '<ul class="facts">' +
          '<li class="facts__status' + (st.open ? " is-open" : "") + '"><i></i>' + esc(st.label) + "</li>" +
          "<li>" + esc(tr("{fee} delivery", { fee: shortMoney(SITE.deliveryFee) })) + "</li>" +
          "<li>" + esc(SITE.eta || "") + "</li>" +
        "</ul>" +
        (status === "soon" ? '<p class="note note--warn">' + esc(tr("Opening soon. Ordering starts shortly.")) + "</p>" : "") +
        (status === "hidden" ? '<p class="note note--warn">' + esc(tr("Not taking orders right now.")) + "</p>" : "") +
      "</header>";
    if (rail.length) {
      html += '<section class="sec" id="featured" aria-labelledby="h-featured"><h2 class="sec__t" id="h-featured">' + esc(tr("Start here")) + "</h2>" +
        '<div class="rail rail--feat">' + rail.map(function (i) { return featHTML(b, i); }).join("") + "</div></section>";
    }
    secs.forEach(function (s) {
      html += '<section class="sec" id="' + esc(s.id) + '" aria-labelledby="h-' + esc(s.id) + '"><h2 class="sec__t" id="h-' + esc(s.id) + '">' + esc(tr(s.title)) + "</h2>" +
        '<div class="' + (s.id === "drinks" ? "cans" : "rows") + '">' + s.items.map(function (i) { return rowHTML(b, i); }).join("") + "</div></section>";
    });
    html += '<section class="sec also" id="oa-also" aria-labelledby="h-also" hidden></section>';
    // people arriving from a shared dish link land here first, so the page explains ordering too
    html += '<section class="sec how" aria-labelledby="h-how"><h2 class="sec__t" id="h-how">' + esc(tr("How ordering works")) + "</h2>" +
      '<ol class="how__steps" data-oa-how>' + howSteps() + '</ol><p class="how__note" data-oa-how-note>' + esc(howNote()) + "</p>" +
      '<p class="areas" data-oa-deliver-to>' + deliverToHTML() + '</p><p class="areas" data-oa-contact>' + contactHTML() + "</p></section>";
    html += '<footer class="pfoot"><p>' + esc(tr(menu.imageNote) + " " + tr("Prices in Aruban florin (ƒ).")) + "</p>" +
      '<a class="pfoot__all" href="' + path("index.html") + '">' + esc(tr("All restaurants")) + "</a>" + langSwitch() + "</footer>";
    main.innerHTML = html;
    wireVideo(main);
    later(function () {
      var others = brandList(false).filter(function (x) { return x !== b; });
      Promise.all(others.map(function (x) { return loadMenu(x).catch(function () { return null; }); })).then(function () {
        var box = $("#oa-also");
        var cards = others.filter(function (x) { return MENU[x]; }).map(function (x) { return shopHTML(x, 9); }).join("");
        if (!box || !cards) return;
        box.innerHTML = '<h2 class="sec__t" id="h-also">' + esc(tr("Also tonight from our kitchen")) + "</h2>" +
          '<p class="also__sub">' + esc(tr("Mix dishes from any of them.") + " " + tr("Still one {fee} delivery.", { fee: shortMoney(SITE.deliveryFee) })) + "</p>" +
          '<div class="shops">' + cards + "</div>";
        box.hidden = false;
      });
    });

    var nav = $("#oa-cats");
    if (nav) {
      var tabs = (rail.length ? [{ id: "featured", title: "Start here" }] : []).concat(secs);
      nav.innerHTML = tabs.map(function (s, i) { return '<a href="#' + esc(s.id) + '" data-nav="' + esc(s.id) + '"' + (i === 0 ? ' class="on"' : "") + ">" + esc(tr(s.title)) + "</a>"; }).join("");
      if ("IntersectionObserver" in window) {
        var io = new IntersectionObserver(function (es) {
          es.forEach(function (en) {
            if (!en.isIntersecting) return;
            $$("a", nav).forEach(function (a) {
              var on = a.getAttribute("data-nav") === en.target.id;
              a.classList.toggle("on", on);
              var sc = nav.parentNode;
              if (on && sc.scrollWidth > sc.clientWidth) sc.scrollTo({ left: Math.max(0, a.offsetLeft - 16), behavior: "smooth" });
            });
          });
        }, { rootMargin: "-140px 0px -60% 0px" });
        $$(".sec", main).forEach(function (s) { io.observe(s); });
        var nameIO = new IntersectionObserver(function (es) { BODY.classList.toggle("past-name", !es[0].isIntersecting); }, { rootMargin: "-60px 0px 0px 0px" });
        nameIO.observe($("#store-name"));
      }
      window.addEventListener("scroll", function () {
        if (window.scrollY < 160) {
          $$("a", nav).forEach(function (a, i) { a.classList.toggle("on", i === 0); });
          if (nav.parentNode.scrollLeft) nav.parentNode.scrollTo({ left: 0 });
        }
      }, { passive: true });
    }
  }

  /* cover picture, or a short silent loop when the menu has one (never for reduce-motion or data saver) */
  function quietMode() {
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var save = navigator.connection && (navigator.connection.saveData || /2g/.test(navigator.connection.effectiveType || ""));
    return reduce || save;
  }
  function coverMedia(menu, img) {
    var pic = '<img src="' + esc(path(img)) + '" alt="" width="780" height="446" fetchpriority="high" decoding="async">';
    if (!menu.video || quietMode()) return pic;
    return '<video class="cover__v" muted loop playsinline autoplay preload="none" poster="' + esc(path(menu.video.poster || img)) + '" aria-hidden="true">' +
      '<source src="' + esc(path(menu.video.src)) + '" type="video/mp4"></video>' +
      '<button type="button" class="cover__pp" aria-label="' + esc(tr("Pause video")) + '" data-pp>' + ICON.pause + "</button>";
  }
  function wireVideo(root) {
    $$("video.cover__v", root).forEach(function (v) {
      var btn = v.parentNode.querySelector("[data-pp]");
      var p = v.play && v.play(); if (p && p.catch) p.catch(function () { /* autoplay blocked: poster stays */ });
      if (btn) btn.addEventListener("click", function () {
        if (v.paused) { v.play(); btn.innerHTML = ICON.pause; btn.setAttribute("aria-label", tr("Pause video")); }
        else { v.pause(); btn.innerHTML = ICON.play; btn.setAttribute("aria-label", tr("Play video")); }
      });
    });
  }
  /* offline cache + faster repeat visits (sw.js at the site root) */
  function registerSW() {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register(path("sw.js")).catch(function () { /* not supported here: the site works without it */ });
  }
  function later(fn) { if ("requestIdleCallback" in window) requestIdleCallback(fn, { timeout: 2500 }); else setTimeout(fn, 600); }

  /* ---------------------------------------------------------------- home page */
  /* the restaurant card's picture ("hero" in menu.json), only while a dish on the menu has that picture and
     isn't sold out, so the card never shows a dish you can't order under another dish's name. Otherwise not the
     signature dish (it's already in the dish rail above) and a photo before a drawing. */
  function heroImg(m) {
    var hero = m.hero && m.items.filter(function (i) { return i.img === m.hero; })[0];
    if (hero && !hero.soldOut) return hero.img;
    var pool = m.items.filter(function (i) { return !i.soldOut && i.kind !== "drink" && i.kind !== "side" && i.style !== "bundle"; });
    var others = pool.filter(function (i) { return i.style !== "signature"; });
    var alt = others.filter(function (i) { return i.img.indexOf("/art/") < 0; })[0] || others[0] || pool[0];
    return alt ? alt.img : m.items[0].img;
  }
  /* one row per restaurant, like the index of a printed menu: a small picture, the name, its own line, the price */
  function shopHTML(b, idx) {
    var m = MENU[b];
    if (!m) return "";
    var status = brandStatus(b), from = fromPrice(m);
    var img = heroImg(m), shown = m.items.filter(function (i) { return i.img === img; })[0] || m.items[0];
    return '<a class="shop' + (status !== "open" ? " is-soon" : "") + '" id="shop-' + esc(b) + '" href="' + path(b + "/index.html") + '" style="--shop:' + esc(m.color) + '">' +
      '<span class="shop__media"><img src="' + esc(path(thumb(img))) + '" data-full="' + esc(path(img)) + '" alt="' + esc(shown.name) + '" width="360" height="360" loading="' + (idx < 3 ? "eager" : "lazy") + '" decoding="async"></span>' +
      '<span class="shop__txt"><span class="shop__top"><h3 class="shop__name">' + esc(m.name) + '</h3><span class="shop__c">' + esc(tr(m.cuisine)) + "</span></span>" +
        '<span class="shop__dishes">' + esc(m.tagline || "") + "</span>" +
        '<span class="shop__meta">' + (status !== "open" ? '<span class="shop__soon">' + esc(tr("Opening soon")) + "</span>"
          : from ? esc(tr("From {price}", { price: money(from) })) : "") + "</span></span></a>";
  }
  /* words people type for the same food: English, Papiamento, Dutch, Spanish */
  var SYNONYMS = {
    chicken: "kip pollo galina", shrimp: "kamaron camaron garnalen prawn", fries: "papita papitas patat friet frietjes french papas fritas",
    rice: "aros arroz rijst", noodles: "noodle mie bami fideos", beef: "karni carne rund rundvlees", pork: "porko cerdo varken",
    burger: "hamburger hamburguesa", cheeseburger: "hamburger burger", penne: "pasta", spaghetti: "pasta", "lo mein": "pasta noodles",
    tacos: "taco", taco: "tacos", burrito: "wrap", quesadilla: "kesadilla", nachos: "chips", "coca-cola": "coke cola soda frisdrank refresco",
    sprite: "soda frisdrank refresco lemon limonada", kroket: "croquette croqueta", bitterballen: "bitterbal", "sate": "satay sateh",
    "saté": "sate satay sateh", wings: "wing alitas vleugels", "garlic bread": "pan bread", "egg rolls": "loempia springroll spring",
    "sweet & sour": "sweet sour zoetzuur agridulce", "fried rice": "nasi bami", "frikandel": "frikadel", vegetarian: "veggie vega vegetariano"
  };
  var SUGGEST = ["Chicken", "Fries", "Tacos", "Pasta", "Burgers", "Shrimp", "Bitterballen"];
  function setupSearch(ids) {
    var input = $("#oa-q"), out = $("#oa-results"), browse = $("#oa-browse");
    if (!input || !out || !browse) return;
    function norm(s) { return String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, ""); }
    function extra(text) {
      var t = norm(text), add = [];
      Object.keys(SYNONYMS).forEach(function (k) { if (t.indexOf(norm(k)) >= 0) add.push(SYNONYMS[k]); });
      return add.join(" ");
    }
    var all = [], seenDrink = {};
    ids.forEach(function (b) {
      var m = MENU[b];
      if (!m || brandStatus(b) !== "open") return;
      m.items.forEach(function (i) {
        if (i.kind === "drink") { if (seenDrink[i.id]) return; seenDrink[i.id] = 1; }
        all.push({ b: b, i: i,
          name: norm(i.name + " " + extra(i.name) + (i.kind === "drink" ? " drink soda can" : "")),
          rest: norm([m.name, m.cuisine].join(" ")),
          desc: norm([i.desc, (i.flags || []).join(" "), extra(i.desc)].join(" ")) });
      });
    });
    function score(x, words) {
      var sc = 0;
      for (var k = 0; k < words.length; k++) {
        var w = words[k], s1 = 0;
        if (new RegExp("(^|\\W)" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(x.name)) s1 = 6;
        else if (x.name.indexOf(w) >= 0) s1 = 4;
        else if (x.rest.indexOf(w) >= 0) s1 = 2;
        else if (x.desc.indexOf(w) >= 0) s1 = 1;
        if (!s1) return 0;
        sc += s1;
      }
      return sc + (x.i.style === "signature" ? 0.5 : 0) - (x.i.kind === "drink" ? 0.3 : 0);
    }
    var t;
    function chips() {
      return '<div class="chips chips--suggest">' + SUGGEST.map(function (w) { w = tr(w); return '<button type="button" class="chip chip--btn" data-q="' + esc(w) + '">' + esc(w) + "</button>"; }).join("") + "</div>";
    }
    function run() {
      var raw = input.value.trim(), q = norm(raw);
      if (!q) { out.hidden = true; browse.hidden = false; return; }
      var words = q.split(/\s+/).filter(Boolean);
      var hits = all.map(function (x) { return { x: x, s: score(x, words) }; }).filter(function (h) { return h.s > 0; })
        .sort(function (a, b) { return b.s - a.s; }).map(function (h) { return h.x; });
      browse.hidden = true; out.hidden = false;
      out.innerHTML = hits.length
        ? '<p class="results__n">' + esc(plural(hits.length, "dish", "dishes")) + "</p>" + '<div class="rows">' + hits.map(function (x) { return rowHTML(x.b, x.i, { brand: true }); }).join("") + "</div>"
        : '<p class="results__none">' + esc(tr("Nothing matches \u201c{q}\u201d. Try one of these:", { q: raw })) + "</p>" + chips();
    }
    out.addEventListener("click", function (e) {
      var c = e.target.closest("[data-q]");
      if (c) { input.value = c.getAttribute("data-q"); run(); input.focus({ preventScroll: true }); }
    });
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 90); });
    input.addEventListener("search", run);
  }
  function lastOrder() {
    try {
      var l = JSON.parse(localStorage.getItem(LAST_KEY));
      if (!l || !Array.isArray(l.lines) || Date.now() - l.at > 60 * 864e5) return null;
      var lines = l.lines.filter(function (x) { var m = MENU[x.b], i = m && m.byId[x.id]; return i && !i.soldOut && brandStatus(x.b) === "open"; });
      return lines.length ? lines : null;
    } catch (e) { return null; }
  }
  function paintAgain() {
    var box = $("#oa-again");
    if (!box) return;
    var lines = liveLines().length ? null : lastOrder();
    if (!lines) { box.hidden = true; return; }
    var sum = lines.reduce(function (t, x) { var i = MENU[x.b].byId[x.id]; return t + unitPrice(i, normOpts(i, x.o || {})) * x.q; }, 0);
    var names = lines.map(function (x) { return x.q + " \u00d7 " + MENU[x.b].byId[x.id].name; });
    var pic = MENU[lines[0].b].byId[lines[0].id];
    box.innerHTML = '<div class="again__card">' + thumbImg(pic, ' loading="lazy"') +
      '<div class="again__body"><h2 class="again__t">' + esc(tr("Order again")) + '</h2><p class="again__items">' + esc(names.join(", ")) + "</p>" +
      '<button type="button" class="btn btn--accent again__btn" data-again><span>' + esc(tr("Add all")) + "</span><span>" + money(sum) + "</span></button></div></div>";
    box.hidden = false;
    $("[data-again]", box).addEventListener("click", function () {
      lines.forEach(function (x) { addItem(x.b, x.id, x.o || {}, x.q); });
      toast(tr("Your last order is in the bag"));
      box.hidden = true;
    });
  }
  function quickRow(ids) {
    var row = $("#oa-quick");
    if (!row) return;
    row.innerHTML = ids.filter(function (b) { return MENU[b]; }).map(function (b) {
      var m = MENU[b];
      return '<a class="qk" href="' + path(b + "/index.html") + '" style="--shop:' + esc(m.color) + '">' +
        '<img src="' + esc(path(m.mark)) + '" alt="" width="64" height="64" decoding="async">' +
        '<span class="qk__c">' + esc(tr(m.cuisine)) + '</span><span class="qk__n">' + esc(m.name) + "</span></a>";
    }).join("");
  }
  function renderHub() {
    var ids = brandList(false);
    paintSign(true);
    paintDeliver();
    Promise.all(ids.map(function (b) { return loadMenu(b).catch(function () { return null; }); })).then(function () {
      var rail = $("#oa-rail"), list = $("#oa-list");
      quickRow(ids);
      if (rail) {
        // one signature dish per restaurant first, family deals after, so no restaurant fills the first screen
        var picks = [];
        ["signature", "bundle"].forEach(function (style) {
          ids.forEach(function (b) {
            var m = MENU[b];
            if (!m || brandStatus(b) !== "open") return;
            m.items.filter(function (i) { return i.style === style && !i.soldOut; }).forEach(function (i) { picks.push([b, i]); });
          });
        });
        rail.innerHTML = picks.map(function (p, n) { return featHTML(p[0], p[1], { brand: true, eager: n < 2 }); }).join("");
        railArrows(rail);
      }
      if (list) {
        list.innerHTML = ids.map(function (b, i) {
          return MENU[b] ? shopHTML(b, i) :
            '<div class="shop shop--fail"><p>' + esc(tr("One menu didn\u2019t load.")) + '</p><button type="button" class="btn btn--line btn--sm" data-retry>' + esc(tr("Try again")) + "</button></div>";
        }).join("");
        $$("[data-retry]", list).forEach(function (r) { r.addEventListener("click", function () { location.reload(); }); });
      }
      BODY.classList.add("oa-loaded");
      setupSearch(ids);
      paintAgain();
    });
  }
  /* desktop: arrow buttons for sideways rails (a mouse wheel can't scroll them) */
  function railArrows(rail) {
    if (!rail || rail._arrows) return;
    rail._arrows = true;
    var wrap = rail.parentNode;
    var nav = el('<div class="railnav" aria-hidden="true"><button type="button" tabindex="-1" data-dir="-1">' + ICON.back + '</button><button type="button" tabindex="-1" data-dir="1">' + ICON.back + "</button></div>");
    wrap.insertBefore(nav, rail);
    function upd() {
      var max = rail.scrollWidth - rail.clientWidth - 4;
      nav.hidden = max <= 0;
      $("[data-dir='-1']", nav).disabled = rail.scrollLeft <= 4;
      $("[data-dir='1']", nav).disabled = rail.scrollLeft >= max;
    }
    nav.addEventListener("click", function (e) {
      var b = e.target.closest("[data-dir]");
      if (b) rail.scrollBy({ left: +b.getAttribute("data-dir") * rail.clientWidth * 0.85, behavior: "smooth" });
    });
    rail.addEventListener("scroll", upd, { passive: true });
    window.addEventListener("resize", upd);
    upd();
  }

  /* ---------------------------------------------------------------- cart page */
  function renderCartPage() {
    var host = $("#oa-main");
    var node = orderNode("page");
    host.appendChild(node);
    Promise.all(menusInCart().concat(crossMenus()).map(function (b) { return loadMenu(b).catch(function () {}); })).then(function () { renderOrder(node); });
    onChange(function () { renderOrder(node); });
  }

  /* ---------------------------------------------------------------- boot */
  function boot() {
    // settings, this restaurant's menu and the menus already in the bag all load at the same time
    var first = PAGE === "brand" ? loadMenu(HERE) : Promise.resolve();
    menusInCart().forEach(function (b) { loadMenu(b).catch(function () {}); });
    Promise.all([loadSite(), first, loadLang()]).then(function () {
      state = readStore();
      translatePage();
      return importHash().then(function () {
        fillCommon();
        setInterval(fillCommon, 60000);
        if (PAGE === "brand") { renderBrand(); openFromHash(); window.addEventListener("hashchange", openFromHash); }
        if (PAGE === "hub") renderHub();
        if (PAGE === "cart") renderCartPage();
        $$("[data-oa-langs]").forEach(function (n) { n.innerHTML = langSwitch(); });
        $$("[data-oa-open-order]").forEach(function (b) { b.addEventListener("click", function (e) { e.preventDefault(); openOrder(); }); });
        setupIAB();
        paintBar();
        onChange(function () {
          paintBar(); repaintCards();
          if (orderSheet && orderSheet.node) renderOrder(orderSheet.node);
        });
        // menus for lines from other restaurants (keeps names and prices fresh)
        menusInCart().forEach(function (b) { loadMenu(b).catch(function () {}); });
        document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") { state = readStore(); emit(); } });
        BODY.classList.add("oa-ready");
        later(registerSW);
      });
    }).catch(function (err) {
      console.error(err);
      var main = $("#oa-main") || BODY;
      main.insertAdjacentHTML("afterbegin", '<p class="note note--warn">' + esc(tr("The menu didn\u2019t load. Check your connection and refresh.")) + "</p>");
    });
  }

  window.OrderAruba = {
    buildMessage: buildMessage, checkoutLink: checkoutLink, addItem: addItem, setLineQty: setLineQty,
    count: count, subtotal: subtotal, fee: fee, total: total, state: function () { return S(); },
    clear: clearOrder, loadMenu: loadMenu, kitchenStatus: function () { return kitchenStatus(); },
    _set: function (patch) { var s = S(); Object.keys(patch).forEach(function (k) { s[k] = patch[k]; }); commit(); }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
