/* Order Aruba: a late-night delivery app, like Uber Eats. The home page lists the restaurants; each
   restaurant page is its own shop. Restaurants marked "mix" in site.json share one order and one
   delivery fee (the app's perk, like DoorDash's Double Dash); any other restaurant has its own order.
   Menus live in <restaurant>/menu.json. Shop settings (WhatsApp number, hours, areas, delivery fee,
   which restaurants are open) live in shared/site.json. Prices are in cents: 1295 = ƒ12.95.
   No framework, no build step. */
(function () {
  "use strict";

  var BODY = document.body;
  var ROOT = BODY.getAttribute("data-root") || "";
  var PAGE = BODY.getAttribute("data-page") || "";
  var HERE = BODY.getAttribute("data-brand") || "";
  var KEY = "", LAST_KEY = "", ALLOWED = [];   // set by setOrder() once site.json is in
  var MIX_KEY = "orderaruba.cart.v2", MIX_LAST = "orderaruba.last.v1";
  var MAX_QTY = 20;
  var OTHER = "Other area";
  var OTHER_NOTE = "Outside our usual area. We\u2019ll confirm on WhatsApp if we can reach you, and the fee.";
  var WA_URL_LIMIT = 1900;
  var DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  var DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
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
  /* small square pictures for menu rows (build/thumbs.py makes them) */
  function thumb(img) { return String(img).replace(/([^/]+)$/, "thumbs/$1"); }   // same file name, in thumbs/
  /* Drinks are words only (no can drawings). A dish whose picture doesn't match its words ("hidePhoto": true in
     menu.json, e.g. a burger picture with one patty for a two-patty burger) shows no picture anywhere until a real
     photo replaces it: a text-only line beats a wrong picture. The chef app's new photo clears the flag. */
  function hasPic(item) { return !!(item && item.img && !item.hidePhoto && item.kind !== "drink"); }
  function thumbImg(item, attrs) {
    if (!hasPic(item)) return "";
    return '<img src="' + esc(path(thumb(item.img))) + '" data-full="' + esc(path(item.img)) + '" alt="" width="360" height="360"' + attrs + ">";
  }
  /* names and lines on screen wrap only between words: "stir-fry", "flat-top" and "35–50" never split at the dash,
     and a count like "(3)" stays on the line of the word before it */
  function keep(s) { return esc(s).replace(/ (\(\d+\))/g, "\u00a0$1").replace(/(\S+[-\u2013]\S+)/g, '<span class="nw">$1</span>'); }
  /* an add-on's price, the same everywhere: "+ ƒ3.00" */
  function addPrice(c) { return "+\u00a0" + money(c); }
  function shortName(i) { return i.name.replace(/ \(can\)$/, "").replace(/ \(side\)$/, ""); }
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
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M15 5l-7 7 7 7"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" d="M12 5v14M5 12h14"/></svg>',
    minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" d="M5 12h14"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" d="M6 6l12 12M18 6 6 18"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.5v13l11-6.5z"/></svg>',
    share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M12 3v12M7.5 7.5 12 3l4.5 4.5M8 11H6.5A1.5 1.5 0 0 0 5 12.5v7A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5v-7a1.5 1.5 0 0 0-1.5-1.5H16"/></svg>',
    wa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.83c0 4.54-3.7 8.23-8.24 8.23Zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.13-.15.17-.25.25-.42.08-.16.04-.31-.02-.43-.06-.13-.56-1.35-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.29Z"/></svg>'
  };

  /* ---------------------------------------------------------------- data */
  var SITE = null;
  var MENU = {};          // id -> loaded menu (sync access)
  var pending = {};       // id -> promise
  var failed = {};        // id -> true when its menu didn't load
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
        delete failed[id];
        if (KEY) refreshLines(id);   // before setOrder() there is no order to refresh yet: boot does it then
        return m;
      }, function (err) { failed[id] = true; delete pending[id]; throw err; });
    }
    return pending[id];
  }
  /* which order this page fills: the shared one for "mix" restaurants, else the restaurant's own */
  function mixGroup() { return (SITE.brands || []).filter(function (b) { return b.mix; }).map(function (b) { return b.id; }); }
  function inMix(b) { return mixGroup().indexOf(b) >= 0; }
  function setOrder() {
    if (inMix(HERE)) { KEY = MIX_KEY; LAST_KEY = MIX_LAST; ALLOWED = mixGroup(); }
    else { KEY = "order." + HERE + ".v1"; LAST_KEY = "last." + HERE + ".v1"; ALLOWED = [HERE]; }
  }
  /* a dish can't be ordered when it's sold out, and a family deal can't when one of the dishes inside it is */
  function isOut(menu, item) {
    if (!item || item.soldOut) return true;
    return (item.includes || []).some(function (id) { var x = menu && menu.byId[id]; return !!(x && x.soldOut); });
  }
  function brandStatus(id) {
    var b = (SITE.brands || []).filter(function (x) { return x.id === id; })[0];
    return b ? b.status || "open" : "hidden";
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
  /* Last orders: site.json "lastOrder" (e.g. "01:30"). New orders stop then; orders already in still go out. */
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
  function shopStatus() {
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
        return { open: true, soon: left <= 30, lastOrder: hasCut ? clock(x.cut) : "", last: last, close: clock(x.c),
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
  /* ---------------------------------------------------------------- cart store */
  var memState = null;
  var SENT_KEEP = 3 * 3600 * 1000;   // a sent order stays on screen for 3 hours, then the bag is empty again
  function blank() { return { v: 2, lines: [], mode: "delivery", area: "", addr: "", name: "", note: "", pay: "", no: "", sentAt: 0, updated: 0 }; }
  function readStore() {
    var s;
    try { s = JSON.parse(localStorage.getItem(KEY)); } catch (e) { return memState || blank(); }
    if (!(s && s.v === 2 && Array.isArray(s.lines))) s = memState || blank();
    if (KEY === MIX_KEY) absorb(s);
    s.mode = "delivery";   // delivery only (Victor, 9 Oct 2026)
    s.lines = s.lines.filter(function (l) { return ALLOWED.indexOf(l.b) >= 0; });
    return s;
  }
  /* For a few hours on 9 Oct 2026 every restaurant had its own order (order.<id>.v1). A mix restaurant's
     unsent lines from then join the shared order once, and the old key goes. */
  function absorb(s) {
    try {
      ALLOWED.forEach(function (b) {
        var k = "order." + b + ".v1", o = JSON.parse(localStorage.getItem(k));
        if (!o) return;
        localStorage.removeItem(k);
        if (!Array.isArray(o.lines) || o.sentAt || s.sentAt) return;
        o.lines.forEach(function (l) { if (!s.lines.some(function (x) { return x.k === l.k; })) s.lines.push(l); });
        ["area", "addr", "name"].forEach(function (f) { if (o[f] && !s[f]) s[f] = o[f]; });
      });
    } catch (e) { /* private mode */ }
  }
  var listeners = [];
  function onChange(fn) { listeners.push(fn); }
  function emit() { listeners.forEach(function (fn) { try { fn(); } catch (e) { console.error(e); } }); }
  function writeStore(s, silent) {
    s.updated = Date.now();
    memState = s;
    try { if (KEY) localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode: keep in memory */ }
    if (!silent) emit();
  }
  var state = null;
  function S() { if (!state) reload(); return state; }
  /* read the order again (page start, another tab, back from WhatsApp), with the same tidying as the first read */
  function reload() { state = readStore(); tidy(state); return state; }
  /* one line per can, whichever restaurant it was added from */
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
  window.addEventListener("storage", function (e) { if (KEY && e.key === KEY) { reload(); emit(); } });

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
    if (!item || isOut(menu, item) || brandStatus(b) !== "open" || ALLOWED.indexOf(b) < 0) return null;
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
      var out = isOut(menu, item);
      if (!!l.soldOut !== out) { l.soldOut = out; changed = true; }
    });
    if (changed) commit();
  }
  function liveLines() { return S().lines.filter(function (l) { return !l.gone && l.q > 0; }); }
  function count() { return liveLines().reduce(function (n, l) { return n + l.q; }, 0); }
  function itemCount(b, id) { return liveLines().reduce(function (n, l) { return n + (l.b === b && l.id === id ? l.q : 0); }, 0); }
  function subtotal() { return liveLines().reduce(function (n, l) { return n + l.q * l.p; }, 0); }
  function fee() { return count() > 0 ? SITE.deliveryFee : 0; }
  function total() { return subtotal() + fee(); }
  /* restaurants with food in the order (drinks don't count unless the order is only drinks), in site.json order */
  function brandsInCart() {
    var lines = liveLines(), food = lines.filter(function (l) { return !isDrinkLine(l); });
    var use = food.length ? food : lines.slice(0, 1), seen = [];
    (SITE.brands || []).forEach(function (b) { if (use.some(function (l) { return l.b === b.id; })) seen.push(b.id); });
    use.forEach(function (l) { if (seen.indexOf(l.b) < 0) seen.push(l.b); });
    return seen;
  }
  function foodLines(b) { return liveLines().filter(function (l) { return !isDrinkLine(l) && (!b || l.b === b); }); }
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
    var st = shopStatus(), win = null, prefix = "";
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
  /* closed, with time slots left tonight: what's ordered now is a pre-order for tonight */
  function preOrder() {
    if (shopStatus().open) return "";
    var ts = timeSlots();
    return ts.slots.length && !/^Tomorrow /.test(ts.slots[0].v) ? tr("Pre-order for tonight") : "";
  }
  function validWhen() {
    var s = S(), ts = timeSlots();
    if (s.when && ts.slots.some(function (x) { return x.v === s.when; })) return s.when;
    return ts.asap ? "" : (ts.slots[0] ? ts.slots[0].v : "");
  }

  /* ---------------------------------------------------------------- WhatsApp ticket */
  function buildMessage() {
    var s = S(), out = [], brands = brandsInCart();
    if (brands.length > 1) out.push("*Order* #" + orderNo() + " · " + brands.length + " restaurants");
    else out.push("*" + brandName(brands[0] || HERE) + " order* #" + orderNo());
    out.push("Delivery · " + (s.area ? s.area + (s.area === OTHER ? " (please confirm)" : "") : "area not set"));
    out.push("Time: " + (validWhen() || "As soon as possible"));
    if (!shopStatus().open) out.push("Pre-order: sent while you were closed");
    out.push("");
    function put(l) {
      out.push(l.q + " × " + l.n + " — " + money(l.q * l.p));
      if (l.inc && l.inc.length) out.push("   Includes: " + l.inc.join(", "));
      if (l.d && l.d.length) out.push("   " + l.d.join(" · "));
    }
    var drinks = drinkLines(), onlyDrinks = drinks.length === liveLines().length;
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
    out.push("Delivery " + money(fee()));
    out.push("*Total " + money(total()) + "*");
    if (payOptions().length) out.push("Pay: " + (payOptions().indexOf(s.pay) >= 0 ? s.pay : "-"));
    out.push("");
    out.push("Name: " + (clean(s.name) || "-"));
    out.push("Address: " + (clean(s.addr) || "-"));
    if (clean(s.note)) out.push("Note: " + clean(s.note));
    return out.join("\n");
  }
  /* how to pay: site.json "payment", e.g. "We take cash in florins or US dollars, or a bank transfer." Empty = say nothing. */
  /* site.json "payWith": the ways to pay the customer taps at checkout (it goes on the ticket as "Pay: Cash"),
     with the "payment" sentence under them. Without it, the sentence is shown above Send instead. */
  function payOptions() { return Array.isArray(SITE.payWith) ? SITE.payWith : []; }
  function payLine() { return SITE.payment && !payOptions().length ? clean(tr(SITE.payment)) + " " : ""; }
  /* this restaurant's WhatsApp: its own number when site.json gives it one ("whatsapp" on the brand), else the shared one */
  function waNum() {
    var b = (SITE.brands || []).filter(function (x) { return x.id === HERE; })[0];
    return String((b && b.whatsapp) || SITE.whatsapp || "");
  }
  function waLink(text) { return "https://wa.me/" + waNum() + "?text=" + encodeURIComponent(text); }
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
    paintBar();   // first: the order bar comes back, so focus can go back to it
    var back = rec.last && rec.last.focus && document.contains(rec.last) && rec.last.offsetParent !== null ? rec.last : $(".bag");
    if (back && back.offsetParent !== null) back.focus({ preventScroll: true });
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
  /* What the recipe contains, then the honest part: traces of the other big allergens are possible, and fried
     food shares the oil. */
  var TRACES = ["gluten", "egg", "dairy", "soy", "sesame", "peanut", "shellfish"];
  function allergenLine(item) {
    if (item.kind === "drink") return "";
    var has = item.allergens || [];
    var names = function (list) { return listAnd(list.map(function (a) { return tr(ALLERGEN_NAMES[a] || a); })); };
    var others = TRACES.filter(function (a) { return has.indexOf(a) < 0; });
    return [has.length ? tr("Contains {list}.", { list: names(has) }) : tr("No major allergens in the recipe."),
      others.length ? tr("May contain traces of {list}.", { list: names(others) }) : "",
      item.fried ? tr("Fried in shared oil.") : ""].filter(Boolean).join(" ");
  }
  function inkFor(hex) {
    var h = String(hex || "").replace("#", "");
    if (h.length !== 6) return "#FFFFFF";
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 ? "#15130F" : "#FFFFFF";
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
  /* the + box, like the tick box on a paper order pad: once the dish is in the order, the box shows how many */
  function plusBtn(item, n) {
    return '<button type="button" class="plus' + (n ? " has-n" : "") + '" data-quick aria-label="' + esc(tr("Add {name}", { name: item.name })) + '">' + ICON.plus +
      '<span class="plus__n" aria-hidden="true">' + (n || "") + "</span></button>";
  }

  /* A menu row, set like a printed menu: the name, then the price (on its own line on a phone; across a dotted line
     where the column is wide), the whole description under it. Beside it, one column of the same width on every row
     of the list: the small picture, and the + box right under it (rows without a picture keep the column, so every
     + sits in the same place and the words keep one measure). Each restaurant's stylesheet gives the row its own
     type, colours and rules. */
  function rowHTML(b, item) {
    var out = isOut(MENU[b], item), n = itemCount(b, item.id), orderable = brandStatus(b) === "open" && !out, pic = hasPic(item);
    var cls = "row" + (item.style === "signature" ? " is-sig" : item.style === "bundle" ? " is-bundle" : "") +
      (item.kind === "drink" ? " row--drink" : item.kind === "side" ? " row--side" : "") + (pic ? "" : " row--np") + (out ? " is-out" : "");
    var inc = item.includes ? includesNames(MENU[b], item).join(", ") : "";
    return '<article class="' + cls + '" data-b="' + esc(b) + '" data-id="' + esc(item.id) + '">' +
      '<button type="button" class="row__open" data-open aria-label="' + esc(item.name) + ", " + money(item.price) + (out ? ", " + esc(tr("Sold out today")) : "") + '"></button>' +
      '<div class="row__text">' +
        '<div class="row__head"><h3 class="row__name">' + keep(item.name) + '</h3><span class="row__lead" aria-hidden="true"></span><p class="row__price">' + money(item.price) + "</p></div>" +
        (out ? '<p class="row__out">' + esc(tr("Sold out today")) + "</p>" : "") +
        (item.desc && item.kind !== "drink" ? '<p class="row__desc">' + keep(item.desc) + "</p>" : "") +
        (inc ? '<p class="row__inc">' + keep(inc) + "</p>" : "") +
        (item.flags && item.flags.length ? '<p class="row__flags">' + flagText(item) + "</p>" : "") +
      "</div>" +
      '<div class="row__side">' + (pic ? '<div class="row__media">' + thumbImg(item, ' loading="lazy" decoding="async"') + "</div>" : "") +
        (orderable ? '<div class="row__act">' + plusBtn(item, n) + "</div>" : "") + "</div></article>";
  }
  function repaintCards() {
    if (MENU[HERE]) paintAgain();
    $$("[data-b][data-id]").forEach(function (c) {
      var n = itemCount(c.getAttribute("data-b"), c.getAttribute("data-id")), box = $(".plus", c);
      if (!box) return;
      box.classList.toggle("has-n", n > 0);
      $(".plus__n", box).textContent = n || "";
    });
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
    if (o) { var it = itemFrom(o); if (it) openDish(it.b, it.id); }
  });

  /* ---------------------------------------------------------------- dish sheet (tap modifiers) */
  function openDish(b, id) {
    var menu = MENU[b], item = menu && menu.byId[id];
    if (!item) return;
    var out = isOut(menu, item), orderable = brandStatus(b) === "open" && !out;
    var o = normOpts(item, {}), qty = 1;
    var groups = (item.options || []).map(function (g) {
      var type = g.type === "one" ? "radio" : "checkbox";
      return '<fieldset class="opt"><legend>' + esc(g.label) + (g.type === "one" ? "" : " <span>" + esc(tr("optional")) + "</span>") + '</legend><div class="chips">' +
        g.choices.map(function (c) {
          var on = g.type === "one" ? o[g.id] === c.id : false;
          return '<label class="chip"><input type="' + type + '" name="g-' + esc(g.id) + '" value="' + esc(c.id) + '"' + (on ? " checked" : "") + ">" +
            "<span><span>" + esc(c.label) + "</span>" + (c.price ? '<i class="chip__p">' + addPrice(c.price) + "</i>" : "") + "</span></label>";
        }).join("") + "</div></fieldset>";
    }).join("");
    var pairs = (item.kind === "side" || item.kind === "drink") ? [] :
      menu.items.filter(function (i) { return (i.kind === "side" || i.kind === "drink") && !isOut(menu, i); }).slice(0, 5);
    var pairHTML = pairs.length && orderable ? '<fieldset class="opt"><legend>' + esc(tr("Goes well with")) + " <span>" + esc(tr("optional")) + '</span></legend><div class="chips">' +
      pairs.map(function (i) {
        return '<label class="chip"><input type="checkbox" name="pair" value="' + esc(i.id) + '"><span><span>' + keep(shortName(i)) + '</span><i class="chip__p">' + addPrice(i.price) + "</i></span></label>";
      }).join("") + "</div></fieldset>" : "";
    var inc = item.includes ? '<ul class="dish__inc">' + includesNames(menu, item).map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>" : "";
    var pic = hasPic(item);
    var node = el(
      '<div class="dish' + (pic ? "" : " dish--np") + '" style="--accent:' + esc(menu.color) + ";--accent-ink:" + inkFor(menu.color) + '">' +
        '<button type="button" class="x x--float" data-close aria-label="' + esc(tr("Close")) + '">' + ICON.close + "</button>" +
        '<button type="button" class="x x--float x--share" data-share aria-label="' + esc(tr("Share this dish")) + '">' + ICON.share + "</button>" +
        (pic ? '<div class="dish__media"><img src="' + esc(path(item.img)) + '" alt="' + esc(item.name) + '" decoding="async"></div>' : "") +
        '<div class="dish__body">' +
          '<h2 class="dish__name" tabindex="-1" data-autofocus>' + keep(item.name) + "</h2>" +
          '<p class="dish__price">' + money(item.price) + "</p>" +
          '<p class="dish__desc">' + keep(item.desc) + "</p>" + inc +
          (item.flags && item.flags.length ? '<p class="row__flags">' + flagText(item) + "</p>" : "") +
          (allergenLine(item) ? '<p class="dish__allergens">' + keep(allergenLine(item) + " " + tr("Allergies? Add a note at checkout.")) + "</p>" : "") +
          groups + pairHTML +
        "</div>" +
        '<div class="dish__foot">' +
          (orderable && preOrder() ? '<p class="dish__pre">' + esc(preOrder()) + "</p>" : "") +
          (orderable ? '<div class="qty qty--lg"><button type="button" class="qty__b" data-q="-1" aria-label="' + esc(tr("One less")) + '">' + ICON.minus + '</button><span class="qty__n" aria-live="polite">1</span><button type="button" class="qty__b" data-q="1" aria-label="' + esc(tr("One more")) + '">' + ICON.plus + "</button></div>" : "") +
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
      var qn = $(".qty__n", node); if (qn) qn.textContent = qty;
      var btn = $(".dish__add", node);
      if (!orderable) btn.textContent = tr(out ? "Sold out today" : "Opening soon");
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
        if (line) { freshStart = false; bump(); }   // no toast here: the new line in the order says it
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
      var field = e.target.closest("[data-err]");
      if (field && field.classList.contains("is-bad") && e.target.value.trim()) setBad(field, false);
      updateSend(node);
      var pre = $(".ticket pre", node); if (pre) pre.textContent = buildMessage();
      paintBar();
    });
    node.addEventListener("change", function (e) {
      var t = e.target;
      if (t.name === "oa-area") { S().area = t.value; commit(); }   // the re-render clears its mark
      if (t.name === "oa-pay") { S().pay = t.value; commit(); }
    });
    return node;
  }
  /* cheap add-ons from the other "mix" restaurants: one order, still one delivery fee */
  var CROSS = [["dushi-wok", "er"], ["nonnas-night-in", "gb"], ["taco-brava", "cs"], ["smash-shack", "fs"], ["oranje-snack", "bb"]];
  function crossPicks() {
    var brands = brandsInCart();
    return CROSS.filter(function (c) {
      var m = MENU[c[0]], i = m && m.byId[c[1]];
      return i && !isOut(m, i) && c[0] !== HERE && ALLOWED.length > 1 && ALLOWED.indexOf(c[0]) >= 0 && brandStatus(c[0]) === "open" && brands.indexOf(c[0]) < 0;
    }).slice(0, 4);
  }
  function crossMenus() { return CROSS.map(function (c) { return c[0]; }).filter(function (b) { return b !== HERE && ALLOWED.indexOf(b) >= 0; }); }
  /* Right under the lines, one compact "anything else?" block, words only: this restaurant's own sides, one side from
     each other restaurant already in the order and the drinks, like the till; then a few cheap dishes from the "mix"
     restaurants not in it yet (the app's perk: same order, still one delivery fee). A dish from another restaurant
     carries that restaurant's name under it (and a small square in its colour). */
  function addChip(b, i, other) {
    var m = MENU[b];
    return '<button type="button" class="add' + (other ? " add--other" : "") + '" data-add="' + esc(b + "|" + i.id) + '"' + (other ? ' style="--shop:' + esc(m.color) + '"' : "") +
      ' aria-label="' + esc(tr("Add {name}", { name: i.name }) + ", " + money(i.price) + (other ? ", " + m.name : "")) + '">' +
      '<span class="add__n">' + keep(shortName(i)) + '</span><span class="add__p">' + addPrice(i.price) + "</span>" +
      (other ? '<span class="add__b" aria-hidden="true">' + esc(m.name) + "</span>" : "") + "</button>";
  }
  function addBlock() {
    var lines = liveLines(), brands = brandsInCart(), host = brands.indexOf(HERE) >= 0 ? HERE : brands[0];
    var menu = MENU[host], own = "", cross = crossPicks();
    function sideFrom(b) { return lines.some(function (l) { var m = MENU[l.b], it = m && m.byId[l.id]; return l.b === b && it && it.kind === "side"; }); }
    function sides(b) { var m = MENU[b]; return m ? m.items.filter(function (i) { return i.kind === "side" && !isOut(m, i); }) : []; }
    if (lines.length && menu && brandStatus(host) === "open") {
      var chips = [], nSide = 0, nDrink = 0;
      if (!sideFrom(host)) sides(host).slice(0, 2).forEach(function (i) { chips.push(addChip(host, i, false)); nSide++; });
      brands.forEach(function (b) {
        if (b === host || ALLOWED.indexOf(b) < 0 || brandStatus(b) !== "open" || sideFrom(b)) return;
        var i = sides(b)[0];
        if (i) { chips.push(addChip(b, i, true)); nSide++; }
      });
      if (!drinkLines().length) menu.items.filter(function (i) { return i.kind === "drink" && !isOut(menu, i); }).forEach(function (i) { chips.push(addChip(host, i, false)); nDrink++; });
      if (chips.length) own = '<h3 class="addon__t" id="oa-add-h">' + esc(tr(nSide && nDrink ? "Add a side or drink" : nDrink ? "Add a drink" : "Add a side")) + "</h3>" +
        '<div class="addon__row">' + chips.join("") + "</div>";
    }
    var other = cross.length ? '<h3 class="addon__t addon__t--other">' + keep(tr("From other restaurants · same order, still one {fee} delivery", { fee: shortMoney(SITE.deliveryFee) })) + "</h3>" +
      '<div class="addon__row addon__row--other">' + cross.map(function (c) { return addChip(c[0], MENU[c[0]].byId[c[1]], true); }).join("") + "</div>" : "";
    return own || other ? '<section class="addon" aria-label="' + esc(tr("Add a side or drink")) + '">' + own + other + "</section>" : "";
  }
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
    var s = S(), lines = liveLines(), st = shopStatus();
    var had = document.activeElement && node.contains(document.activeElement) && document.activeElement !== node;
    var fKey = had ? focusKey(document.activeElement) : null;
    var html = "";
    var head = node._mode === "sheet"
      ? '<div class="sheet__head"><h2>' + esc(tr("Your order")) + '</h2><button type="button" class="x" data-close aria-label="' + esc(tr("Close")) + '">' + ICON.close + "</button></div>"
      : "";
    if (!lines.length) {
      node.innerHTML = head + '<div class="empty"><p class="empty__t">' + esc(tr("Your order is empty")) + "</p><p>" + esc(tr("Tap + on any dish.")) + "</p>" +
        '<button type="button" class="btn btn--accent" data-close>' + esc(tr("Back to the menu")) + "</button></div>";
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
    var brands = brandsInCart(), groups = [];
    brands.forEach(function (b) { var f = foodLines(b); if (f.length) groups.push({ t: brandName(b), b: b, lines: f }); });
    if (drinkLines().length) groups.push({ t: tr("Drinks"), lines: drinkLines() });
    if (groups.length < 2) groups = [{ t: "", lines: foodLines().concat(drinkLines()) }];
    groups.forEach(function (g) {
      if (g.t) html += '<h3 class="lines__brand' + (g.b ? "" : " lines__brand--drinks") + '"' + (g.b && MENU[g.b] ? ' style="--shop:' + esc(MENU[g.b].color) + '"' : "") + ">" + esc(g.t) + "</h3>";
      html += '<ul class="lines">' + g.lines.map(function (l) {
        var extra = (l.inc && l.inc.length ? l.inc.join(", ") : "") + (l.inc && l.d && l.d.length ? " · " : "") + (l.d || []).join(" · ");
        var m = MENU[l.b], it = m && m.byId[l.id];   // a small picture per line, so the order can be checked at a glance
        // no picture (a drink, or a dish shown without one): the restaurant's mark, or an empty box for a can, so the words line up
        var pic = it && hasPic(it) ? thumbImg(it, ' class="line__pic" loading="lazy" decoding="async"')
          : m && !isDrinkLine(l) ? '<img class="line__pic line__pic--mark" src="' + esc(path(m.mark)) + '" alt="" width="192" height="192" loading="lazy" decoding="async">'
          : '<span class="line__pic line__pic--none" aria-hidden="true"></span>';
        return '<li class="line">' + pic +
          '<div class="line__main"><p class="line__n">' + keep(l.n) + "</p>" +
          (extra ? '<p class="line__d">' + esc(extra) + "</p>" : "") +
          (l.soldOut ? '<p class="line__d line__d--warn">' + esc(tr("Sold out today. Please remove.")) + "</p>" : "") +
          '<p class="line__t">' + money(l.p * l.q) + "</p></div>" +
          '<div class="qty"><button type="button" class="qty__b" data-line="' + esc(l.k) + '" data-d="-1" aria-label="' + esc(tr(l.q === 1 ? "Remove {name}" : "One less {name}", { name: l.n })) + '">' + ICON.minus + "</button>" +
          '<span class="qty__n">' + l.q + "</span>" +
          '<button type="button" class="qty__b" data-line="' + esc(l.k) + '" data-d="1" aria-label="' + esc(tr("One more {name}", { name: l.n })) + '">' + ICON.plus + "</button></div></li>";
      }).join("") + "</ul>";
    });
    html += addBlock();
    var areas = (SITE.areas || []).concat([OTHER]);
    html += '<form class="form" novalidate onsubmit="return false">';
    var ts = timeSlots(), when = validWhen();
    var whenOpts = (ts.asap ? ['<option value=""' + (when === "" ? " selected" : "") + ">" + esc(tr("As soon as possible ({eta})", { eta: SITE.eta || "" })) + "</option>"] : [])
      .concat(ts.slots.map(function (x) { return '<option value="' + esc(x.v) + '"' + (x.v === when ? " selected" : "") + ">" + esc(x.d) + "</option>"; }));
    html += '<label class="field"><span class="field__l">' + esc(tr(ts.asap ? "When" : "Tonight at")) + '</span><span class="select"><select id="oa-when" data-f="when">' + whenOpts.join("") + "</select></span></label>";
    // closed: say so right at the time choice, where it matters
    if (!st.open) html += '<p class="note note--warn">' + keep(tr(st.finishing ? "Last orders have passed for tonight." : "We\u2019re closed.") + " " + st.label + ". " + tr("Order now for later and we confirm when we open.")) + "</p>";
    // after a Send that found gaps, every field still missing says so (and keeps saying so through a re-render)
    var bad = node._tried ? missing() : {};
    function errAttrs(f, extra) {
      var ids = (extra ? [extra] : []).concat(bad[f] ? ["oa-" + f + "-err"] : []);
      return (bad[f] ? ' aria-invalid="true"' : "") + (ids.length ? ' aria-describedby="' + ids.join(" ") + '"' : "");
    }
    function err(f, text) { return '<p class="field__err" id="oa-' + f + '-err">' + esc(text) + "</p>"; }
    html += '<fieldset class="field field--areas' + (bad.area ? " is-bad" : "") + '" id="oa-f-area" data-err="area"><legend>' + esc(tr("Delivery area")) + '</legend><div class="chips">' +
        areas.map(function (a) {
          return '<label class="chip"><input type="radio" name="oa-area" value="' + esc(a) + '"' + (s.area === a ? " checked" : "") + errAttrs("area") + "><span>" + esc(tr(a)) + "</span></label>";
        }).join("") + "</div>" + err("area", tr("Pick your area.")) +
        (s.area === OTHER ? '<p class="note note--warn">' + esc(tr(OTHER_NOTE)) + "</p>" : "") + "</fieldset>" +
        '<div class="field' + (bad.addr ? " is-bad" : "") + '" id="oa-f-addr" data-err="addr"><label class="field__l" for="oa-addr">' + esc(tr("Address or landmark")) + "</label>" +
        '<textarea id="oa-addr" data-f="addr" rows="2" maxlength="160" autocomplete="street-address"' + errAttrs("addr", "oa-addr-help") + ">" + esc(s.addr) + "</textarea>" +
        '<p class="field__help" id="oa-addr-help">' + esc(tr("Street and house number, or a landmark. House colour helps the driver.")) + "</p>" +
        err("addr", tr("Add an address for the driver.")) + "</div>";
    html += '<div class="field' + (bad.name ? " is-bad" : "") + '" id="oa-f-name" data-err="name"><label class="field__l" for="oa-name">' + esc(tr("Name")) + "</label>" +
      '<input id="oa-name" data-f="name" type="text" maxlength="40" autocomplete="name" value="' + esc(s.name) + '"' + errAttrs("name") + ">" +
      err("name", tr("Add your name.")) + "</div>" +
      '<label class="field"><span class="field__l">' + esc(tr("Note")) + " <em>" + esc(tr("optional")) + "</em></span>" +
      '<textarea id="oa-note" data-f="note" rows="2" maxlength="160" placeholder="' + esc(tr("Allergies, gate code")) + '">' + esc(s.note) + "</textarea></label>" +
      (payOptions().length ? '<fieldset class="field field--areas' + (bad.pay ? " is-bad" : "") + '" id="oa-f-pay" data-err="pay"><legend>' + esc(tr("How will you pay?")) + '</legend><div class="chips">' +
        payOptions().map(function (p) {
          return '<label class="chip"><input type="radio" name="oa-pay" value="' + esc(p) + '"' + (s.pay === p ? " checked" : "") + errAttrs("pay") + "><span>" + esc(tr(p)) + "</span></label>";
        }).join("") + "</div>" + (SITE.payment ? '<p class="field__help">' + esc(clean(tr(SITE.payment))) + "</p>" : "") +
        err("pay", tr("Pick how you\u2019ll pay.")) + "</fieldset>" : "") +
      "</form>";
    html += '<dl class="sum"><div><dt>' + esc(tr("Food")) + "</dt><dd>" + money(subtotal()) + "</dd></div>" +
      "<div><dt>" + esc(tr("Delivery")) + "</dt><dd>" + money(fee()) + "</dd></div>" +
      '<div class="sum__total"><dt>' + esc(tr("Total")) + "</dt><dd>" + money(total()) + "</dd></div></dl>";
    html += '<details class="ticket"><summary><span>' + esc(tr("Preview the message")) + "</span></summary><pre>" + esc(buildMessage()) + "</pre></details>";
    html += '<p class="order__hint">' + esc(payLine()) + tr("Opens WhatsApp with your order typed out. Press <b>Send</b> there.") +
      (waNum() ? " " + esc(tr("It goes to {app} on WhatsApp, {number}.", { app: SITE.name || "us", number: waNumber() })) : "") + "</p>" +
      '<button type="button" class="link" data-copy>' + esc(tr("Copy the order instead")) + "</button>" +
      '<div class="order__send"><a class="btn btn--wa" data-send href="#" target="_blank" rel="noopener">' + ICON.wa +
      '<span class="lg">' + esc(tr("Send on WhatsApp")) + '</span><span class="sm">' + esc(tr("Send order")) + '</span><span class="btn__total">' + money(total()) + "</span></a></div>";
    node.innerHTML = html;
    wireSend(node);
    if (had) restoreFocus(node, fKey, ".qty__b, .x, [data-send]");
  }
  /* which checkout details are still missing */
  function missing() {
    var s = S(), out = {};
    if (!s.area) out.area = true;
    if (!clean(s.addr)) out.addr = true;
    if (!clean(s.name)) out.name = true;
    if (payOptions().length && payOptions().indexOf(s.pay) < 0) out.pay = true;
    return out;
  }
  /* mark one field as missing (or not): the red text shows, its control is marked invalid and points at that text */
  function setBad(field, bad) {
    if (!field) return;
    var f = field.getAttribute("data-err"), id = "oa-" + f + "-err";
    field.classList.toggle("is-bad", bad);
    $$("input,textarea", field).forEach(function (c) {
      var ids = (c.getAttribute("aria-describedby") || "").split(/\s+/).filter(function (x) { return x && x !== id; });
      if (bad) { ids.push(id); c.setAttribute("aria-invalid", "true"); } else c.removeAttribute("aria-invalid");
      if (ids.length) c.setAttribute("aria-describedby", ids.join(" ")); else c.removeAttribute("aria-describedby");
    });
  }
  function validate(node) {
    var bad = missing(), first = null;
    node._tried = true;
    ["area", "addr", "name", "pay"].forEach(function (f) {
      var field = $('[data-err="' + f + '"]', node);
      if (!field) return;
      setBad(field, !!bad[f]);
      if (bad[f] && !first) first = field;
    });
    if (first) {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
      // the first missing field gets the focus (in a group of choices: the picked one, else the first), so a screen
      // reader says which detail is missing and why
      var inp = $("input:checked", first) || $("input,textarea", first);
      if (inp) inp.focus({ preventScroll: true });
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
    if (bar) return bar;
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
    $(".bar__label", bar).textContent = S().sentAt ? tr("Sent: see order") : preOrder() || tr(stale ? "Continue order" : "View order");
    // food only here; the delivery fee is added at checkout
    $(".bar__total", bar).textContent = money(subtotal());
    $("button", bar).setAttribute("aria-label", tr("View order: {items}, {total} before delivery", { items: plural(n, "item", "items"), total: money(subtotal()) }));
  }
  var orderSheet = null;
  function openOrder() {
    if (orderSheet) return;
    var node = orderNode("sheet");
    Promise.all([HERE].concat(menusInCart(), crossMenus()).map(function (b) { return loadMenu(b).catch(function () {}); })).then(function () { renderOrder(node); });
    orderSheet = openSheet(node, { label: tr("Your order"), cls: "sheet__panel--order", onClose: function () { orderSheet = null; } });
    orderSheet.node = node;
  }

  /* ---------------------------------------------------------------- shared bits */
  function setHTML(sel, html) { $$(sel).forEach(function (n) { if (n._html !== html) { n._html = html; n.innerHTML = html; } }); }
  function fillCommon() {
    $$("[data-oa-fee]").forEach(function (n) { n.textContent = shortMoney(SITE.deliveryFee); });
    setHTML("[data-oa-hero]", mixGroup().length > 1
      ? keep(tr("Order from several restaurants at once.")) + " <b>" + keep(tr("You pay {fee} delivery once.", { fee: shortMoney(SITE.deliveryFee) })) + "</b>"
      : esc(tr("Late-night food, delivered.")) + " <b>" + esc(tr("{fee} delivery.", { fee: shortMoney(SITE.deliveryFee) })) + "</b>");
    var ar = SITE.areas || [];
    setHTML("[data-oa-facts]", [SITE.eta ? tr("Delivery in {eta}", { eta: SITE.eta }) : "", ar.length > 1 ? tr("{from} to {to}", { from: ar[0], to: ar[ar.length - 1] }) : ar.join("")]
      .filter(Boolean).map(function (t) { return "<li>" + esc(t) + "</li>"; }).join(""));
    paintSign(false);
    setHTML("[data-oa-deliver-to]", deliverToHTML());
    setHTML("[data-oa-contact]", contactHTML());
    setHTML("[data-oa-how]", howSteps());
    setHTML("[data-oa-how-note]", keep(howNote()));
    setHTML("[data-oa-endnote]", endNoteHTML());
    setHTML("[data-oa-foot]", footNote());
  }
  function deliverToHTML() {
    return keep(tr("We deliver to {areas}.", { areas: listAnd(SITE.areas || []) })) + " " + keep(tr("Elsewhere?")) +
      ' <span class="nw"><a data-oa-ask href="' + esc(waLink("Hi! Do you deliver to my area? I’m in ")) + '" target="_blank" rel="noopener">' + esc(tr("Ask us")) + "</a>.</span>";
  }
  /* the restaurant's real WhatsApp number, written out, so people can see who they're ordering from */
  function waNumber() {
    var w = waNum();
    // no-break spaces: the number never splits over two lines
    return w.length === 10 && w.indexOf("297") === 0 ? "+297\u00a0" + w.slice(3, 6) + "\u00a0" + w.slice(6) : "+" + w;
  }
  function contactHTML() {
    if (!waNum()) return "";
    var parts = tr("Questions? WhatsApp us on {number}.", { number: "\u0000" }).split("\u0000");
    var after = parts[1] || "", stop = /^[^\s]*/.exec(after)[0];   // the full stop stays with the number
    return esc(parts[0]) + '<span class="nw"><a href="' + esc(waLink("Hi! ")) + '" target="_blank" rel="noopener">' + esc(waNumber()) + "</a>" + esc(stop) + "</span>" + esc(after.slice(stop.length));
  }
  /* the end of a restaurant page: ordering, the fee, delivery only, hours and areas in one paragraph (the number under it) */
  function endNoteHTML() {
    return keep(tr("You order here and send it on WhatsApp. We reply to confirm.") + " " + howNote()) + " " + deliverToHTML();
  }
  /* "Pictures are illustrations. Prices in Aruban florin (ƒ)." in that order everywhere; "(ƒ)." never ends up alone */
  function footNote(note) {
    return esc(tr(note || "Pictures are illustrations.") + " " + tr("Prices in Aruban florin (ƒ).")).replace(/ \(ƒ\)/, "\u00a0(ƒ)");
  }
  function howSteps() {
    var steps = [
      mixGroup().length > 1 ? [tr("Pick your dishes"), tr("From one restaurant or several, in one order.")]
        : [tr("Pick a restaurant"), tr("Each restaurant is its own order. Tap + on what you want.")],
      [tr("Send it on WhatsApp"), tr("WhatsApp opens with your order already written out. Just press send.")],
      [tr("We reply to confirm"), clean((SITE.eta ? tr("Delivery takes about {eta}.", { eta: SITE.eta }) : "") + " " + (SITE.payment ? tr(SITE.payment) : ""))]
    ];
    return steps.map(function (s) { return "<li><b>" + keep(s[0]) + ".</b> <span>" + keep(s[1]) + "</span></li>"; }).join("");
  }
  function howNote() {
    var vals = DAYS.map(function (d) { return SITE.hours[d] ? SITE.hours[d].join("-") : "x"; });
    var h = SITE.hours.mon, same = h && vals.every(function (v) { return v === vals[0]; }), today = SITE.hours[DAYS[arubaNow().getDay()]];
    var hours = same ? tr("Open every night from {open} to {close}.", { open: clock(mins(h[0])), close: clock(mins(h[1])) })
      : today ? tr("Open today {hours}.", { hours: clock(mins(today[0])) + "–" + clock(mins(today[1])) }) : tr("Closed today.");
    var many = PAGE === "hub" ? mixGroup().length > 1 : ALLOWED.length > 1;
    return [tr(many ? "Delivery is {fee} per order, even with dishes from several restaurants." : "Delivery is {fee} per order.", { fee: shortMoney(SITE.deliveryFee) }),
      tr("We only deliver: there\u2019s no pickup or dine-in."), hours,
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
    if (location.hash === "#o") {
      try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* ignore */ }
      if (count()) openOrder();
      return;
    }
    var m = /[#&]d=([^&]+)/.exec(location.hash), id = null;
    try { id = m && decodeURIComponent(m[1]); } catch (e) { id = null; }   // a link cut off in a chat ("#d=%E0%A4%A"): ignore it
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
    var ids = []; pack.forEach(function (p) { if (ids.indexOf(p[0]) < 0 && ALLOWED.indexOf(p[0]) >= 0) ids.push(p[0]); });
    return Promise.all(ids.map(function (b) { return loadMenu(b).catch(function () {}); })).then(function () {
      if (liveLines().length) return;
      pack.forEach(function (p) { if (ALLOWED.indexOf(p[0]) >= 0) addItem(p[0], p[1], p[3] || {}, p[2]); });
    });
  }
  function listAnd(arr) { return arr.length < 2 ? arr.join("") : arr.slice(0, -1).join(", ") + " " + tr("and") + " " + arr[arr.length - 1]; }
  function paintSign(first) {
    // the greeting follows the Aruba clock: Papiamento for morning, afternoon and night
    var hello = $("[data-oa-hello]"), hr = arubaNow().getHours();
    if (hello) hello.textContent = hr >= 5 && hr < 12 ? "Bon dia." : hr >= 12 && hr < 18 ? "Bon tardi." : "Bon nochi.";
    var sign = $("[data-oa-sign]");
    if (!sign) return;
    var st = shopStatus();
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
    var b = HERE, menu = MENU[b], status = brandStatus(b), st = shopStatus();
    setAccent(menu.color);
    var main = $("#oa-main");
    var feat = menu.items.filter(function (i) { return i.style === "signature" || i.style === "bundle"; });
    // two house dishes (a family deal and the house dish) open the menu as "Start here"; one just leads its own section
    var lead = feat.length >= 2 ? feat : [];
    var leadIds = lead.map(function (i) { return i.id; });
    var secs = menu.sections.map(function (s) {
      var items = menu.items.filter(function (i) { return i.section === s.id && leadIds.indexOf(i.id) < 0; });
      return { id: s.id, title: s.title, kicker: s.kicker, klang: s.lang, items: items.filter(function (i) { return i.style === "signature"; }).concat(items.filter(function (i) { return i.style !== "signature"; })) };
    }).filter(function (s) { return s.items.length; });
    // without "Start here", a section that only holds the house dish ("Signature") isn't a section: that dish leads the next one
    secs = secs.reduce(function (out, s, n) {
      var carry = out.carry || [];
      if (!lead.length && s.items.every(function (i) { return i.style; }) && n < secs.length - 1) { out.carry = carry.concat(s.items); return out; }
      out.list.push({ id: s.id, title: s.title, kicker: s.kicker, klang: s.klang, items: carry.concat(s.items) }); out.carry = null; return out;
    }, { list: [], carry: null }).list;
    var cover = coverPick(menu, feat);
    // the app's delivery line, said as the app's ("Order Aruba delivers until 2 AM"), then the restaurant's own sign: its
    // wordmark, its line, a small framed picture. Closed: an unlit sign, like the home page's, when it opens in amber,
    // and no delivery time (so the line stays one line)
    var app = SITE.name || "", says = st.open && !st.last && app;   // "Order Aruba delivers until 2 AM · ƒ5 · 35–50 min"
    var html = '<div class="strip' + (st.open ? "" : " strip--closed") + '"><ul class="facts">' +
          '<li class="facts__status' + (st.open ? " is-open" : " is-closed") + '">' + (st.open ? "" : '<span class="unlit">' + esc(tr("Closed")) + "</span> ") +
            esc(says ? tr("{app} delivers until {time}", { app: app, time: st.close }) : st.label) + "</li>" +
          "<li>" + esc(says ? shortMoney(SITE.deliveryFee) : tr("{fee} delivery", { fee: shortMoney(SITE.deliveryFee) })) + "</li>" +
          (st.open && SITE.eta ? "<li>" + esc(SITE.eta) + "</li>" : "") +
        "</ul></div>" +
      '<header class="store' + (cover ? "" : " store--plain") + '">' +
        '<h1 class="store__name" id="store-name"><img class="store__logo" src="' + esc(path(menu.logo)) + '" alt="" decoding="async">' +
          '<span class="sr">' + esc(menu.name) + "</span></h1>" +
        '<p class="store__tag">' + keep(menu.tagline) + "</p>" +
        (cover ? '<div class="cover">' + coverMedia(menu, cover) + "</div>" : "") +
        (status === "soon" ? '<p class="note note--warn">' + esc(tr("Opening soon. Ordering starts shortly.")) + "</p>" : "") +
        (status === "hidden" ? '<p class="note note--warn">' + esc(tr("Not taking orders right now.")) + "</p>" : "") +
      "</header>" +
      '<section class="again" id="oa-again" hidden></section>';
    function section(id, label, items, kicker, klang) {
      return '<section class="sec sec--' + esc(id) + '" id="' + esc(id) + '" aria-labelledby="h-' + esc(id) + '"><h2 class="sec__t" id="h-' + esc(id) + '">' +
        (kicker ? '<span class="sec__k"' + (klang ? ' lang="' + esc(klang) + '"' : "") + ">" + esc(kicker) + "</span> " : "") + '<span class="sec__n">' + esc(label) + "</span></h2>" +
        '<div class="rows' + (id === "drinks" ? " rows--drinks" : "") + '">' + items.map(function (i) { return rowHTML(b, i); }).join("") + "</div></section>";
    }
    if (lead.length) html += section("featured", tr("Start here"), lead);
    secs.forEach(function (s) { html += section(s.id, tr(s.title), s.items, s.kicker, s.klang); });
    html += '<section class="sec also" id="oa-also" aria-labelledby="h-also" hidden></section>';
    // people arriving from a shared dish link land here too, so the page ends with how ordering works, in one paragraph
    // (the three steps are on the home page)
    html += '<section class="sec how how--brief" aria-labelledby="h-how"><h2 class="sec__t" id="h-how">' + esc(tr("How ordering works")) + "</h2>" +
      '<p class="areas" data-oa-endnote>' + endNoteHTML() + "</p>" +
      // the number on its own line, so its tap area never covers "Ask us" just above it
      '<p class="areas" data-oa-contact>' + contactHTML() + "</p></section>";
    html += '<footer class="pfoot"><p>' + footNote(menu.imageNote) + "</p>" +
      '<a class="pfoot__all" href="' + path("index.html") + '">' + esc(tr("All restaurants")) + "</a>" + langSwitch() + "</footer>";
    main.innerHTML = html;
    wireVideo(main);
    paintAgain();
    // like any delivery app: other restaurants on Order Aruba, at the very end, as small plates. Never in the order itself.
    later(function () {
      var others = (SITE.brands || []).filter(function (x) { return x.id !== b && x.status !== "hidden"; }).map(function (x) { return x.id; });
      Promise.all(others.map(function (x) { return loadMenu(x).catch(function () { return null; }); })).then(function () {
        var box = $("#oa-also");
        var cards = others.filter(function (x) { return MENU[x]; }).map(plateHTML).join("");
        if (!box || !cards) return;
        // (the one-order perk is said once on this page, in How ordering works, and again in the order itself)
        box.innerHTML = '<h2 class="sec__t" id="h-also">' + esc(tr("More on {app}", { app: SITE.name || "" })) + "</h2>" +
          '<div class="plates">' + cards + "</div>";
        box.hidden = false;
      });
    });

    var nav = $("#oa-cats");
    if (nav) {
      var tabs = (lead.length ? [{ id: "featured", title: "Start here" }] : []).concat(secs);
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
  /* The restaurant's small framed picture: not a featured dish and not one inside a bundle picture, so no dish shows
     twice on the first screen; a photo before a drawing. "cover": false in menu.json = no picture (the house dish leads). */
  function coverPick(menu, feat) {
    if (menu.cover === false) return "";
    if (menu.video && menu.video.poster) return menu.video.poster;
    var featIds = feat.map(function (i) { return i.id; }), inside = [];
    feat.forEach(function (i) { (i.includes || []).forEach(function (x) { inside.push(x); }); });
    var pool = menu.items.filter(function (i) { return i.kind !== "drink" && i.kind !== "side" && hasPic(i) && featIds.indexOf(i.id) < 0 && inside.indexOf(i.id) < 0; });
    var named = menu.cover && menu.byId[menu.cover];
    var pick = (hasPic(named) ? named : null) || pool.filter(function (i) { return i.img.indexOf("/art/") < 0 && !isOut(menu, i); })[0] || pool[0];
    return pick ? pick.img : "";
  }
  /* On a phone the cover is a small still. Where it's big (wide screens) it plays the menu's short silent loop,
     unless the phone asks for less motion or less data. */
  function coverMedia(menu, img) {
    var wide = window.matchMedia && matchMedia("(min-width: 760px)").matches;
    var pic = '<img src="' + esc(path(img)) + '" alt="" width="960" height="540" fetchpriority="high" decoding="async">';
    if (!menu.video || quietMode() || !wide) return pic;
    return '<video class="cover__v" muted loop playsinline autoplay preload="none" poster="' + esc(path(img)) + '" aria-hidden="true">' +
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

  /* ---------------------------------------------------------------- order again (this restaurant's last sent order) */
  function lastSent() {
    try {
      var l = JSON.parse(localStorage.getItem(LAST_KEY));
      return l && Array.isArray(l.lines) && Date.now() - l.at <= 60 * 864e5 ? l : null;
    } catch (e) { return null; }
  }
  /* the restaurants in the last sent order: their menus load first, so "Order again" shows all of it */
  function lastBrands() {
    var l = lastSent(), out = [];
    (l ? l.lines : []).forEach(function (x) { if (ALLOWED.indexOf(x.b) >= 0 && out.indexOf(x.b) < 0) out.push(x.b); });
    return out;
  }
  function lastOrder() {
    var l = lastSent();
    if (!l) return null;
    // a menu still on its way: wait for it (a menu that didn't load leaves its dishes out)
    if (lastBrands().some(function (b) { return !MENU[b] && !failed[b]; })) return null;
    var lines = l.lines.filter(function (x) { var m = MENU[x.b], i = m && m.byId[x.id]; return ALLOWED.indexOf(x.b) >= 0 && i && !isOut(m, i) && brandStatus(x.b) === "open"; });
    return lines.length ? lines : null;
  }
  function paintAgain() {
    var box = $("#oa-again");
    if (!box) return;
    var lines = liveLines().length ? null : lastOrder();
    if (!lines) { box.hidden = true; return; }
    var sum = lines.reduce(function (t, x) { var i = MENU[x.b].byId[x.id]; return t + unitPrice(i, normOpts(i, x.o || {})) * x.q; }, 0);
    var names = lines.map(function (x) { return x.q + "\u00a0\u00d7\u00a0" + MENU[x.b].byId[x.id].name; });   // "1 × Chicken" never splits
    var pic = lines.map(function (x) { return MENU[x.b].byId[x.id]; }).filter(hasPic)[0];
    var html = '<div class="again__card' + (pic ? "" : " again__card--np") + '">' + (pic ? thumbImg(pic, ' loading="lazy"') : "") +
      '<div class="again__body"><h2 class="again__t">' + esc(tr("Order again")) + '</h2><p class="again__items">' + keep(names.join(", ")) + "</p>" +
      '<button type="button" class="btn btn--accent again__btn" data-again><span>' + esc(tr("Add all")) + "</span><span>" + money(sum) + "</span></button></div></div>";
    if (box._html === html && !box.hidden) return;
    box._html = html; box.innerHTML = html;
    box.hidden = false;
    $("[data-again]", box).addEventListener("click", function () {
      lines.forEach(function (x) { addItem(x.b, x.id, x.o || {}, x.q); });
      toast(tr("Your last order is in the bag"));
      box.hidden = true;
    });
  }
  /* ---------------------------------------------------------------- home page (the app: every restaurant, each its own shop) */
  /* "From ƒ…": the cheapest dish in the restaurant's main section (menu.json "mainSection", else the house dish's
     section) or the house dish itself, so a burger place starts at its cheapest burger, not at a side of fries */
  function fromPrice(m) {
    var sig = m.items.filter(function (i) { return i.style === "signature"; })[0];
    var sec = m.mainSection || (sig && sig.section);
    var mains = m.items.filter(function (i) {
      return i.kind !== "drink" && i.kind !== "side" && i.style !== "bundle" && (!sec || i.section === sec || i.style === "signature");
    });
    return mains.length ? Math.min.apply(null, mains.map(function (i) { return i.price; })) : 0;
  }
  /* the restaurant's dish picture on the home page ("hero" in menu.json: the dish its line is about), only while a
     dish on the menu has that picture, it isn't sold out and the picture matches the dish. Otherwise a photo before a drawing.
     "hero": false = no dish picture at all (no true picture of the dish its line is about yet): just its sign. */
  function heroImg(m) {
    if (m.hero === false) return "";
    var hero = m.hero && m.items.filter(function (i) { return i.img === m.hero; })[0];
    if (hero && !isOut(m, hero) && hasPic(hero)) return hero.img;
    var pool = m.items.filter(function (i) { return !isOut(m, i) && hasPic(i) && i.kind !== "side" && i.style !== "bundle"; });
    var alt = pool.filter(function (i) { return i.img.indexOf("/art/") < 0; })[0] || pool[0];
    return alt ? alt.img : "";
  }
  function signStyle(m) {
    return "--shop:" + esc(m.color) + (m.sign ? ";--sign:" + esc(m.sign.ground || "") + ";--sign-line:" + esc(m.sign.line || "transparent") : "");
  }
  function fromLine(b, m) {
    var from = fromPrice(m);
    return brandStatus(b) !== "open" ? '<span class="soon">' + esc(tr("Opening soon")) + "</span>" : from ? "<span>" + esc(tr("From {price}", { price: money(from) })) + "</span>" : "";
  }
  /* the home page's list: each restaurant's own sign (its wordmark on its own ground, framed), one dish picture,
     then its cuisine, price and its own line in the app's type */
  function shopHTML(b, idx) {
    var m = MENU[b];
    if (!m) return "";
    var img = heroImg(m);
    // the cuisine label on every row, so the five rows read alike
    var label = "<b>" + esc(tr(m.cuisine)) + "</b>";
    return '<a class="shop' + (brandStatus(b) !== "open" ? " is-soon" : "") + (img ? "" : " shop--np") + '" id="shop-' + esc(b) + '" data-shop="' + esc(b) + '" href="' + path(b + "/index.html") + '" style="' + signStyle(m) + '">' +
      '<span class="shop__sign"><img class="shop__logo" src="' + esc(path(m.logo)) + '" alt="" loading="' + (idx < 3 ? "eager" : "lazy") + '" decoding="async"></span>' +
      (img ? '<span class="shop__pic"><img src="' + esc(path(thumb(img))) + '" data-full="' + esc(path(img)) + '" alt="" width="360" height="360" loading="' + (idx < 2 ? "eager" : "lazy") + '" decoding="async"></span>' : "") +
      '<span class="shop__txt"><h3 class="shop__name">' + esc(m.name) + "</h3>" +
        '<span class="meta">' + label + fromLine(b, m) + "</span>" +
        '<span class="shop__tag">' + keep(m.tagline || "") + "</span></span></a>";
  }
  /* "More on Order Aruba" at the end of a restaurant page: small plates, the sign and two facts */
  function plateHTML(b) {
    var m = MENU[b];
    return '<a class="plate' + (brandStatus(b) !== "open" ? " is-soon" : "") + '" href="' + path(b + "/index.html") + '" data-shop="' + esc(b) + '" style="' + signStyle(m) + '">' +
      '<span class="plate__sign"><img class="plate__logo" src="' + esc(path(m.logo)) + '" alt="' + esc(m.name) + '" loading="lazy" decoding="async"></span>' +
      '<span class="meta plate__txt"><b>' + esc(tr(m.cuisine)) + "</b>" + fromLine(b, m) + "</span></a>";
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
  /* the search box hint: the long one ("Search tacos, fried rice, bitterballen") when it fits the box in this
     language, else the short one, so it's never cut off on a small phone */
  function fitSearchHint() {
    var input = $("#oa-q");
    if (!input) return;
    var long = tr("Search tacos, fried rice, bitterballen"), short = tr("Search all menus");
    var cs = getComputedStyle(input), c = document.createElement("canvas").getContext("2d");
    c.font = cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
    var room = input.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 4;
    input.placeholder = c.measureText(long).width <= room ? long : short;
  }
  function setupSearch(ids) {
    var input = $("#oa-q"), out = $("#oa-results"), browse = $("#oa-browse");
    if (!input || !out || !browse) return;
    fitSearchHint();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitSearchHint);
    window.addEventListener("resize", fitSearchHint);
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
        ? '<p class="results__n">' + esc(plural(hits.length, "dish", "dishes")) + "</p>" + '<div class="rows">' + hits.map(function (x) { return linkRowHTML(x.b, x.i); }).join("") + "</div>"
        : '<p class="results__none">' + esc(tr("Nothing matches \u201c{q}\u201d. Try one of these:", { q: raw })) + "</p>" + chips();
    }
    out.addEventListener("click", function (e) {
      var c = e.target.closest("[data-q]");
      if (c) { input.value = c.getAttribute("data-q"); run(); input.focus({ preventScroll: true }); }
    });
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 90); });
    input.addEventListener("search", run);
  }
  function renderHub() {
    var ids = (SITE.brands || []).filter(function (b) { return b.status !== "hidden"; }).map(function (b) { return b.id; });
    paintSign(true);
    Promise.all(ids.map(function (b) { return loadMenu(b).catch(function () { return null; }); })).then(function () {
      var start = $("#oa-rail"), list = $("#oa-list");
      if (start) {
        // one house dish per restaurant first, family deals after: a short printed list, each opens on its own restaurant's page
        var picks = [];
        ["signature", "bundle"].forEach(function (style) {
          ids.forEach(function (b) {
            var m = MENU[b];
            if (!m || brandStatus(b) !== "open") return;
            m.items.filter(function (i) { return i.style === style && !isOut(m, i); }).forEach(function (i) { picks.push([b, i]); });
          });
        });
        start.innerHTML = picks.map(function (p) { return linkRowHTML(p[0], p[1], true); }).join("");
      }
      if (list) {
        list.innerHTML = ids.map(function (b, i) {
          return MENU[b] ? shopHTML(b, i) :
            '<div class="shop shop--fail"><p>' + esc(tr("One menu didn’t load.")) + '</p><button type="button" class="btn btn--line btn--sm" data-retry>' + esc(tr("Try again")) + "</button></div>";
        }).join("");
        $$("[data-retry]", list).forEach(function (r) { r.addEventListener("click", function () { location.reload(); }); });
      }
      BODY.classList.add("oa-loaded");
      setupSearch(ids);
      paintMine(ids);
    });
  }

  /* home page dish lines (search results, "Start with these") open the dish on its own restaurant's page */
  function dishLink(b, item) { return path(b + "/#d=" + encodeURIComponent(item.id)); }
  function linkRowHTML(b, item, short) {
    var m = MENU[b], pic = hasPic(item), out = isOut(m, item);
    return '<a class="row row--link' + (short ? " row--start" : "") + (pic ? "" : " row--np") + (out ? " is-out" : "") + '" href="' + esc(dishLink(b, item)) + '" data-shop="' + esc(b) + '" style="--shop:' + esc(m.color) + '">' +
      '<div class="row__text"><p class="row__brand">' + esc(m.name) + "</p>" +
        '<div class="row__head"><h3 class="row__name">' + keep(item.name) + '</h3><span class="row__lead" aria-hidden="true"></span><p class="row__price">' + money(item.price) + "</p></div>" +
        (out ? '<p class="row__out">' + esc(tr("Sold out today")) + "</p>" : "") +
        (!short && item.desc && item.kind !== "drink" ? '<p class="row__desc">' + keep(item.desc) + "</p>" : "") + "</div>" +
      '<div class="row__media' + (pic ? "" : " row__media--mark") + '">' + (pic ? thumbImg(item, ' loading="lazy" decoding="async"') :
        '<img src="' + esc(path(m.mark)) + '" alt="" width="192" height="192" loading="lazy" decoding="async">') + "</div></a>";
  }
  /* an order already started at a restaurant: a way back to it from the home page */
  function paintMine(ids) {
    var box = $("#oa-mine");
    if (!box) return;
    function row(key, keep) {
      var o = null;
      try { o = JSON.parse(localStorage.getItem(key)); } catch (e) { o = null; }
      if (!o || !Array.isArray(o.lines)) return "";
      // an unsent order from hours ago is forgotten here; a sent one stays for 3 hours, like on its restaurant's page
      if (o.sentAt ? Date.now() - o.sentAt > SENT_KEEP : Date.now() - (o.updated || 0) > SENT_KEEP) return "";
      var lines = o.lines.filter(function (l) { return !l.gone && l.q > 0 && keep.indexOf(l.b) >= 0 && MENU[l.b]; });
      if (!lines.length) return "";
      var bs = []; lines.forEach(function (l) { if (bs.indexOf(l.b) < 0 && !isDrinkLine(l)) bs.push(l.b); });
      if (!bs.length) bs = [lines[0].b];
      var n = lines.reduce(function (t, l) { return t + l.q; }, 0), sum = lines.reduce(function (t, l) { return t + l.q * l.p; }, 0);
      return '<a class="mine__row" href="' + esc(path(bs[0] + "/#o")) + '" style="--shop:' + esc(MENU[bs[0]].color) + '"><span class="mine__t">' +
        esc(tr("Your order: {names}", { names: listAnd(bs.map(function (b) { return MENU[b].name; })) })) + '</span><span class="mine__d">' +
        esc(o.sentAt ? tr("Sent: see order") : plural(n, "item", "items") + " \u00b7 " + money(sum)) + "</span></a>";
    }
    var mix = mixGroup();
    var rows = row(MIX_KEY, mix) + ids.filter(function (b) { return mix.indexOf(b) < 0; }).map(function (b) { return row("order." + b + ".v1", [b]); }).join("");
    box.innerHTML = rows;
    box.hidden = !rows;
  }

  /* ---------------------------------------------------------------- boot */
  function boot() {
    if (PAGE === "hub") {
      Promise.all([loadSite(), loadLang()]).then(function () {
        translatePage();
        fillCommon();
        setInterval(fillCommon, 60000);
        renderHub();
        $$("[data-oa-langs]").forEach(function (n) { n.innerHTML = langSwitch(); });
        setupIAB();
        BODY.classList.add("oa-ready");
        later(registerSW);
      }).catch(function (err) {
        console.error(err);
        ($("#oa-main") || BODY).insertAdjacentHTML("afterbegin", '<p class="note note--warn">' + esc(tr("The menu didn\u2019t load. Check your connection and refresh.")) + "</p>");
      });
      return;
    }
    if (PAGE !== "brand" || !HERE) return;
    // settings, this restaurant's menu and the words all load at the same time
    Promise.all([loadSite(), loadMenu(HERE), loadLang()]).then(function () {
      setOrder();
      reload();
      // this restaurant's menu came in before the order was known: now its lines get today's prices and sold-out marks
      Object.keys(MENU).forEach(function (b) { refreshLines(b); });
      menusInCart().forEach(function (b) { loadMenu(b).catch(function () {}); });   // and the other restaurants' lines, as their menus come in
      translatePage();
      return importHash().then(function () {
        fillCommon();
        setInterval(fillCommon, 60000);
        renderBrand(); openFromHash(); window.addEventListener("hashchange", openFromHash);
        // "Order again" waits for the menus of every restaurant in the last sent order, then shows all of it
        if (lastBrands().some(function (x) { return !MENU[x]; })) Promise.all(lastBrands().map(function (x) { return loadMenu(x).catch(function () {}); })).then(paintAgain);
        $$("[data-oa-open-order]").forEach(function (b) { b.addEventListener("click", function (e) { e.preventDefault(); openOrder(); }); });
        setupIAB();
        paintBar();
        onChange(function () {
          paintBar(); repaintCards();
          if (orderSheet && orderSheet.node) renderOrder(orderSheet.node);
        });
        document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") { reload(); emit(); } });
        BODY.classList.add("oa-ready");
        later(registerSW);
      });
    }).catch(function (err) {
      console.error(err);
      var main = $("#oa-main") || BODY;
      main.insertAdjacentHTML("afterbegin", '<p class="note note--warn">' + esc(tr("The menu didn\u2019t load. Check your connection and refresh.")) + "</p>");
    });
  }

  window.OrderApp = {
    buildMessage: buildMessage, checkoutLink: checkoutLink, addItem: addItem, setLineQty: setLineQty,
    count: count, subtotal: subtotal, fee: fee, total: total, state: function () { return S(); },
    clear: clearOrder, loadMenu: loadMenu, shopStatus: function () { return shopStatus(); },
    _set: function (patch) { var s = S(); Object.keys(patch).forEach(function (k) { s[k] = patch[k]; }); commit(); }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
