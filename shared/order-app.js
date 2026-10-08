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
  var OLD_KEY = "brandhub.crosscart.v1";
  var OLD_NAMES = { "Dushi Wok": "dushi-wok", "Taco Brava": "taco-brava", "Smash Shack": "smash-shack",
    "Nonna's Night In": "nonnas-night-in", "Nonna’s Night In": "nonnas-night-in", "Oranje Snack": "oranje-snack" };
  var MAX_QTY = 20;
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
  function el(html) { var t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }
  function clean(s) { return String(s || "").trim().replace(/\s+/g, " "); }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  var ICON = {
    bag: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M5 8h14l-1.2 11.1a2 2 0 0 1-2 1.9H8.2a2 2 0 0 1-2-1.9L5 8Zm4 0V6.5a3 3 0 0 1 6 0V8"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" d="M12 5v14M5 12h14"/></svg>',
    minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" d="M5 12h14"/></svg>',
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" d="M6 6l12 12M18 6 6 18"/></svg>',
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="M15 5l-7 7 7 7"/></svg>',
    flame: '<svg viewBox="0 0 34 50" aria-hidden="true"><path fill="currentColor" d="M17,0 C21.2,11 34,19 34,32 C34,44 26,50 17,50 C8,50 0,44 0,32 C0,23 8,18 11,9 C13,17 15,20 18,22 C20,14 19,6 17,0 Z"/></svg>',
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
  function kitchenStatus() {
    var t = arubaNow(), d = t.getDay(), now = t.getHours() * 60 + t.getMinutes();
    // still open from last night's late shift?
    var y = windowFor(d - 1);
    if (y && y.c > 24 * 60 && now < y.c - 24 * 60) {
      var left = y.c - 24 * 60 - now;
      return { open: true, soon: left <= 30, label: "Open until " + fmtTime(y.c) };
    }
    var w = windowFor(d);
    if (w && now >= w.o && now < w.c) return { open: true, soon: w.c - now <= 30, label: "Open until " + fmtTime(w.c) };
    if (w && now < w.o) return { open: false, label: "Opens " + (w.o >= 18 * 60 ? "tonight " : "today ") + fmtTime(w.o), opens: fmtTime(w.o) };
    for (var i = 1; i <= 7; i++) {
      var n = windowFor(d + i);
      if (n) {
        var when = (i === 1 ? (n.o >= 18 * 60 ? "tomorrow night " : "tomorrow ") : DAY_NAMES[(d + i) % 7] + " ") + fmtTime(n.o);
        return { open: false, label: "Opens " + when, opens: when };
      }
    }
    return { open: false, label: "Closed", opens: "" };
  }
  function hoursLabel() {
    var vals = DAYS.map(function (d) { return SITE.hours[d] ? SITE.hours[d].join("-") : "x"; });
    var first = SITE.hours.mon;
    if (vals.every(function (v) { return v === vals[0]; }) && first) {
      var night = mins(first[1]) <= mins(first[0]) || mins(first[0]) >= 18 * 60;
      return (night ? "Every night, " : "Every day, ") + fmtTime(mins(first[0])) + "\u2013" + fmtTime(mins(first[1]));
    }
    return DAYS.map(function (d, i) {
      var h = SITE.hours[d];
      return DAY_NAMES[i].slice(0, 3) + " " + (h ? fmtTime(mins(h[0])) + "\u2013" + fmtTime(mins(h[1])) : "closed");
    }).join(", ");
  }

  /* ---------------------------------------------------------------- cart store */
  var memState = null;
  function blank() { return { v: 2, lines: [], mode: "delivery", area: "", addr: "", name: "", note: "", no: "", sentAt: 0, updated: 0 }; }
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
  function S() { if (!state) state = readStore(); return state; }
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
  function addItem(b, id, opts, qty) {
    var menu = MENU[b], item = menu && menu.byId[id];
    if (!item || item.soldOut || brandStatus(b) !== "open") return null;
    var o = normOpts(item, opts || {});
    var k = lineKey(b, id, o);
    var s = S();
    if (s.sentAt) { s.sentAt = 0; }
    var line = s.lines.filter(function (l) { return l.k === k; })[0];
    if (line) line.q = Math.min(MAX_QTY, line.q + (qty || 1));
    else {
      line = { k: k, b: b, id: id, q: Math.min(MAX_QTY, qty || 1), o: o, d: describe(item, o), n: item.name, p: unitPrice(item, o) };
      if (item.includes) line.inc = includesNames(menu, item);
      s.lines.push(line);
    }
    commit();
    return line;
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
  function brandsInCart() {
    var seen = [];
    brandList(true).forEach(function (b) { if (liveLines().some(function (l) { return l.b === b; })) seen.push(b); });
    liveLines().forEach(function (l) { if (seen.indexOf(l.b) < 0) seen.push(l.b); });
    return seen;
  }
  function brandName(b) { return MENU[b] ? MENU[b].name : b.replace(/-/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); }); }
  function orderNo() {
    var s = S();
    if (!s.no) { s.no = String(1000 + Math.floor(Math.random() * 9000)); writeStore(s, true); }
    return s.no;
  }
  function clearOrder() {
    var s = S();
    s.lines = []; s.no = ""; s.sentAt = 0; s.note = "";
    commit();
  }

  /* ---------------------------------------------------------------- WhatsApp ticket */
  function buildMessage() {
    var s = S(), lines = liveLines(), brands = brandsInCart(), out = [];
    var no = "#" + orderNo();
    if (brands.length === 1) out.push("*" + brandName(brands[0]) + " order* " + no);
    else out.push("*Kitchen order* " + no + " · " + brands.length + " restaurants");
    out.push(s.mode === "delivery" ? "Delivery · " + (s.area || "area not set") : "Pickup");
    if (!kitchenStatus().open) out.push("Pre-order — sent while we were closed");
    out.push("");
    brands.forEach(function (b) {
      if (brands.length > 1) out.push("*" + brandName(b) + "*");
      lines.filter(function (l) { return l.b === b; }).forEach(function (l) {
        out.push(l.q + " × " + l.n + " — " + money(l.q * l.p));
        if (l.inc && l.inc.length) out.push("   Includes: " + l.inc.join(", "));
        if (l.d && l.d.length) out.push("   " + l.d.join(" · "));
      });
    });
    out.push("");
    out.push("Subtotal " + money(subtotal()));
    out.push(s.mode === "delivery" ? "Delivery " + money(fee()) : "Pickup " + money(0));
    out.push("*Total " + money(total()) + "*");
    out.push("");
    out.push("Name: " + (clean(s.name) || "-"));
    if (s.mode === "delivery") out.push("Address: " + (clean(s.addr) || "-"));
    if (clean(s.note)) out.push("Note: " + clean(s.note));
    return out.join("\n");
  }
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
    return (item.flags || []).map(function (f) { return '<span class="fl fl--' + esc(f) + '">' + esc(FLAG_NAMES[f] || f) + "</span>"; }).join("");
  }
  function allergenLine(item) {
    if (!item.allergens || !item.allergens.length) return item.kind === "drink" ? "" : "No major allergens.";
    return "Contains " + item.allergens.map(function (a) { return ALLERGEN_NAMES[a] || a; }).join(", ") + ".";
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
    return orderable ? '<button type="button" class="plus" data-quick aria-label="Add ' + esc(item.name) + '">' + ICON.plus + "</button>" : "";
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
        '<p class="row__price">' + money(item.price) + (item.soldOut ? ' <span class="row__out">Sold out today</span>' : "") + "</p>" +
        (item.desc && item.kind !== "drink" ? '<p class="row__desc">' + esc(item.desc) + "</p>" : "") +
        (item.flags && item.flags.length ? '<p class="row__flags">' + flagText(item) + "</p>" : "") +
      "</div>" +
      '<div class="row__media' + (item.kind === "drink" ? " is-drink" : "") + '"><img src="' + esc(path(item.img)) + '" alt="" width="780" height="446" loading="lazy" decoding="async">' +
        qtyBadge(n) + plusBtn(item, orderable) + "</div></article>";
  }
  /* a big picture card for featured dishes */
  function featHTML(b, item, opts) {
    opts = opts || {};
    var m = MENU[b], n = itemCount(b, item.id), orderable = brandStatus(b) === "open" && !item.soldOut;
    var tag = opts.brand ? m.name : item.style === "bundle" ? "Family deal" : item.style === "signature" ? "Signature" : "";
    return '<article class="feat" data-b="' + esc(b) + '" data-id="' + esc(item.id) + '">' +
      '<button type="button" class="feat__open" data-open aria-label="' + esc(item.name) + ", " + money(item.price) + '"></button>' +
      '<div class="feat__media"><img src="' + esc(path(item.img)) + '" alt="" width="780" height="446" loading="lazy" decoding="async">' + qtyBadge(n) + plusBtn(item, orderable) + "</div>" +
      '<h3 class="feat__name">' + esc(item.name) + "</h3>" +
      '<p class="feat__meta"><span>' + money(item.price) + "</span>" + (tag ? "<span>" + esc(tag) + "</span>" : "") + "</p></article>";
  }
  function repaintCards() {
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
      toast(line.n + " added");
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
      return '<fieldset class="opt"><legend>' + esc(g.label) + (g.type === "one" ? "" : " <span>optional</span>") + '</legend><div class="chips">' +
        g.choices.map(function (c) {
          var on = g.type === "one" ? o[g.id] === c.id : false;
          return '<label class="chip"><input type="' + type + '" name="g-' + esc(g.id) + '" value="' + esc(c.id) + '"' + (on ? " checked" : "") + ">" +
            "<span>" + esc(c.label) + (c.price ? " +" + shortMoney(c.price) : "") + "</span></label>";
        }).join("") + "</div></fieldset>";
    }).join("");
    var inc = item.includes ? '<ul class="dish__inc">' + includesNames(menu, item).map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>" : "";
    var node = el(
      '<div class="dish' + (item.kind === "drink" ? " dish--drink" : "") + '" style="--accent:' + esc(menu.color) + ";--accent-ink:" + inkFor(menu.color) + '">' +
        '<button type="button" class="x x--float" data-close aria-label="Close">' + ICON.close + "</button>" +
        '<div class="dish__media"><img src="' + esc(path(item.img)) + '" alt="' + esc(item.name) + '" decoding="async"></div>' +
        '<div class="dish__body">' +
          (PAGE !== "brand" ? '<p class="dish__brand">' + esc(menu.name) + "</p>" : "") +
          '<h2 class="dish__name">' + esc(item.name) + "</h2>" +
          '<p class="dish__price">' + money(item.price) + "</p>" +
          '<p class="dish__desc">' + esc(item.desc) + "</p>" + inc +
          (item.flags && item.flags.length ? '<p class="row__flags">' + flagText(item) + "</p>" : "") +
          (allergenLine(item) ? '<p class="dish__allergens">' + esc(allergenLine(item)) + " Allergies? Add a note at checkout.</p>" : "") +
          groups +
        "</div>" +
        '<div class="dish__foot">' +
          '<div class="qty qty--lg"><button type="button" class="qty__b" data-q="-1" aria-label="One less">' + ICON.minus + '</button><span class="qty__n" aria-live="polite">1</span><button type="button" class="qty__b" data-q="1" aria-label="One more">' + ICON.plus + "</button></div>" +
          '<button type="button" class="btn btn--accent dish__add" data-autofocus' + (orderable ? "" : " disabled") + "></button>" +
        "</div>" +
      "</div>");
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
      if (!orderable) btn.textContent = item.soldOut ? "Sold out today" : "Opening soon";
      else btn.innerHTML = "<span>Add " + qty + "</span><span>" + money(unitPrice(item, o) * qty) + "</span>";
    }
    node.addEventListener("change", paint);
    node.addEventListener("click", function (e) {
      var q = e.target.closest("[data-q]");
      if (q) { qty = Math.max(1, Math.min(MAX_QTY, qty + (+q.getAttribute("data-q")))); paint(); }
    });
    var rec = openSheet(node, { label: item.name, cls: "sheet__panel--dish" });
    $(".dish__add", node).addEventListener("click", function () {
      if (!orderable) return;
      addItem(b, id, readOpts(), qty);
      closeSheet(rec);
      toast(qty + " × " + item.name + " added");
    });
    paint();
  }

  /* ---------------------------------------------------------------- delivery or pickup, chosen up front */
  function deliverLabel() {
    var s = S();
    if (s.mode === "pickup") return "Pickup";
    return s.area || "Delivery";
  }
  function paintDeliver() { $$("[data-oa-deliver] .deliver__t").forEach(function (t) { t.textContent = deliverLabel(); }); }
  function openDeliver() {
    var s = S(), areas = (SITE.areas || []).concat(["Other area"]);
    var node = el('<div class="dl">' +
      '<div class="sheet__head"><h2>Delivery or pickup</h2><button type="button" class="x" data-close aria-label="Close">' + ICON.close + "</button></div>" +
      '<fieldset class="seg"><legend class="sr">Delivery or pickup</legend>' +
        '<label><input type="radio" name="dl-mode" value="delivery"' + (s.mode !== "pickup" ? " checked" : "") + '><span><b>Delivery</b><small>' + shortMoney(SITE.deliveryFee) + " per order</small></span></label>" +
        '<label><input type="radio" name="dl-mode" value="pickup"' + (s.mode === "pickup" ? " checked" : "") + "><span><b>Pickup</b><small>Free</small></span></label>" +
      "</fieldset>" +
      '<fieldset class="dl__areas"' + (s.mode === "pickup" ? " hidden" : "") + '><legend>Area</legend><div class="chips">' +
        areas.map(function (a) { return '<label class="chip"><input type="radio" name="dl-area" value="' + esc(a) + '"' + (s.area === a ? " checked" : "") + "><span>" + esc(a) + "</span></label>"; }).join("") +
      "</div></fieldset>" +
      '<button type="button" class="btn btn--accent dl__done" data-close>Done</button></div>');
    node.addEventListener("change", function (e) {
      var t = e.target;
      if (t.name === "dl-mode") { S().mode = t.value; $(".dl__areas", node).hidden = t.value === "pickup"; commit(); }
      if (t.name === "dl-area") { S().area = t.value; commit(); }
      paintDeliver();
    });
    openSheet(node, { label: "Delivery or pickup" });
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
        if (line) toast(line.n + " added");
        return;
      }
      if (e.target.closest("[data-copy]")) {
        if (!validate(node)) return;
        copyText(buildMessage()).then(function (ok) { toast(ok ? "Copied. Paste it in WhatsApp." : "Copy didn’t work here."); });
        return;
      }
      if (e.target.closest("[data-new]")) { clearOrder(); toast("New order started"); if (node._mode === "sheet") closeSheet(); return; }
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
    });
    return node;
  }
  function suggestions() {
    var lines = liveLines(), brands = brandsInCart();
    if (!brands.length) return "";
    var host = brands.indexOf(HERE) >= 0 ? HERE : brands[0];
    var menu = MENU[host];
    if (!menu || brandStatus(host) !== "open") return "";
    var hasDrink = lines.some(function (l) { var m = MENU[l.b], it = m && m.byId[l.id]; return it && it.kind === "drink"; });
    var hasSide = lines.some(function (l) { var m = MENU[l.b], it = m && m.byId[l.id]; return l.b === host && it && it.kind === "side"; });
    var picks = [];
    if (!hasSide) picks = picks.concat(menu.items.filter(function (i) { return i.kind === "side" && !i.soldOut; }).slice(0, 2));
    if (!hasDrink) picks = picks.concat(menu.items.filter(function (i) { return i.kind === "drink" && !i.soldOut; }));
    if (!picks.length) return "";
    return '<section class="sugg" aria-label="Add to your order"><h3>' + (!hasDrink && !hasSide ? "Add a side or drink" : !hasDrink ? "Add a drink" : "Add a side") + "</h3>" +
      '<div class="sugg__row">' + picks.map(function (i) {
        return '<button type="button" class="sugg__i' + (i.kind === "drink" ? " is-drink" : "") + '" data-add="' + esc(host + "|" + i.id) + '" aria-label="Add ' + esc(i.name) + ", " + money(i.price) + '">' +
          '<span class="sugg__img"><img src="' + esc(path(i.img)) + '" alt="" loading="lazy" decoding="async"><i>' + ICON.plus + "</i></span>" +
          '<span class="sugg__n">' + esc(i.name.replace(/ \(can\)$/, "")) + '</span><span class="sugg__p">' + money(i.price) + "</span></button>";
      }).join("") + "</div></section>";
  }
  function renderOrder(node) {
    var s = S(), lines = liveLines(), brands = brandsInCart(), st = kitchenStatus();
    var focusId = document.activeElement && node.contains(document.activeElement) ? document.activeElement.id : null;
    var html = "";
    var head = node._mode === "sheet"
      ? '<div class="sheet__head"><h2>Your order</h2><button type="button" class="x" data-close aria-label="Close">' + ICON.close + "</button></div>"
      : "";
    if (!lines.length) {
      node.innerHTML = head + '<div class="empty"><p class="empty__t">Your order is empty</p><p>Tap + on any dish.</p>' +
        (PAGE === "brand" && node._mode === "sheet" ? '<button type="button" class="btn btn--accent" data-close>Back to the menu</button>' : '<a class="btn btn--accent" href="' + path("index.html") + '">Browse restaurants</a>') + "</div>";
      return;
    }
    if (s.sentAt) {
      node.innerHTML = head + '<div class="sent"><div class="sent__icon">' + ICON.check + "</div>" +
        "<h3>Order #" + esc(s.no) + " is in WhatsApp</h3>" +
        "<p>Tap <b>Send</b> there. We reply to confirm.</p>" +
        '<a class="btn btn--wa" data-send href="#" target="_blank" rel="noopener">' + ICON.wa + "<span>Open WhatsApp again</span></a>" +
        '<button type="button" class="btn btn--line" data-new>Start a new order</button>' +
        '<button type="button" class="link" data-edit>Edit this order</button></div>';
      wireSend(node);
      return;
    }
    html += head;
    if (!st.open) html += '<p class="note note--warn">We’re closed. ' + esc(st.label) + ". Order now and we confirm when we open.</p>";
    brands.forEach(function (b) {
      if (brands.length > 1) html += '<h3 class="lines__brand">' + esc(brandName(b)) + "</h3>";
      html += '<ul class="lines">' + lines.filter(function (l) { return l.b === b; }).map(function (l) {
        var extra = (l.inc && l.inc.length ? l.inc.join(", ") : "") + (l.inc && l.d && l.d.length ? " · " : "") + (l.d || []).join(" · ");
        return '<li class="line">' +
          '<div class="line__main"><p class="line__n">' + esc(l.n) + "</p>" +
          (extra ? '<p class="line__d">' + esc(extra) + "</p>" : "") +
          (l.soldOut ? '<p class="line__d line__d--warn">Sold out today. Please remove.</p>' : "") +
          '<p class="line__t">' + money(l.p * l.q) + "</p></div>" +
          '<div class="qty"><button type="button" class="qty__b" data-line="' + esc(l.k) + '" data-d="-1" aria-label="' + (l.q === 1 ? "Remove " : "One less ") + esc(l.n) + '">' + ICON.minus + "</button>" +
          '<span class="qty__n">' + l.q + "</span>" +
          '<button type="button" class="qty__b" data-line="' + esc(l.k) + '" data-d="1" aria-label="One more ' + esc(l.n) + '">' + ICON.plus + "</button></div></li>";
      }).join("") + "</ul>";
    });
    html += suggestions();
    var areas = (SITE.areas || []).concat(["Other area"]);
    html += '<form class="form" novalidate onsubmit="return false">' +
      '<fieldset class="seg"><legend class="sr">Delivery or pickup</legend>' +
        '<label><input type="radio" name="oa-mode" value="delivery"' + (s.mode === "delivery" ? " checked" : "") + "><span><b>Delivery</b><small>" + shortMoney(SITE.deliveryFee) + " per order</small></span></label>" +
        '<label><input type="radio" name="oa-mode" value="pickup"' + (s.mode === "pickup" ? " checked" : "") + "><span><b>Pickup</b><small>Free</small></span></label>" +
      "</fieldset>";
    if (s.mode === "delivery") {
      html += '<fieldset class="field field--areas" id="oa-f-area"><legend>Area</legend><div class="chips">' +
        areas.map(function (a) {
          return '<label class="chip"><input type="radio" name="oa-area" value="' + esc(a) + '"' + (s.area === a ? " checked" : "") + "><span>" + esc(a) + "</span></label>";
        }).join("") + '</div><p class="field__err">Pick your area.</p></fieldset>' +
        '<label class="field" id="oa-f-addr"><span class="field__l">Address or landmark</span>' +
        '<textarea id="oa-addr" data-f="addr" rows="2" maxlength="160" autocomplete="street-address" placeholder="Palm Beach 12, yellow house">' + esc(s.addr) + "</textarea>" +
        '<span class="field__err">Add an address for the driver.</span></label>';
    } else {
      html += '<p class="note">We send the pickup address and time on WhatsApp.</p>';
    }
    html += '<label class="field" id="oa-f-name"><span class="field__l">Name</span>' +
      '<input id="oa-name" data-f="name" type="text" maxlength="40" autocomplete="name" value="' + esc(s.name) + '">' +
      '<span class="field__err">Add your name.</span></label>' +
      '<label class="field"><span class="field__l">Note <em>optional</em></span>' +
      '<textarea id="oa-note" data-f="note" rows="2" maxlength="160" placeholder="Allergies, gate code">' + esc(s.note) + "</textarea></label>" +
      "</form>";
    html += '<dl class="sum"><div><dt>Food</dt><dd>' + money(subtotal()) + "</dd></div>" +
      "<div><dt>" + (s.mode === "delivery" ? "Delivery" : "Pickup") + "</dt><dd>" + (s.mode === "delivery" ? money(fee()) : "Free") + "</dd></div>" +
      '<div class="sum__total"><dt>Total</dt><dd>' + money(total()) + "</dd></div></dl>";
    html += '<details class="ticket"><summary>Preview the message</summary><pre>' + esc(buildMessage()) + "</pre></details>";
    html += '<p class="order__hint">Opens WhatsApp with your order. Tap <b>Send</b> there.</p>' +
      '<button type="button" class="link" data-copy>Copy the order instead</button>' +
      '<div class="order__send"><a class="btn btn--wa" data-send href="#" target="_blank" rel="noopener">' + ICON.wa +
      '<span>Send on WhatsApp</span><span class="btn__total">' + money(total()) + "</span></a></div>";
    node.innerHTML = html;
    wireSend(node);
    if (focusId) { var f = document.getElementById(focusId); if (f) f.focus({ preventScroll: true }); }
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
    if (first) {
      first.scrollIntoView({ behavior: "smooth", block: "center" });
      var inp = $("input,textarea", first); if (inp && inp.type !== "radio") inp.focus({ preventScroll: true });
      toast("Fill in the missing details");
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
      if (liveLines().some(function (l) { return l.soldOut; })) { e.preventDefault(); toast("Remove the sold-out dish first"); return; }
      var link = checkoutLink();
      a.href = link.url;
      if (link.short) copyText(link.full).then(function (ok) { toast(ok ? "Long order: it’s copied. Paste it in the chat." : "Tap “Copy the order” and paste it in WhatsApp."); });
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
    $(".bar__label", bar).textContent = S().sentAt ? "Check your order" : stale ? "Continue order" : "View order";
    $(".bar__total", bar).textContent = money(total());
    $("button", bar).setAttribute("aria-label", "View order: " + plural(n, "item", "items") + ", " + money(total()));
  }
  var orderSheet = null;
  function openOrder() {
    if (orderSheet) return;
    var node = orderNode("sheet");
    Promise.all(brandsInCart().map(loadMenu)).then(function () { renderOrder(node); }, function () {});
    orderSheet = openSheet(node, { label: "Your order", cls: "sheet__panel--order", onClose: function () { orderSheet = null; } });
    orderSheet.node = node;
  }

  /* ---------------------------------------------------------------- shared bits */
  function fillCommon() {
    $$("[data-oa-hours]").forEach(function (n) { n.textContent = hoursLabel(); });
    $$("[data-oa-fee]").forEach(function (n) { n.textContent = shortMoney(SITE.deliveryFee); });
    $$("[data-oa-eta]").forEach(function (n) { n.textContent = SITE.eta || ""; });
    $$("[data-oa-areas]").forEach(function (n) { n.textContent = listAnd(SITE.areas || []); });
    $$("[data-oa-ask]").forEach(function (a) { a.href = waLink("Hi! Do you deliver to my area? I’m in "); });
    paintSign(false);
  }
  function setupIAB() {
    var ua = navigator.userAgent || "";
    var iab = /(Instagram|FBAN|FBAV|FB_IAB|musical_ly|BytedanceWebview|Snapchat|Line\/)/i.test(ua);
    if (!iab) return;
    var app = /Instagram/i.test(ua) ? "Instagram" : /FBAN|FBAV|FB_IAB/i.test(ua) ? "Facebook" : /musical_ly|Bytedance/i.test(ua) ? "TikTok" : /Snapchat/i.test(ua) ? "Snapchat" : "this app";
    var box = el('<div class="iab"><p>Opened in ' + esc(app) + "? Tap <b>•••</b> and <b>Open in browser</b> to order on WhatsApp.</p>" +
      '<button type="button" class="btn btn--line btn--sm">Copy link</button></div>');
    var host = $("main") || BODY;
    host.insertBefore(box, host.firstChild);
    $("button", box).addEventListener("click", function () {
      copyText(shareUrl()).then(function (ok) { toast(ok ? "Link copied with your order" : "Use ••• then Open in browser"); });
    });
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
  function listAnd(arr) { return arr.length < 2 ? arr.join("") : arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1]; }
  function paintSign(first) {
    var sign = $("[data-oa-sign]");
    if (!sign) return;
    var st = kitchenStatus();
    sign.innerHTML = st.open ? "<b>Open</b><span>" + esc(st.label.replace(/^Open /, "")) + "</span>" : "<b>Closed</b><span>" + esc(st.label) + "</span>";
    sign.classList.toggle("is-on", st.open);
    if (first && st.open) sign.classList.add("flick");
  }

  /* ---------------------------------------------------------------- restaurant page */
  function renderBrand() {
    var b = HERE, menu = MENU[b], status = brandStatus(b), st = kitchenStatus();
    document.title = menu.name + " · Order Aruba";
    setAccent(menu.color);
    var main = $("#oa-main");
    var feat = menu.items.filter(function (i) { return i.style === "signature" || i.style === "bundle"; });
    var featIds = feat.map(function (i) { return i.id; });
    var secs = menu.sections.map(function (s) {
      return { id: s.id, title: s.title, items: menu.items.filter(function (i) { return i.section === s.id && featIds.indexOf(i.id) < 0; }) };
    }).filter(function (s) { return s.items.length; });
    // cover: a dish that is not already in Featured, real photo first
    var pool = menu.items.filter(function (i) { return i.kind !== "drink" && i.kind !== "side" && featIds.indexOf(i.id) < 0; });
    var pick = pool.filter(function (i) { return i.img.indexOf("/art/") < 0; })[0] || pool[0] || feat[0] || menu.items[0];
    var cover = pick.img;
    var html = '<div class="cover"><img src="' + esc(path(cover)) + '" alt="" width="780" height="446" fetchpriority="high" decoding="async"></div>' +
      '<header class="store">' +
        '<img class="store__mark" src="' + esc(path(menu.mark)) + '" alt="" width="76" height="76">' +
        '<h1 class="store__name" id="store-name">' + esc(menu.name) + "</h1>" +
        '<p class="store__tag">' + esc(menu.tagline) + "</p>" +
        '<ul class="facts">' +
          '<li class="facts__status' + (st.open ? " is-open" : "") + '"><i></i>' + esc(st.label) + "</li>" +
          "<li>" + shortMoney(SITE.deliveryFee) + " delivery</li>" +
          "<li>" + esc(SITE.eta || "") + "</li>" +
        "</ul>" +
        (status === "soon" ? '<p class="note note--warn">Opening soon. Ordering starts shortly.</p>' : "") +
        (status === "hidden" ? '<p class="note note--warn">Not taking orders right now.</p>' : "") +
      "</header>";
    if (feat.length) {
      html += '<section class="sec" id="featured" aria-labelledby="h-featured"><h2 class="sec__t" id="h-featured">Featured</h2>' +
        '<div class="rail rail--feat">' + feat.map(function (i) { return featHTML(b, i); }).join("") + "</div></section>";
    }
    secs.forEach(function (s) {
      html += '<section class="sec" id="' + esc(s.id) + '" aria-labelledby="h-' + esc(s.id) + '"><h2 class="sec__t" id="h-' + esc(s.id) + '">' + esc(s.title) + "</h2>" +
        '<div class="' + (s.id === "drinks" ? "cans" : "rows") + '">' + s.items.map(function (i) { return rowHTML(b, i); }).join("") + "</div></section>";
    });
    html += '<footer class="pfoot"><p>' + esc(menu.imageNote) + " Prices in Aruban florin (ƒ).</p>" +
      '<a class="pfoot__all" href="' + path("index.html") + '">All restaurants</a></footer>';
    main.innerHTML = html;

    var nav = $("#oa-cats");
    if (nav) {
      var tabs = (feat.length ? [{ id: "featured", title: "Featured" }] : []).concat(secs);
      nav.innerHTML = tabs.map(function (s, i) { return '<a href="#' + esc(s.id) + '" data-nav="' + esc(s.id) + '"' + (i === 0 ? ' class="on"' : "") + ">" + esc(s.title) + "</a>"; }).join("");
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

  /* ---------------------------------------------------------------- home page */
  function shopHTML(b, idx) {
    var m = MENU[b];
    if (!m) return "";
    var status = brandStatus(b), from = fromPrice(m);
    var sig = m.items.filter(function (i) { return i.style === "signature"; })[0] || m.items[0];
    return '<a class="shop' + (status !== "open" ? " is-soon" : "") + '" href="' + path(b + "/index.html") + '" style="--shop:' + esc(m.color) + '">' +
      '<div class="shop__media"><img src="' + esc(path(m.hero || sig.img)) + '" alt="' + esc(sig.name) + '" width="780" height="446" loading="' + (idx < 2 ? "eager" : "lazy") + '" decoding="async">' +
        (status !== "open" ? '<span class="shop__soon">Opening soon</span>' : "") + "</div>" +
      '<div class="shop__body"><img class="shop__mark" src="' + esc(path(m.mark)) + '" alt="" width="48" height="48" loading="lazy">' +
        '<div><h3 class="shop__name">' + esc(m.name) + "</h3>" +
        '<p class="shop__meta"><span>' + esc(m.cuisine) + "</span>" + (from && status === "open" ? "<span>From " + money(from) + "</span>" : "") + "</p></div></div></a>";
  }
  function setupSearch(ids) {
    var input = $("#oa-q"), out = $("#oa-results"), browse = $("#oa-browse");
    if (!input || !out || !browse) return;
    function norm(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
    var all = [], seenDrink = {};
    ids.forEach(function (b) {
      var m = MENU[b];
      if (!m || brandStatus(b) !== "open") return;
      m.items.forEach(function (i) {
        if (i.kind === "drink") { if (seenDrink[i.id]) return; seenDrink[i.id] = 1; }
        all.push({ b: b, i: i, hay: norm([i.name, i.desc, m.name, m.cuisine, (i.flags || []).join(" "), i.kind === "drink" ? "drink soda can" : ""].join(" ")) });
      });
    });
    var t;
    function run() {
      var raw = input.value.trim(), q = norm(raw);
      if (!q) { out.hidden = true; browse.hidden = false; return; }
      var words = q.split(/\s+/);
      var hits = all.filter(function (x) { return words.every(function (w) { return x.hay.indexOf(w) >= 0; }); });
      browse.hidden = true; out.hidden = false;
      out.innerHTML = hits.length
        ? '<p class="results__n">' + plural(hits.length, "dish", "dishes") + "</p>" + '<div class="rows">' + hits.map(function (x) { return rowHTML(x.b, x.i, { brand: true }); }).join("") + "</div>"
        : '<p class="results__none">Nothing matches “' + esc(raw) + '”. Try chicken, shrimp or fries.</p>';
    }
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 90); });
    input.addEventListener("search", run);
  }
  function renderHub() {
    var ids = brandList(false);
    paintSign(true);
    paintDeliver();
    Promise.all(ids.map(function (b) { return loadMenu(b).catch(function () { return null; }); })).then(function () {
      var rail = $("#oa-rail"), list = $("#oa-list");
      if (rail) {
        var picks = [];
        ids.forEach(function (b) {
          var m = MENU[b];
          if (!m || brandStatus(b) !== "open") return;
          m.items.filter(function (i) { return (i.style === "signature" || i.style === "bundle") && !i.soldOut; }).forEach(function (i) { picks.push(featHTML(b, i, { brand: true })); });
        });
        rail.innerHTML = picks.join("");
      }
      if (list) list.innerHTML = ids.map(shopHTML).join("");
      setupSearch(ids);
    });
  }

  /* ---------------------------------------------------------------- cart page */
  function renderCartPage() {
    var host = $("#oa-main");
    var node = orderNode("page");
    host.appendChild(node);
    Promise.all(brandsInCart().map(function (b) { return loadMenu(b).catch(function () {}); })).then(function () { renderOrder(node); });
    onChange(function () { renderOrder(node); });
  }

  /* ---------------------------------------------------------------- boot */
  function boot() {
    loadSite().then(function () {
      state = readStore();
      var first = PAGE === "brand" ? loadMenu(HERE) : Promise.resolve();
      return first.then(importHash).then(function () {
        fillCommon();
        setInterval(fillCommon, 60000);
        if (PAGE === "brand") renderBrand();
        if (PAGE === "hub") renderHub();
        if (PAGE === "cart") renderCartPage();
        $$("[data-oa-open-order]").forEach(function (b) { b.addEventListener("click", function (e) { e.preventDefault(); openOrder(); }); });
        setupIAB();
        paintBar();
        onChange(function () {
          paintBar(); repaintCards();
          if (orderSheet && orderSheet.node) renderOrder(orderSheet.node);
        });
        // menus for lines from other restaurants (keeps names and prices fresh)
        brandsInCart().forEach(function (b) { loadMenu(b).catch(function () {}); });
        document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") { state = readStore(); emit(); } });
        BODY.classList.add("oa-ready");
      });
    }).catch(function (err) {
      console.error(err);
      var main = $("#oa-main") || BODY;
      main.insertAdjacentHTML("afterbegin", '<p class="note note--warn">The menu didn\u2019t load. Check your connection and refresh.</p>');
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
