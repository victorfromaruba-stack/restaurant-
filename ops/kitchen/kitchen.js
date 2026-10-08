/* Kitchen app: Prep / Cook an order / Close up.
   Data: kitchen-data.json (built by _build/make_data.py). No libraries, works offline once loaded.
   Saved on this device (localStorage): open orders, running timers, prep + close-up ticks per date. */
(function () {
  'use strict';

  var DATA = null;
  var DISH = {};
  var BRAND = {};
  var INDEX = [];
  var main = document.getElementById('main');
  var bar = document.getElementById('bar');
  var foot = document.getElementById('foot');
  var tray = document.getElementById('tray');
  var sheet = document.getElementById('sheet');
  var toastEl = document.getElementById('toast');

  // ------------------------------------------------------------------ helpers
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: keep going */ } },
    del: function (k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } }
  };
  var KEY_ORDERS = 'kitchen.orders.v1';
  // Victor's bookkeeping app. Shop receipts are photographed there (the chef needs a Book Keeper login).
  var BOOKKEEPER = 'https://bookingkeepingaruba.vercel.app';
  var KEY_TIMERS = 'kitchen.timers.v1';
  function ticksKey(list, date) { return 'kitchen.' + list + '.' + date; }

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function today() { var d = new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function niceDate() {
    try { return new Date().toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' }); }
    catch (e) { return today(); }
  }
  function clock(ts) { var d = new Date(ts); return pad(d.getHours()) + ':' + pad(d.getMinutes()); }
  function fmtDur(sec) {
    if (sec < 60 || (sec <= 120 && sec % 60)) return sec + ' sec';
    if (sec < 3600) { var m = Math.floor(sec / 60), s = sec % 60; return m + ' min' + (s ? ' ' + s + ' sec' : ''); }
    var h = Math.floor(sec / 3600), mm = Math.round((sec % 3600) / 60);
    return h + ' h' + (mm ? ' ' + mm + ' min' : '');
  }
  function fmtLeft(ms) {
    var s = Math.max(0, Math.ceil(ms / 1000));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return h ? h + ':' + pad(m) + ':' + pad(x) : m + ':' + pad(x);
  }
  var toastT = 0, toastAt = 0;
  function toast(msg, ms) {
    toastEl.textContent = msg; toastEl.hidden = false; toastAt = Date.now();
    clearTimeout(toastT); toastT = setTimeout(function () { toastEl.hidden = true; }, ms || 2600);
  }
  toastEl.addEventListener('click', function () { toastEl.hidden = true; });
  function go(hash, replace) {
    if (replace) { history.replaceState(null, '', hash); render(); }
    else if (location.hash === hash) render();
    else location.hash = hash;
  }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

  // A photo tile. When the picture is missing (being redrawn) it turns into a plain tile with the name.
  function photo(src, name, accent, cls) {
    var style = accent ? ' style="--acc:' + esc(accent) + '"' : '';
    if (!src) return '<div class="ph noimg ' + (cls || '') + '"' + style + '><span class="ph-name">' + esc(name) + '</span></div>';
    return '<div class="ph ' + (cls || '') + '"' + style + '><img src="' + esc(src) + '" alt="" decoding="async">' +
      '<span class="ph-name">' + esc(name) + '</span></div>';
  }
  document.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t.tagName === 'IMG' && t.parentNode && t.parentNode.classList && t.parentNode.classList.contains('ph')) {
      t.parentNode.classList.add('noimg');
      t.parentNode.removeChild(t);
    }
  }, true);

  // ------------------------------------------------------------------ names + matching
  function norm(s) {
    s = String(s || '').toLowerCase();
    if (s.normalize) s = s.normalize('NFD').replace(/[̀-ͯ]/g, '');
    return s.replace(/[’‘`´']/g, '').replace(/&/g, ' and ').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  var STOP = { 'with': 1, 'the': 1, 'a': 1, 'and': 1, 'of': 1, 'can': 1, 'order': 1, 'side': 1 };
  function loose(s) {
    return norm(String(s || '').replace(/\([^)]*\)/g, ' ')).split(' ').filter(function (w) { return w && !STOP[w]; }).join(' ');
  }
  function toks(s) {
    return loose(s).split(' ').filter(Boolean).map(function (w) { return w.length > 3 ? w.replace(/(es|s)$/, '') : w; });
  }
  function dice(a, b) {
    if (!a.length || !b.length) return 0;
    var hit = 0, used = {};
    a.forEach(function (w) { for (var i = 0; i < b.length; i++) { if (!used[i] && b[i] === w) { used[i] = 1; hit++; break; } } });
    return (2 * hit) / (a.length + b.length);
  }
  function buildIndex() {
    INDEX = [];
    Object.keys(DISH).forEach(function (k) {
      var d = DISH[k];
      [d.name].concat(d.aliases || []).forEach(function (nm) {
        INDEX.push({ key: k, brand: d.brand, n: norm(nm), l: loose(nm), t: toks(nm) });
      });
    });
  }
  function matchDish(name, brandId) {
    var n = norm(name), l = loose(name), t = toks(name);
    var pools = brandId
      ? [INDEX.filter(function (x) { return x.brand === brandId || x.brand === null; }), INDEX]
      : [INDEX];
    var i, hit;
    for (i = 0; i < pools.length; i++) {
      hit = pools[i].filter(function (x) { return x.n === n; })[0] || pools[i].filter(function (x) { return x.l === l; })[0];
      if (hit) return hit.key;
    }
    for (i = 0; i < pools.length; i++) {
      var best = null, score = 0;
      pools[i].forEach(function (x) { var s = dice(t, x.t); if (s > score) { score = s; best = x; } });
      if (best && score >= 0.6) return best.key;
    }
    return null;
  }
  function matchBrand(text) {
    var n = norm(String(text || '').replace(/^[\s—–=:-]+|[\s—–=:-]+$/g, ''));
    if (!n) return null;
    for (var i = 0; i < DATA.brands.length; i++) {
      var b = DATA.brands[i];
      if (norm(b.name) === n) return b;
    }
    return null;
  }

  // ------------------------------------------------------------------ WhatsApp order parser
  function stripMarks(line) {
    return line.replace(/\*([^*]*)\*/g, '$1').replace(/(^|\s)_([^_]+)_(?=\s|$)/g, '$1$2').replace(/^[*_~]+|[*_~]+$/g, '').trim();
  }
  function splitTop(s, sep) {
    // split on commas that are not inside brackets
    var out = [], depth = 0, cur = '';
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (ch === '(') depth++;
      if (ch === ')') depth = Math.max(0, depth - 1);
      if (ch === sep && depth === 0) { out.push(cur); cur = ''; } else cur += ch;
    }
    out.push(cur);
    return out.map(function (x) { return x.trim(); }).filter(Boolean);
  }
  /* "ƒ25.90" at the end of a line -> 2590 (cents). Also reads "25,90" and "1,234.50". */
  function priceOf(text) {
    var m = /(?:ƒ|afl\.?|awg|fl\.?|f(?=\s?\d))\s*(\d[\d.,]*)\s*\**\s*$/i.exec(String(text || '').trim());
    if (!m) return null;
    var v = m[1].replace(/,(\d{2})$/, '.$1').replace(/,/g, '');
    var c = Math.round(parseFloat(v) * 100);
    return isFinite(c) ? c : null;
  }
  function parseItemLine(text, brandId) {
    var price = priceOf(text);
    var s = text
      .replace(/\s*[—–-]*\s*(?:ƒ|afl\.?|awg|fl\.?|f(?=\s?\d))\s*\d[\d.,]*\s*$/i, '')
      .replace(/\s+[—–-]+\s*\d+[.,]\d{2}\s*$/, '')
      .replace(/\s+[—–-]+\s*$/, '')
      .trim();
    var m = /^(\d{1,3})\s*[x×X✕✖*]\s*(.+)$/.exec(s);
    if (m) return { qty: +m[1], name: m[2].trim(), price: price };
    m = /^(.+?)\s*[x×X]\s*(\d{1,3})$/.exec(s);
    if (m && matchDish(m[1], brandId)) return { qty: +m[2], name: m[1].trim(), price: price };
    m = /^(\d{1,3})\s+(.+)$/.exec(s);
    if (m && matchDish(m[2], brandId)) return { qty: +m[1], name: m[2].trim(), price: price };
    return null;
  }
  function parseOrder(text) {
    var o = {
      id: 'o' + uid(), no: '', title: '', brandId: null, multi: false, mode: '', area: '', preorder: false,
      name: '', address: '', note: '', phone: '', lines: [], other: [], created: Date.now(), closed: false
    };
    var cur = null, last = null, header = false, sawFee = false;
    String(text || '').replace(/\r\n?/g, '\n').split('\n').forEach(function (raw) {
      var line = raw.replace(/[   \t]/g, ' ').replace(/[​-‍﻿]/g, '').trim();
      if (!line) { last = null; return; }
      var bare = stripMarks(line), m;
      if (!bare) return;
      if ((m = /^(name|customer|address|addr|note|notes|comment|phone|tel|mobile|time|when|pay|payment)\s*:\s*(.*)$/i.exec(bare))) {
        var f = m[1].toLowerCase(), v = m[2].trim();
        if (/^(time|when)$/.test(f)) o.time = v;
        else if (/^pay/.test(f)) o.pay = v;
        else if (/^(name|customer)$/.test(f)) o.name = v;
        else if (/^addr/.test(f)) o.address = v;
        else if (/^(note|notes|comment)$/.test(f)) o.note = v;
        else o.phone = v;
        last = null; return;
      }
      if (/^pre[\s-]?order\b/i.test(bare)) { o.preorder = true; last = null; return; }
      if (!header && /\border\b/i.test(bare) && (/#/.test(bare) || (!o.lines.length && !cur))) {
        m = /^(.*?)\s*\border\b[\s:]*(?:#\s*([A-Za-z0-9-]+))?/i.exec(bare);
        if (m) {
          header = true;
          o.no = m[2] || '';
          var b = matchBrand(m[1]);
          if (b) { o.brandId = b.id; cur = b.id; o.title = b.name; }
          else { o.multi = true; o.title = 'Kitchen order'; }
          last = null; return;
        }
      }
      var br = matchBrand(bare);
      if (br) { cur = br.id; last = null; if (!o.title) o.title = br.name; return; }
      if (/^drinks?$/i.test(bare)) { last = null; return; }   // website groups cans under *Drinks*
      if (/^total\b/i.test(bare)) { var tm = /ƒ\s*([\d.,]+)/.exec(bare); if (tm) o.total = tm[1]; o.totalC = priceOf(bare); }
      if (/^sub\s*-?\s*total\b/i.test(bare)) o.subtotalC = priceOf(bare);
      if (/^(sub\s*-?\s*total|total|delivery fee|service|tip|discount|fee)\b/i.test(bare)) {
        if (/^delivery fee/i.test(bare)) sawFee = true;
        last = null; return;
      }
      if ((m = /^(delivery|deliver|pick\s*-?\s*up|collection)\b\s*[·•:|,—–-]*\s*(.*)$/i.exec(bare))) {
        if (/ƒ|\bafl\b|awg|\d+[.,]\d{2}/i.test(m[2])) { if (/^d/i.test(m[1])) sawFee = true; o.feeC = priceOf(bare); last = null; return; }
        o.mode = /^d/i.test(m[1]) ? 'Delivery' : 'Pickup';
        o.area = m[2].replace(/^[·•:|,—–-\s]+/, '').trim();
        last = null; return;
      }
      var it = parseItemLine(bare, cur);
      if (it) {
        last = { qty: it.qty, raw: it.name, brandId: cur, key: matchDish(it.name, cur), mods: [], includes: null, price: it.price };
        o.lines.push(last);
        return;
      }
      if (last) {
        var t = bare.replace(/^[-•–—>\s]+/, '').trim();
        var inc = /^includes?\s*:\s*(.*)$/i.exec(t);
        if (inc) { last.includes = (last.includes || []).concat(splitTop(inc[1], ',')); return; }
        if (last.key && DISH[last.key] && DISH[last.key].kind === 'bundle' && matchDish(t, cur)) {
          last.includes = (last.includes || []).concat([t.replace(/\s*[x×]\s*\d+$/, '')]);
          return;
        }
        t.split(/\s*[·•|]\s*/).forEach(function (p) { p = p.trim(); if (p) last.mods.push(p); });
        return;
      }
      o.other.push(line);
    });
    if (!o.mode && (sawFee || o.address)) o.mode = 'Delivery';
    o.items = expandLines(o.lines);
    if (!o.title) o.title = o.items.length ? 'Order' : '';
    return o;
  }
  function expandLines(lines) {
    var items = [];
    lines.forEach(function (ln) {
      var d = ln.key ? DISH[ln.key] : null;
      if (!d) {
        items.push({ uid: uid(), key: null, name: ln.raw, qty: ln.qty, mods: ln.mods, unknown: true, brand: ln.brandId, done: false });
        return;
      }
      if (d.kind === 'drink') {
        items.push({ uid: uid(), key: d.key, name: d.name, qty: ln.qty, mods: ln.mods, drink: true, brand: null, done: false });
        return;
      }
      if (d.kind === 'bundle') {
        var keys = (d.includes || []).slice();
        if (ln.includes && ln.includes.length) {
          var named = ln.includes.map(function (n) { return matchDish(n, d.brand); });
          if (named.every(Boolean)) keys = named;
        }
        keys.forEach(function (k) {
          items.push({ uid: uid(), key: k, name: DISH[k].name, qty: ln.qty, mods: ln.mods.slice(), brand: DISH[k].brand,
            bundle: { key: d.key, name: d.name }, done: false });
        });
        return;
      }
      items.push({ uid: uid(), key: d.key, name: d.name, qty: ln.qty, mods: ln.mods, brand: d.brand, done: false });
    });
    return items;
  }

  // ------------------------------------------------------------------ orders store
  function loadOrders() { return store.get(KEY_ORDERS, []); }
  function saveOrders(list) {
    // keep open orders + the 30 most recent closed ones
    var open = list.filter(function (o) { return !o.closed; });
    var closed = list.filter(function (o) { return o.closed; }).slice(-30);
    store.set(KEY_ORDERS, open.concat(closed));
  }
  function getOrder(id) { return loadOrders().filter(function (o) { return o.id === id; })[0] || null; }
  function putOrder(o) {
    var list = loadOrders(), found = false;
    list = list.map(function (x) { if (x.id === o.id) { found = true; return o; } return x; });
    if (!found) list.push(o);
    saveOrders(list);
  }
  function orderLabel(o) { return o.no ? 'Order #' + o.no : (o.manual ? 'Picked dishes · ' + clock(o.created) : 'Order · ' + clock(o.created)); }
  function itemsDone(o) { return o.items.filter(function (i) { return i.done; }).length; }

  // ------------------------------------------------------------------ allergies + modifiers
  var ALLERGY = [
    [/peanut|\bnuts?\b|satay|sat[eé]\b/i, 'peanut'], [/gluten|wheat|c(o)?eliac/i, 'gluten'],
    [/shellfish|shrimp|prawn|seafood/i, 'shellfish'], [/dairy|milk|lactose|cheese/i, 'dairy'],
    [/\beggs?\b/i, 'egg'], [/\bsoya?\b/i, 'soy'], [/sesame/i, 'sesame'], [/mustard/i, 'mustard']
  ];
  function noteAllergens(note) {
    var out = [];
    ALLERGY.forEach(function (a) { if (a[0].test(note || '') && out.indexOf(a[1]) < 0) out.push(a[1]); });
    return out;
  }
  function isAllergyNote(note) { return !!note && (noteAllergens(note).length > 0 || /allerg|intoleran|vegan|vegetarian|halal|kosher|pork/i.test(note)); }
  function conflicts(order, dish) {
    if (!order || !order.note || !dish) return [];
    var al = dish.allergens || [], fl = dish.flags || [];
    var hits = noteAllergens(order.note).filter(function (a) { return al.indexOf(a) >= 0 || fl.indexOf(a) >= 0; });
    if (/pork|halal/i.test(order.note) && fl.indexOf('pork') >= 0) hits.push('pork');
    return hits;
  }
  var SKIP_WORDS = {
    'onion': ['onions', 'onion'], 'scallion': ['scallions', 'scallion'], 'egg': ['eggs', 'egg'],
    'peppers': ['bell peppers', 'pepper strips', 'peppers', 'pepper'], 'cilantro': ['cilantro'],
    'cream': ['sour cream', 'crema', 'cream'], 'lettuce': ['lettuce'], 'black beans': ['black beans', 'beans'],
    'cheddar': ['cheddar'], 'tomato': ['tomatoes', 'tomato'], 'pickles': ['pickles', 'pickle'], 'ketchup': ['ketchup'],
    'mayo': ['mayo'], 'parmesan': ['parmesan', 'parm'], 'shallot': ['fried onion', 'shallot'], 'curry ketchup': ['curry ketchup']
  };
  function skipList(mods) {
    var words = [];
    (mods || []).forEach(function (m) {
      var x = /^no\s+(.+)$/i.exec(m.trim());
      if (!x) return;
      var k = x[1].toLowerCase();
      words = words.concat(SKIP_WORDS[k] || [k]);
    });
    return words;
  }
  function markSkips(html, words) {
    if (!words.length) return html;
    var rx = new RegExp('\\b(' + words.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')\\b', 'gi');
    return html.replace(rx, function (m, w, off, str) {
      var pre = str.slice(Math.max(0, off - 9), off).toLowerCase();
      if (/(white|black|cracked|curry)\s$/.test(pre) && /pepper|ketchup/i.test(m)) return m;
      if (/curry\s$/.test(pre)) return m;
      return '<mark class="skip">No ' + m + '</mark>';
    });
  }

  // ------------------------------------------------------------------ ticks (prep / close)
  function getTicks(list) { return store.get(ticksKey(list, today()), {}); }
  function setTick(list, id, on) {
    var t = getTicks(list);
    if (on) t[id] = Date.now(); else delete t[id];
    store.set(ticksKey(list, today()), t);
  }
  function findTask(list, id) {
    var secs = DATA[list] || [];
    for (var i = 0; i < secs.length; i++) {
      for (var j = 0; j < secs[i].tasks.length; j++) if (secs[i].tasks[j].id === id) return { task: secs[i].tasks[j], sec: secs[i] };
    }
    return null;
  }

  // ------------------------------------------------------------------ timers
  var TIMERS = store.get(KEY_TIMERS, []);
  var actx = null, lastBeep = 0, wakeLock = null;
  function saveTimers() { store.set(KEY_TIMERS, TIMERS); }
  function activated() { return !navigator.userActivation || navigator.userActivation.hasBeenActive; }
  function audio() {
    try {
      if (!actx) {
        if (!activated()) return null; // browsers only allow sound after the first tap
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        actx = new AC();
      }
      if (actx.state === 'suspended') actx.resume();
    } catch (e) { return null; }
    return actx;
  }
  document.addEventListener('pointerdown', function () { audio(); }, { passive: true });
  function beep() {
    var a = audio();
    if (!a || a.state !== 'running') return;
    var t0 = a.currentTime + 0.02;
    [0, 0.22, 0.44, 0.66].forEach(function (dt, i) {
      var o = a.createOscillator(), g = a.createGain();
      o.type = 'square';
      o.frequency.value = i % 2 ? 1320 : 990;
      g.gain.setValueAtTime(0.0001, t0 + dt);
      g.gain.exponentialRampToValueAtTime(0.7, t0 + dt + 0.01);
      g.gain.setValueAtTime(0.7, t0 + dt + 0.15);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + dt + 0.19);
      o.connect(g); g.connect(a.destination);
      o.start(t0 + dt); o.stop(t0 + dt + 0.2);
    });
  }
  function keepAwake() {
    var want = TIMERS.length > 0;
    try {
      if (want && !wakeLock && navigator.wakeLock && document.visibilityState === 'visible') {
        navigator.wakeLock.request('screen').then(function (l) {
          wakeLock = l;
          l.addEventListener('release', function () { wakeLock = null; });
        }).catch(function () { /* not allowed - fine */ });
      } else if (!want && wakeLock) { wakeLock.release(); wakeLock = null; }
    } catch (e) { /* ignore */ }
  }
  function startTimer(t) {
    TIMERS = TIMERS.filter(function (x) { return x.id !== t.id; });
    TIMERS.push({ id: t.id, label: t.label, title: t.title, sec: t.sec, ends: Date.now() + t.sec * 1000, href: t.href, fired: false });
    saveTimers();
    audio();
    keepAwake();
    drawTray(true);
  }
  function stopTimer(id) {
    TIMERS = TIMERS.filter(function (x) { return x.id !== id; });
    saveTimers();
    keepAwake();
    drawTray(true);
    if (!TIMERS.some(function (x) { return x.fired; })) document.title = 'Kitchen';
  }
  var trayIds = '';
  function drawTray(force) {
    var now = Date.now();
    var list = TIMERS.slice().sort(function (a, b) { return (b.fired - a.fired) || (a.ends - b.ends); });
    var ids = list.map(function (t) { return t.id + (t.fired ? '!' : ''); }).join('|');
    if (force || ids !== trayIds) {
      trayIds = ids;
      tray.innerHTML = list.map(function (t) {
        return '<button class="tm' + (t.fired ? ' done' : '') + '" data-act="tray" data-id="' + esc(t.id) + '">' +
          '<span class="tm-t">' + esc(t.title) + '</span><span class="tm-l">' + esc(t.label) + '</span>' +
          '<span class="tm-r" data-left="' + esc(t.id) + '">' + (t.fired ? 'DONE' : fmtLeft(t.ends - now)) + '</span></button>';
      }).join('');
    }
    list.forEach(function (t) {
      var left = t.fired ? 'DONE' : fmtLeft(t.ends - now);
      var els = document.querySelectorAll('[data-left="' + (window.CSS && CSS.escape ? CSS.escape(t.id) : t.id) + '"]');
      for (var i = 0; i < els.length; i++) if (els[i].textContent !== left) els[i].textContent = left;
    });
  }
  function tick() {
    var now = Date.now(), fired = [];
    TIMERS.forEach(function (t) { if (!t.fired && t.ends <= now) { t.fired = true; fired.push(t); } });
    if (fired.length) {
      saveTimers();
      drawTray(true);
      toast('TIMER DONE: ' + fired.map(function (t) { return t.label + ' · ' + t.title; }).join(' / '), 6000);
      var cur = currentTimerButtons();
      if (fired.some(function (t) { return cur.indexOf(t.id) >= 0; })) render(true);
    } else {
      drawTray(false);
    }
    var ringing = TIMERS.some(function (t) { return t.fired; });
    if (ringing) {
      document.title = (Math.floor(now / 800) % 2 ? 'TIMER DONE' : '* TIMER DONE *') + ' · Kitchen';
      if (now - lastBeep > 1500) {
        lastBeep = now;
        beep();
        try { if (navigator.vibrate && activated()) navigator.vibrate([400, 150, 400, 150, 400]); } catch (e) { /* ignore */ }
      }
    }
  }
  function currentTimerButtons() {
    var out = [], els = main.querySelectorAll('[data-tid]');
    for (var i = 0; i < els.length; i++) out.push(els[i].getAttribute('data-tid'));
    return out;
  }
  function timerButton(tid, t, title, href) {
    var run = TIMERS.filter(function (x) { return x.id === tid; })[0];
    if (run && run.fired) {
      return '<button class="tbtn done" data-act="tray" data-id="' + esc(tid) + '" data-tid="' + esc(tid) + '">TIMER DONE · tap to stop<small>' + esc(t.label) + '</small></button>';
    }
    if (run) {
      return '<button class="tbtn run" data-act="tray" data-id="' + esc(tid) + '" data-tid="' + esc(tid) + '"><span><span data-left="' + esc(tid) + '">' +
        fmtLeft(run.ends - Date.now()) + '</span> left</span><small>' + esc(t.label) + ' · running</small></button>';
    }
    return '<button class="tbtn" data-act="timer" data-tid="' + esc(tid) + '" data-sec="' + t.sec + '" data-label="' + esc(t.label) +
      '" data-title="' + esc(title) + '" data-href="' + esc(href) + '">Start ' + fmtDur(t.sec) + ' timer<small>' + esc(t.label) + '</small></button>';
  }

  // ------------------------------------------------------------------ cards
  function dishCards(d) {
    var cards = [];
    if (d.ahead) cards.push({ t: 'ahead' });
    if (d.before) cards.push({ t: 'before' });
    (d.steps || []).forEach(function (s, i) { cards.push({ t: 'step', i: i }); });
    cards.push({ t: 'plate' });
    cards.push({ t: 'pack' });
    return cards;
  }
  function taskCards(task) {
    var l = task.link, d = DISH[l.dish];
    if (!d) return [];
    if (l.flow === 'ahead') return [{ t: 'ahead' }].concat(d.label ? [{ t: 'label' }] : []);
    if (l.flow === 'before') return [{ t: 'before' }];
    return (l.steps || []).map(function (i) { return { t: 'step', i: i }; });
  }
  function linesHtml(lines, skips, cls) {
    if (!lines || !lines.length) return '';
    return '<ul class="lines' + (cls ? ' ' + cls : '') + '">' + lines.map(function (l) {
      return '<li>' + markSkips(keepUnits(esc(l)), skips) + '</li>';
    }).join('') + '</ul>';
  }
  function keepUnits(html) {
    // "60 s", "2–3 min", "15 g", "8 × 8" never break across lines
    return html
      .replace(/\d+(?:[.,]\d+)?(?:\s*[–-]\s*\d+(?:[.,]\d+)?)?\s?(?:s|sec|min|h|g|kg|ml|L|cm|oz|°C)(?![A-Za-z])/g,
        function (m) { return '<span class="nw">' + m + '</span>'; })
      .replace(/(\d) × (?=\d)/g, '$1\u00a0×\u00a0');
  }
  function checksHtml(checks, notes) {
    return (checks || []).map(function (c) {
      return '<div class="check"><span class="k">Check with the probe</span><span class="t">' + c + '°C</span>' +
        '<span class="s">in the middle</span>' +
        ((notes && notes.length) ? '<span class="n">' + esc(notes.join(' · ')) + '</span>' : '') + '</div>';
    }).join('');
  }
  function heatHtml(heat) {
    var seen = {};
    return (heat || []).filter(function (h) { var k = h.kind + h.temp; if (seen[k]) return false; seen[k] = 1; return true; })
      .map(function (h) { return '<span class="heat">' + esc(h.kind) + ' ' + esc(h.temp) + '</span>'; }).join('');
  }
  function fixesHtml(fixes) {
    return (fixes || []).map(function (f) {
      var stop = /^STOP/.test(f.then);
      return '<div class="fix' + (stop ? ' stop' : '') + '"><b>If: ' + esc(f.if) + '</b><span>→ ' + esc(f.then) + '</span></div>';
    }).join('');
  }
  function containsHtml(d) {
    if (!d.allergens || !d.allergens.length) return '';
    return '<p class="contains">Contains: <b>' + esc(d.allergens.join(' · ')) + '</b></p>';
  }

  // ctx: {dish, item, order, cards, c, tid, title, href(c), mode: 'order'|'task'}
  function cardBody(ctx) {
    var d = ctx.dish, card = ctx.cards[ctx.c], skips = skipList(ctx.item ? ctx.item.mods : []);
    var h = '', timers = [], kind = '', title = '';
    var tTitle = (ctx.item && ctx.item.qty > 1 ? ctx.item.qty + ' × ' : '') + d.name;
    if (card.t === 'ahead') {
      var a = d.ahead;
      kind = ctx.mode === 'order' ? 'Made ahead? Check the fridge' : 'Prep';
      title = a.title;
      if (ctx.mode === 'order') h += '<p class="sec-note">Cooking now? This had to be done earlier. Check it is ready in the fridge.</p>';
      h += linesHtml(a.lines, []);
      if (ctx.mode !== 'order') timers = a.timers || [];
      h += checksHtml(a.checks);
      h += fixesHtml(a.fixes);
    } else if (card.t === 'before') {
      var b = d.before;
      kind = 'Before you start';
      title = '';
      h += linesHtml(b.lines, skips);
      timers = b.timers || [];
      h += checksHtml(b.checks);
    } else if (card.t === 'step') {
      var s = d.steps[card.i];
      kind = s.prep ? 'Prep step' : '';
      h += linesHtml(s.lines, skips);
      h += heatHtml(s.heat) ? '<div>' + heatHtml(s.heat) + '</div>' : '';
      h += checksHtml(s.checks, s.checkNotes);
      timers = s.timers || [];
      if (ctx.c === firstCookCard(ctx.cards)) h += containsHtml(d);
    } else if (card.t === 'plate') {
      var p = d.plating || { lines: [] };
      kind = 'Plate it';
      title = 'Make it look great';
      h += linesHtml(p.lines, skips);
      if (p.remember && p.remember.length) h += '<h2>Remember</h2>' + linesHtml(p.remember, skips, 'small');
      timers = p.timers || [];
    } else if (card.t === 'pack') {
      var k = d.pack || { lines: [], hold: [] };
      kind = 'Pack it';
      title = 'Pack and send';
      var packLines = (k.lines || []).slice();
      if (ctx.item && ctx.item.bundle) {
        var bd = DISH[ctx.item.bundle.key];
        if (bd) {
          packLines = (bd.pack && bd.pack.lines || packLines).slice();
          (bd.steps || []).forEach(function (st) { st.lines.slice(1).forEach(function (l) { packLines.push(l); }); });
        }
      }
      h += linesHtml(packLines, []);
      var side = (ctx.item ? ctx.item.mods : []).filter(function (m) { return /on the side/i.test(m); });
      if (side.length) h += '<div class="banner mods">' + esc(side.join(' · ')) + ': add a cup on the side</div>';
      if (k.hold && k.hold.length) h += '<h2>Holding</h2>' + linesHtml(k.hold, [], 'small');
      h += containsHtml(d);
      if (ctx.order) {
        var drinks = ctx.order.items.filter(function (i) { return i.drink; });
        if (drinks.length) h += '<h2>Drinks in this order</h2>' + linesHtml(drinks.map(function (i) { return 'Grab ' + i.qty + ' × ' + DISH[i.key].grab; }), [], 'small');
      }
    } else if (card.t === 'label') {
      kind = 'Label it';
      title = 'Label the container';
      var br = BRAND[d.brand] || {};
      h += '<div class="labelcard">' +
        '<div><small>Restaurant</small>' + esc(br.name || '') + '</div>' +
        '<div><small>What</small>' + esc(d.label.name) + '</div>' +
        '<div><small>Allergens</small>' + esc((d.allergens || []).join(', ') || 'none') + '</div>' +
        '<div><small>Use-by</small>Date + time</div>' +
        '<div><small>Next step</small>' + esc(d.label.next) + '</div></div>';
    }
    var tb = timers.map(function (t, k2) { return timerButton(ctx.tid + ':' + ctx.c + ':' + k2, t, tTitle, ctx.href(ctx.c)); }).join('');
    var tools = '';
    var fx = (d.fixes || []);
    if (fx.length && card.t !== 'ahead') tools += '<button class="ghost" data-act="fixes">Problem? What to do</button>';
    if (d.ingredients && d.ingredients.length) tools += '<button class="ghost" data-act="ingredients">Ingredients (batch of 10)</button>';
    return '<div class="card">' + photo(d.img, d.name, (BRAND[d.brand] || {}).accent, 'hero') +
      '<section class="stack">' +
      '<div>' + (kind ? '<p class="card-kind">' + esc(kind) + '</p>' : '') + (title ? '<h1 class="card-title">' + esc(title) + '</h1>' : '') + h + '</div>' +
      (tb ? '<div class="stack">' + tb + '</div>' : '') +
      (tools ? '<div class="tools">' + tools + '</div>' : '') +
      '</section></div>';
  }
  function firstCookCard(cards) {
    for (var i = 0; i < cards.length; i++) if (cards[i].t === 'step') return i;
    return -1;
  }

  // ------------------------------------------------------------------ screens
  var picks = {};
  var draft = '';
  var lastErr = '';
  var sheetCtx = null;

  function setBar(opts) {
    var acc = opts.accent ? '<span class="accent" style="background:' + esc(opts.accent) + '"></span>' : '';
    bar.innerHTML = (opts.home === false ? '' : '<a class="home" href="#/">Home</a>') + acc +
      '<div class="t">' + (opts.sub ? '<small>' + esc(opts.sub) + '</small>' : '') + '<b>' + esc(opts.title) + '</b></div>' +
      (opts.side ? '<a class="side" href="' + esc(opts.side.href) + '">' + esc(opts.side.label) + '</a>' : '');
  }

  function screenHome() {
    setBar({ title: 'Kitchen', sub: niceDate(), home: false });
    var open = loadOrders().filter(function (o) { return !o.closed; });
    var pc = countTicks('prep'), cc = countTicks('close');
    main.innerHTML = '<div class="home-grid">' +
      '<a class="big-mode prep" href="#/prep"><b>Prep</b><span>Night before, morning, before you open</span>' +
      '<span class="count">' + pc.done + ' of ' + pc.total + ' done today</span></a>' +
      '<a class="big-mode cook" href="#/cook"><b>Cook an order</b><span>Paste the WhatsApp order or pick dishes</span>' +
      (open.length ? '<span class="count">' + open.length + ' open order' + (open.length > 1 ? 's' : '') + '</span>' : '') + '</a>' +
      '<a class="big-mode close" href="#/close"><b>Close up</b><span>Cool down, label, throw away, clean</span>' +
      '<span class="count">' + cc.done + ' of ' + cc.total + ' done today</span></a>' +
      '<a class="big-mode books" href="' + esc(BOOKKEEPER + '/dashboard/receipts') + '" target="_blank" rel="noopener"><b>Receipts</b>' +
      '<span>Bought something? Take a photo of the shop receipt. It goes into Book Keeper.</span></a>' +
      '</div>' +
      '<div class="home-foot" id="oldScreens" hidden><h2>Old screens</h2><div class="old-links">' +
      '<a href="../chef.html">Chef hub</a><a href="../checklist.html">Shopping checklist</a>' +
      '<a href="../buyer.html">Buyer list</a><a href="../recipes.html">Plate receipts</a></div></div>';
    foot.innerHTML = '';
    // The old screens hold costs and buyer prices, so they only exist on the private copy (not the public site).
    try {
      fetch('../chef.html', { method: 'HEAD', cache: 'no-store' }).then(function (r) {
        var el = document.getElementById('oldScreens');
        if (el && r.ok) el.hidden = false;
      }, function () {});
    } catch (e) { /* no fetch: keep hidden */ }
  }
  function countTicks(list) {
    var t = getTicks(list), total = 0, done = 0;
    (DATA[list] || []).forEach(function (s) { s.tasks.forEach(function (x) { total++; if (t[x.id]) done++; }); });
    return { total: total, done: done };
  }

  var scrollToTask = null;
  function screenList(list, secId) {
    var ticks = getTicks(list), cnt = countTicks(list);
    setBar({ title: list === 'prep' ? 'Prep' : 'Close up', sub: niceDate() + ' · ' + cnt.done + ' of ' + cnt.total + ' done' });
    var secs = DATA[list];
    var h = '<div class="jump">' + secs.map(function (s) {
      return '<a href="#/' + list + '/' + s.id + '">' + esc(s.short || s.title) + '</a>';
    }).join('') + '</div>';
    secs.forEach(function (s) {
      var d = s.tasks.filter(function (t) { return ticks[t.id]; }).length;
      h += '<section class="sec" id="sec-' + s.id + '"><h2>' + esc(s.title) + '<span class="sec-count">' + d + '/' + s.tasks.length + '</span></h2>';
      if (s.note) h += '<p class="sec-note">' + esc(s.note) + '</p>';
      s.tasks.forEach(function (t) {
        var on = !!ticks[t.id];
        var open = '';
        if (t.link && DISH[t.link.dish]) open = '<a class="open" href="#/task/' + list + '/' + t.id + '/0">Show the steps ›</a>';
        else if (t.goto) open = '<a class="open" href="#/' + t.goto.replace('#', '/') + '">Open the list ›</a>';
        h += '<div class="task' + (on ? ' on' : '') + (t.overnight ? ' overnight' : '') + '" id="task-' + t.id + '">' +
          '<button class="tick" data-act="tick" data-list="' + list + '" data-id="' + t.id + '" aria-pressed="' + on + '" aria-label="Tick">' +
          '<span class="box">' + (on ? '✓' : '') + '</span></button>' +
          '<div class="tbody"><button class="txt" data-act="tick" data-list="' + list + '" data-id="' + t.id + '"><b>' + esc(t.text) + '</b>' +
          (t.sub ? '<span>' + esc(t.sub) + '</span>' : '') + '</button>' + open + '</div></div>';
      });
      h += '</section>';
    });
    h += '<div class="reset-row"><button class="btn warn wide" data-act="reset" data-list="' + list + '">Untick everything for today</button></div>';
    main.innerHTML = h;
    foot.innerHTML = '';
    var target = scrollToTask ? document.getElementById('task-' + scrollToTask) : (secId ? document.getElementById('sec-' + secId) : null);
    scrollToTask = null;
    if (target) setTimeout(function () { target.scrollIntoView({ block: 'center' }); }, 0);
  }

  function screenCook() {
    setBar({ title: 'Cook an order', sub: niceDate() });
    var open = loadOrders().filter(function (o) { return !o.closed; }).reverse();
    var h = '';
    if (open.length) {
      h += '<h2 style="margin-top:4px">Open orders</h2><div class="open-orders">' + open.map(function (o) {
        var n = o.items.length, d = itemsDone(o);
        return '<a class="oo" href="#/order/' + o.id + '"><div><b>' + esc(orderLabel(o)) + '</b><span>' +
          esc((o.title || '') + (o.mode ? ' · ' + o.mode : '') + ' · ' + d + ' of ' + n + ' done') + '</span></div><span class="go">Open ›</span></a>';
      }).join('') + '</div>';
    }
    h += '<h2' + (open.length ? '' : ' style="margin-top:4px"') + '>Paste WhatsApp order</h2>' +
      '<textarea class="paste" id="paste" placeholder="Long-press here and tap Paste.&#10;The whole WhatsApp message, as it came in." autocomplete="off" autocapitalize="off" spellcheck="false">' + esc(draft) + '</textarea>' +
      (lastErr ? '<div class="err">' + esc(lastErr) + '</div>' : '') +
      '<div class="row-btns"><button class="btn" data-act="clip">Paste from phone</button>' +
      '<button class="btn primary" data-act="read">Read order</button></div>';
    h += '<h2>Or pick dishes</h2><p class="muted">Tap a picture to add it. Tap again for more.</p>';
    DATA.brands.forEach(function (b) {
      h += '<div class="brand-h" style="background:' + esc(b.accent) + ';color:' + esc(b.ink) + '">' + esc(b.name) + '</div><div class="grid">';
      b.dishes.forEach(function (k) { h += tileHtml(DISH[k], b.accent); });
      h += '</div>';
    });
    var drinks = Object.keys(DISH).filter(function (k) { return DISH[k].kind === 'drink'; });
    h += '<div class="brand-h" style="background:#fff;color:#000">Drinks</div><div class="grid">' +
      drinks.map(function (k) { return tileHtml(DISH[k], '#ffffff'); }).join('') + '</div>';
    main.innerHTML = h;
    var ta = document.getElementById('paste');
    ta.addEventListener('input', function () { draft = ta.value; });
    drawPickFoot();
  }
  function tileHtml(d, accent) {
    var q = picks[d.key] || 0;
    return '<div class="tile-wrap"><button class="tile' + (q ? ' picked' : '') + '" data-act="pick" data-key="' + esc(d.key) + '">' +
      photo(d.img, d.name, accent, 'tileph') + '<span class="nm">' + esc(d.name) + '</span>' +
      (q ? '<span class="qty">×' + q + '</span>' : '') + '</button>' +
      (q ? '<button class="minus" data-act="unpick" data-key="' + esc(d.key) + '">Take one off</button>' : '') + '</div>';
  }
  function drawPickFoot() {
    var n = Object.keys(picks).reduce(function (s, k) { return s + picks[k]; }, 0);
    foot.innerHTML = n ? '<button class="navbtn" data-act="clearpicks">Clear</button>' +
      '<button class="navbtn done" data-act="cookpicks">Cook (' + n + ') ›</button>' : '';
  }

  function screenOrder(oid) {
    var o = getOrder(oid);
    if (!o) { go('#/cook', true); return; }
    var brands = [];
    o.items.forEach(function (i) { if (!i.drink && i.brand && brands.indexOf(i.brand) < 0) brands.push(i.brand); });
    var accent = brands.length === 1 ? BRAND[brands[0]].accent : null;
    setBar({ title: orderLabel(o), sub: brands.map(function (b) { return BRAND[b].name; }).join(' + ') || o.title, accent: accent,
      side: { label: 'Orders', href: '#/cook' } });
    var done = itemsDone(o), n = o.items.length;
    var h = '<div class="order-wrap"><div>' + orderHead(o) + '</div><div>';
    h += '<p class="progress-line">' + done + ' of ' + n + ' done</p>';
    var groups = brands.map(function (b) { return { id: b, items: [] }; });
    var drinks = [], unknown = [];
    o.items.forEach(function (it, idx) {
      if (it.drink) drinks.push(idx);
      else if (it.unknown) unknown.push(idx);
      else groups.filter(function (g) { return g.id === it.brand; })[0].items.push(idx);
    });
    groups.forEach(function (g) {
      var b = BRAND[g.id];
      h += '<div class="brand-h" style="background:' + esc(b.accent) + ';color:' + esc(b.ink) + '">' + esc(b.name) + '</div>';
      g.items.forEach(function (idx) { h += itemRow(o, idx); });
    });
    if (drinks.length) {
      h += '<div class="brand-h" style="background:#fff;color:#000">Drinks</div>';
      drinks.forEach(function (idx) { h += itemRow(o, idx); });
    }
    if (unknown.length) {
      h += '<div class="brand-h" style="background:' + 'var(--orange)' + ';color:#000">Not sure what this is</div>';
      unknown.forEach(function (idx) { h += itemRow(o, idx); });
    }
    if (o.other && o.other.length) h += '<div class="other-lines"><b>Other lines in the message:</b>\n' + esc(o.other.join('\n')) + '</div>';
    if (receiptModel(o)) h += '<div class="row-btns" style="margin-top:22px"><button class="btn go wide" data-act="receipt" data-id="' + o.id + '">Receipt for the customer</button></div>';
    h += replyBlock(o);
    h += '<div class="row-btns" style="margin-top:26px"><button class="btn warn" data-act="delorder" data-id="' + o.id + '">Delete this order</button></div>';
    h += '</div></div>';
    main.innerHTML = h;
    foot.innerHTML = done === n && n
      ? '<button class="navbtn done" data-act="goready" data-id="' + o.id + '">Order ready ›</button>'
      : '';
  }
  /* Ready-made WhatsApp replies for the customer. Tap one: it is copied and WhatsApp opens to pick the chat. */
  function replyTexts(o) {
    var no = o.no ? 'Order #' + o.no : 'Your order';
    var hi = 'Danki' + (o.name ? ', ' + o.name : '') + '! ';
    var timed = o.time && !/possible|asap/i.test(o.time);
    var pickup = o.mode === 'Pickup';
    var total = o.total ? ' Total \u0192' + o.total + '.' : '';
    return [
      { k: 'Confirm', t: hi + no + (timed ? ' is booked for ' + o.time + '.' : ' is confirmed.') +
          (pickup ? ' We\u2019ll message you when it\u2019s ready for pickup.' : timed ? '' : ' It\u2019s with you in about 35\u201350 min.') + total },
      { k: pickup ? 'Ready for pickup' : 'On the way', t: pickup ? no + ' is ready for pickup. See you soon!' : no + ' is on the way. See you in a few minutes!' },
      { k: 'Sold out', t: 'Sorry, one dish in ' + no.toLowerCase().replace('your order', 'your order') + ' is sold out tonight. Can we swap it for something else?' }
    ];
  }
  function replyBlock(o) {
    return '<h2>Reply to the customer</h2><div class="replies">' + replyTexts(o).map(function (r, i) {
      return '<a class="reply" href="https://wa.me/?text=' + encodeURIComponent(r.t) + '" target="_blank" rel="noopener" data-reply="' + i + '" data-id="' + o.id + '">' +
        '<b>' + esc(r.k) + '</b><span>' + esc(r.t) + '</span></a>';
    }).join('') + '</div>';
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-reply]');
    if (!a) return;
    var o = loadOrders().filter(function (x) { return x.id === a.getAttribute('data-id'); })[0];
    if (!o) return;
    var t = replyTexts(o)[+a.getAttribute('data-reply')].t;
    try { if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t); } catch (err) { /* ignore */ }
    toast('Copied. Pick the customer\u2019s chat in WhatsApp and send.');
  });
  function orderHead(o, noMode) {
    var h = '<div class="ohead">' + (noMode ? '' : '<div class="mode">' + esc(o.mode ? o.mode + (o.area ? ' · ' + o.area : '') : 'Delivery or pickup: not in message') + '</div>');
    if (o.time) h += '<div class="when' + (/possible|asap/i.test(o.time) ? '' : ' when--set') + '">' + (/possible|asap/i.test(o.time) ? 'As soon as possible' : 'Ready for ' + esc(o.time)) + '</div>';
    if (o.preorder) h += '<span class="badge">PRE-ORDER · sent while closed</span>';
    if (o.pay && o.pay !== '-') {   // the website ticket says "Pay: Cash" or "Pay: Bank transfer"
      var bank = /bank|transfer/i.test(o.pay);
      h += '<div class="pay' + (bank ? ' pay--bank' : '') + '">' + (bank ? 'Pays by bank transfer · check it came in'
        : /cash/i.test(o.pay) ? 'Pays cash ' + (o.mode === 'Pickup' ? 'at pickup' : 'to the driver') + (o.total ? ' · \u0192' + esc(o.total) : '') : 'Pays: ' + esc(o.pay)) + '</div>';
    }
    if (o.name) h += '<div class="who">' + esc(o.name) + (o.phone ? ' · ' + esc(o.phone) : '') + '</div>';
    if (o.address) h += '<div class="addr">' + esc(o.address) + '</div>';
    if (o.note) h += '<div class="notebox' + (isAllergyNote(o.note) ? ' allergy' : '') + '"><small>' + (isAllergyNote(o.note) ? 'Allergy / diet note' : 'Customer note') + '</small>' + esc(o.note) + '</div>';
    return h + '</div>';
  }
  function itemRow(o, idx) {
    var it = o.items[idx];
    if (it.drink) {
      var dd = DISH[it.key];
      return '<button class="item drink' + (it.done ? ' done' : '') + '" data-act="drink" data-id="' + o.id + '" data-idx="' + idx + '">' +
        '<span class="box">' + (it.done ? '✓' : '') + '</span>' + photo(dd.img, dd.grab, '#ffffff') +
        '<span class="it"><b>Grab ' + it.qty + ' × ' + esc(dd.grab) + '</b>' + (it.done ? '<span class="part">In the bag</span>' : '') + '</span></button>';
    }
    if (it.unknown) {
      return '<button class="item unknown' + (it.done ? ' done' : '') + '" data-act="drink" data-id="' + o.id + '" data-idx="' + idx + '">' +
        '<span class="box">' + (it.done ? '✓' : '') + '</span><span class="it"><b>' + it.qty + ' × ' + esc(it.name) + '</b>' +
        '<span class="part">Could not match this to a dish. Check the message. Tap to tick.</span>' + modChips(it.mods, []) + '</span></button>';
    }
    var d = DISH[it.key], warn = conflicts(o, d);
    return '<a class="item' + (it.done ? ' done' : '') + '" href="#/order/' + o.id + '/' + idx + '/0">' +
      photo(d.img, d.name, BRAND[d.brand].accent) +
      '<span class="it"><b>' + it.qty + ' × ' + esc(d.name) + '</b>' +
      (it.bundle ? '<span class="part">Part of ' + esc(it.bundle.name) + '</span>' : '') +
      modChips(it.mods, warn) + '</span>' +
      '<span class="go">' + (it.done ? '✓ Done' : 'Cook ›') + '</span></a>';
  }
  function modChips(mods, warn) {
    var c = (mods || []).map(function (m) { return '<span class="chip">' + esc(m) + '</span>'; });
    (warn || []).forEach(function (w) { c.push('<span class="chip warn">Note says ' + esc(w) + '!</span>'); });
    return c.length ? '<span class="chips">' + c.join('') + '</span>' : '';
  }

  function screenOrderCard(oid, idx, c) {
    var o = getOrder(oid);
    if (!o || !o.items[idx] || !DISH[o.items[idx].key]) { go('#/order/' + oid, true); return; }
    var it = o.items[idx], d = DISH[it.key], b = BRAND[d.brand];
    var cards = dishCards(d);
    c = Math.max(0, Math.min(cards.length - 1, c));
    setBar({ title: it.qty + ' × ' + d.name, sub: b.name + ' · ' + orderLabel(o), accent: b.accent, side: { label: 'Order', href: '#/order/' + oid } });
    var banners = '';
    if (it.mods && it.mods.length) banners += '<div class="banner mods">' + esc(it.mods.join(' · ')) + '</div>';
    if (it.bundle) banners += '<div class="banner note"><small>Family Table</small>Part of ' + esc(it.bundle.name) + ' · ' + it.qty + ' tray' + (it.qty > 1 ? 's' : '') + '</div>';
    var warn = conflicts(o, d);
    if (warn.length) banners += '<div class="banner allergy"><small>Warning</small>The note mentions ' + esc(warn.join(', ')) + ' and this dish has it. Read the note.</div>';
    if (o.note) banners += '<div class="banner slim ' + (isAllergyNote(o.note) ? 'allergy' : 'note') + '"><b>' + (isAllergyNote(o.note) ? 'Allergy note:' : 'Note:') + '</b> ' + esc(o.note) + '</div>';
    if (cards[c].t === 'step' && d.steps[cards[c].i].prep) banners += '<div class="banner prep"><small>Prep step</small>Usually done before service. Already done? Tap Next.</div>';
    var ctx = { dish: d, item: it, order: o, cards: cards, c: c, tid: 'o:' + oid + ':' + idx, mode: 'order',
      href: function (k) { return '#/order/' + oid + '/' + idx + '/' + k; } };
    main.innerHTML = banners + progHtml(c, cards.length) + cardBody(ctx);
    sheetCtx = { dish: d };
    var last = c === cards.length - 1;
    foot.innerHTML = '<button class="navbtn" data-act="nav" data-href="' + (c > 0 ? ctx.href(c - 1) : '#/order/' + oid) + '">‹ Back</button>' +
      (last ? '<button class="navbtn done" data-act="itemdone" data-id="' + oid + '" data-idx="' + idx + '">' + (it.done ? 'Done ✓ Back to order' : 'Mark done ✓') + '</button>'
        : '<button class="navbtn next" data-act="nav" data-href="' + ctx.href(c + 1) + '">Next ›</button>');
  }
  function progHtml(c, n) {
    return '<div class="prog"><b>Step ' + (c + 1) + ' of ' + n + '</b><span class="pbar"><i style="width:' + Math.round(((c + 1) / n) * 100) + '%"></i></span></div>';
  }

  function screenTask(list, tid, c) {
    var f = findTask(list, tid);
    if (!f || !f.task.link || !DISH[f.task.link.dish]) { go('#/' + list, true); return; }
    var t = f.task, d = DISH[t.link.dish], b = BRAND[d.brand];
    var cards = taskCards(t);
    c = Math.max(0, Math.min(cards.length - 1, c));
    setBar({ title: t.text, sub: (list === 'prep' ? 'Prep' : 'Close up') + ' · ' + b.name + ' · ' + d.name, accent: b.accent,
      side: { label: 'List', href: '#/' + list + '/' + f.sec.id } });
    var ctx = { dish: d, item: null, order: null, cards: cards, c: c, tid: 't:' + list + ':' + tid, mode: 'task',
      href: function (k) { return '#/task/' + list + '/' + tid + '/' + k; } };
    main.innerHTML = (t.sub ? '<div class="banner note">' + esc(t.sub) + '</div>' : '') + progHtml(c, cards.length) + cardBody(ctx);
    sheetCtx = { dish: d };
    var last = c === cards.length - 1;
    foot.innerHTML = '<button class="navbtn" data-act="nav" data-href="' + (c > 0 ? ctx.href(c - 1) : '#/' + list + '/' + f.sec.id) + '">‹ Back</button>' +
      (last ? '<button class="navbtn done" data-act="taskdone" data-list="' + list + '" data-id="' + tid + '">Done ✓ Tick it</button>'
        : '<button class="navbtn next" data-act="nav" data-href="' + ctx.href(c + 1) + '">Next ›</button>');
  }

  function screenReady(oid) {
    var o = getOrder(oid);
    if (!o) { go('#/cook', true); return; }
    setBar({ title: 'Order ready', sub: orderLabel(o), side: { label: 'Order', href: '#/order/' + oid } });
    var h = '<div class="ready"><div class="big"><b>ORDER READY</b><span>' + esc(o.no ? '#' + o.no : orderLabel(o)) + '</span></div>' +
      '<div class="mode">' + esc(o.mode ? o.mode + (o.area ? ' · ' + o.area : '') : 'Delivery or pickup: check the message') + '</div>' +
      '</div>' + orderHead(o, true) + '<h2>In the bag</h2><ul class="lines small">' +
      o.items.map(function (i) {
        var nm = i.drink ? DISH[i.key].grab : (i.key ? DISH[i.key].name : i.name);
        return '<li>' + i.qty + ' × ' + esc(nm) + (i.bundle ? ' (' + esc(i.bundle.name) + ')' : '') + (i.mods && i.mods.length ? ' · ' + esc(i.mods.join(' · ')) : '') + '</li>';
      }).join('') + '</ul>' +
      (receiptModel(o) ? '<div class="row-btns" style="margin-top:18px"><button class="btn go wide" data-act="receipt" data-id="' + o.id + '">Receipt for the customer</button></div>' : '');
    main.innerHTML = h;
    foot.innerHTML = '<button class="navbtn" data-act="nav" data-href="#/order/' + oid + '">‹ Order</button>' +
      '<button class="navbtn done" data-act="closeorder" data-id="' + oid + '">Close order ✓</button>';
  }

  // ------------------------------------------------------------------ customer receipt
  /* Built from the WhatsApp order's own lines and prices, so it says exactly what the customer ordered and paid.
     Business details come from shared/site.json (name, WhatsApp, and an optional "receipt" block with
     legalName / kvk / address, shown only when filled in). */
  var SITE = {};
  function money(c) { return '\u0192' + (c / 100).toFixed(2); }
  function phoneText(n) { n = String(n || ''); return /^297\d{7}$/.test(n) ? '+297 ' + n.slice(3, 6) + ' ' + n.slice(6) : '+' + n; }
  function receiptModel(o) {
    var lines = o.lines || [];
    // every line needs its price, or a dish would silently be missing from the receipt
    if (!lines.length || lines.some(function (l) { return l.price == null; })) return null;
    var brands = [];
    lines.forEach(function (l) { var b = l.brandId && BRAND[l.brandId]; if (b && !/drink/i.test(l.raw) && brands.indexOf(b.name) < 0) brands.push(b.name); });
    var sub = o.subtotalC != null ? o.subtotalC : lines.reduce(function (t, l) { return t + l.price; }, 0);
    var fee = o.feeC != null ? o.feeC : 0;
    return { no: o.no || '', when: o.created, brands: brands, mode: o.mode ? o.mode + (o.mode === 'Delivery' && o.area ? ' \u00b7 ' + o.area.replace(/\s*\(please confirm\)/i, '') : '') : '',
      name: o.name || '', lines: lines.map(function (l) { return { q: l.qty, n: l.raw, p: l.price, d: (l.includes || []).concat(l.mods || []) }; }),
      sub: sub, fee: fee, feeLabel: o.mode === 'Pickup' ? 'Pickup' : 'Delivery', total: o.totalC != null ? o.totalC : sub + fee,
      pay: o.pay && o.pay !== '-' ? o.pay : '' };
  }
  function receiptDate(ts) {
    var d = new Date(ts);
    try { return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) + ' \u00b7 ' + clock(ts); } catch (e) { return today() + ' ' + clock(ts); }
  }
  function receiptText(r) {
    var biz = SITE.name || 'Order Aruba', out = ['*' + biz + ' \u00b7 Receipt*'];
    if (r.brands.length) out.push(r.brands.join(' \u00b7 '));
    out.push((r.no ? 'Order #' + r.no + ' \u00b7 ' : '') + receiptDate(r.when));
    if (r.mode) out.push(r.mode);
    out.push('');
    r.lines.forEach(function (l) { out.push(l.q + ' \u00d7 ' + l.n + '  ' + money(l.p)); if (l.d.length) out.push('   ' + l.d.join(' \u00b7 ')); });
    out.push('', 'Subtotal ' + money(r.sub), r.feeLabel + ' ' + money(r.fee), '*Total ' + money(r.total) + '*');
    if (r.pay) out.push('Payment: ' + r.pay);
    out.push('', 'Danki! ' + biz + (SITE.whatsapp ? ' \u00b7 WhatsApp ' + phoneText(SITE.whatsapp) : ''));
    return out.join('\n');
  }
  /* Draws the receipt on a canvas: a paper slip, 600px wide at 2x. Long dish names wrap. */
  function receiptCanvas(r) {
    var W = 600, P = 34, S = 2, cv = document.createElement('canvas'), ctx = cv.getContext('2d');
    var F = '"Archivo", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
    var INK = '#14171C', GREY = '#6B6558', PAPER = '#FFFDF5', biz = SITE.name || 'Order Aruba', R = SITE.receipt || {};
    function font(w, px) { ctx.font = w + ' ' + px + 'px ' + F; }
    function wrap(text, w, px, max) {
      font(w, px); var words = String(text).split(' '), rows = [], cur = '';
      words.forEach(function (x) { var t = cur ? cur + ' ' + x : x; if (ctx.measureText(t).width > max && cur) { rows.push(cur); cur = x; } else cur = t; });
      if (cur) rows.push(cur); return rows;
    }
    var ops = [], y = P;
    function text(t, w, px, color, align, gap) { ops.push({ k: 't', t: t, w: w, px: px, c: color || INK, a: align || 'left', y: y + px }); y += px + (gap == null ? 8 : gap); }
    function rule() { y += 6; ops.push({ k: 'r', y: y }); y += 16; }
    function pair(l, r, w, px, color) { ops.push({ k: 'p', l: l, r: r, w: w, px: px, c: color || INK, y: y + px }); y += px + 8; }
    text(biz.toUpperCase(), '900', 34, INK, 'left', 6);
    if (r.brands.length) wrap(r.brands.join(' \u00b7 '), '600', 17, W - 2 * P).forEach(function (row) { text(row, '600', 17, GREY, 'left', 4); });
    [R.legalName, R.address, R.kvk ? 'KvK ' + R.kvk : ''].filter(Boolean).forEach(function (t) { text(t, '500', 15, GREY, 'left', 3); });
    y += 10;
    text('RECEIPT' + (r.no ? '  #' + r.no : ''), '800', 22, INK, 'left', 4);
    text(receiptDate(r.when) + (r.mode ? '  \u00b7  ' + r.mode : ''), '500', 17, GREY);
    rule();
    r.lines.forEach(function (l) {
      var rows = wrap(l.q + ' \u00d7 ' + l.n, '700', 20, W - 2 * P - 120);
      rows.forEach(function (row, i) { if (i === 0) pair(row, money(l.p), '700', 20); else text(row, '700', 20); });
      if (l.d.length) wrap(l.d.join(' \u00b7 '), '500', 16, W - 2 * P - 140).forEach(function (row) { text('   ' + row, '500', 16, GREY, 'left', 4); });
      y += 4;
    });
    rule();
    pair('Subtotal', money(r.sub), '500', 18, GREY);
    pair(r.feeLabel, money(r.fee), '500', 18, GREY);
    y += 4; pair('TOTAL', money(r.total), '900', 30);
    if (r.pay) text('Payment: ' + r.pay, '700', 18);
    rule();
    text('Danki!  Bon apetit.', '800', 20, INK, 'center', 6);
    if (SITE.whatsapp) text('WhatsApp ' + phoneText(SITE.whatsapp), '500', 16, GREY, 'center');
    y += P - 8;
    cv.width = W * S; cv.height = Math.ceil(y) * S;
    ctx.scale(S, S); ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, y);
    ctx.textBaseline = 'alphabetic';
    ops.forEach(function (op) {
      if (op.k === 'r') { ctx.strokeStyle = '#C9C2B2'; ctx.lineWidth = 2; ctx.setLineDash([7, 6]); ctx.beginPath(); ctx.moveTo(P, op.y); ctx.lineTo(W - P, op.y); ctx.stroke(); ctx.setLineDash([]); return; }
      font(op.w, op.px); ctx.fillStyle = op.c;
      if (op.k === 'p') { ctx.textAlign = 'left'; ctx.fillText(op.l, P, op.y); ctx.textAlign = 'right'; ctx.fillText(op.r, W - P, op.y); return; }
      ctx.textAlign = op.a; ctx.fillText(op.t, op.a === 'center' ? W / 2 : P, op.y);
    });
    return cv;
  }
  var receiptFile = null;
  function openReceipt(o) {
    var r = receiptModel(o);
    if (!r) { toast('Some dishes have no price in this order, so no receipt. Paste the full WhatsApp order from the website.', 4500); return; }
    var txt = receiptText(r);
    var ready = document.fonts && document.fonts.load ? document.fonts.load('900 34px "Archivo"').catch(function () {}) : Promise.resolve();
    ready.then(function () {
      var cv = receiptCanvas(r), url = cv.toDataURL('image/png');
      receiptFile = null;
      cv.toBlob(function (b) { if (b && window.File) receiptFile = new File([b], 'receipt-' + (r.no || clock(r.when).replace(':', '')) + '.png', { type: 'image/png' }); }, 'image/png');
      openSheet('<h2>Receipt for the customer</h2>' +
        '<img class="rcpt" src="' + url + '" alt="Receipt">' +
        '<div class="row-btns"><button class="btn go wide" data-act="rshare">Send picture on WhatsApp</button></div>' +
        '<div class="row-btns"><a class="btn" href="https://wa.me/?text=' + encodeURIComponent(txt) + '" target="_blank" rel="noopener">Send as text</a>' +
        '<a class="btn" href="' + url + '" download="receipt-' + esc(r.no || 'order') + '.png">Save picture</a></div>' +
        '<p class="hint">Tap Send, pick WhatsApp, then pick the customer\u2019s chat.</p>');
    });
  }

  // ------------------------------------------------------------------ sheet
  function openSheet(html) {
    sheet.innerHTML = '<div class="panel">' + html + '<div class="row-btns"><button class="btn primary wide" data-act="closesheet">Close</button></div></div>';
    sheet.hidden = false;
  }
  function closeSheet() { sheet.hidden = true; sheet.innerHTML = ''; }
  sheet.addEventListener('click', function (e) { if (e.target === sheet) closeSheet(); });

  // ------------------------------------------------------------------ router
  var lastRoute = '';
  function render(keepScroll) {
    if (!DATA) return;
    var r = (location.hash || '#/').replace(/^#\/?/, '').split('/').map(decodeURIComponent);
    var route = r.join('/');
    var y = main.scrollTop;
    closeSheet();
    if (keepScroll !== true && Date.now() - toastAt > 500) toastEl.hidden = true;
    if (!r[0]) screenHome();
    else if (r[0] === 'prep' || r[0] === 'close') screenList(r[0], r[1]);
    else if (r[0] === 'cook') screenCook();
    else if (r[0] === 'order' && r.length >= 4) screenOrderCard(r[1], +r[2], +r[3]);
    else if (r[0] === 'order') screenOrder(r[1]);
    else if (r[0] === 'task') screenTask(r[1], r[2], +r[3] || 0);
    else if (r[0] === 'ready') screenReady(r[1]);
    else screenHome();
    if (keepScroll === true && route === lastRoute) main.scrollTop = y;
    else if (!/^(prep|close)/.test(route)) main.scrollTop = 0;
    lastRoute = route;
    drawTray(true);
  }
  window.addEventListener('hashchange', function () { render(); });

  // ------------------------------------------------------------------ actions
  var ACT = {
    receipt: function (el) { var o = getOrder(el.getAttribute('data-id')); if (o) openReceipt(o); },
    rshare: function () {
      var f = receiptFile;
      if (f && navigator.canShare && navigator.canShare({ files: [f] })) {
        navigator.share({ files: [f] }).catch(function () { /* closed the share menu */ });
      } else toast('This phone can\u2019t share a picture from here. Use \u201cSend as text\u201d or \u201cSave picture\u201d.', 4000);
    },
    tick: function (el) {
      var list = el.getAttribute('data-list'), id = el.getAttribute('data-id');
      var on = !getTicks(list)[id];
      setTick(list, id, on);
      render(true);
    },
    reset: function (el) {
      var list = el.getAttribute('data-list');
      openSheet('<h2>Untick everything on the ' + (list === 'prep' ? 'Prep' : 'Close up') + ' list for today?</h2>' +
        '<div class="row-btns"><button class="btn warn wide" data-act="resetyes" data-list="' + list + '">Yes, untick all</button></div>');
    },
    resetyes: function (el) {
      store.del(ticksKey(el.getAttribute('data-list'), today()));
      closeSheet(); render();
    },
    pick: function (el) {
      var k = el.getAttribute('data-key');
      picks[k] = (picks[k] || 0) + 1;
      el.parentNode.outerHTML = tileHtml(DISH[k], tileAccent(k));
      drawPickFoot();
    },
    unpick: function (el) {
      var k = el.getAttribute('data-key');
      picks[k] = Math.max(0, (picks[k] || 0) - 1);
      if (!picks[k]) delete picks[k];
      el.parentNode.outerHTML = tileHtml(DISH[k], tileAccent(k));
      drawPickFoot();
    },
    clearpicks: function () { picks = {}; render(true); },
    cookpicks: function () {
      var lines = [];
      Object.keys(picks).forEach(function (k) { lines.push({ qty: picks[k], raw: DISH[k].name, brandId: DISH[k].brand, key: k, mods: [], includes: null }); });
      if (!lines.length) return;
      var o = { id: 'o' + uid(), no: '', title: 'Picked dishes', manual: true, mode: '', area: '', preorder: false, name: '', address: '',
        note: '', phone: '', other: [], created: Date.now(), closed: false, items: expandLines(lines) };
      putOrder(o);
      picks = {};
      go('#/order/' + o.id);
    },
    clip: function () {
      var ta = document.getElementById('paste');
      if (navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(function (t) {
          if (t) { draft = t; ta.value = t; lastErr = ''; ACT.read(); }
          else { ta.focus(); toast('Nothing copied yet. Copy the WhatsApp message first.'); }
        }).catch(function () { ta.focus(); toast('Long-press in the box and tap Paste.'); });
      } else { ta.focus(); toast('Long-press in the box and tap Paste.'); }
    },
    read: function () {
      var ta = document.getElementById('paste');
      var text = ta ? ta.value : draft;
      draft = text;
      if (!text.trim()) { lastErr = 'The box is empty. Paste the WhatsApp order first.'; render(true); return; }
      var o = parseOrder(text);
      if (!o.items.length) { lastErr = 'No dishes found in that message. Check it is the whole order (lines like "2 × Chicken fried rice").'; render(true); return; }
      if (o.no) {
        var dup = loadOrders().filter(function (x) { return !x.closed && x.no === o.no; })[0];
        if (dup) { lastErr = ''; draft = ''; toast('Order #' + o.no + ' is already open.'); go('#/order/' + dup.id); return; }
      }
      putOrder(o);
      lastErr = ''; draft = '';
      var miss = o.items.filter(function (i) { return i.unknown; }).length;
      if (miss) toast(miss + ' line' + (miss > 1 ? 's' : '') + ' not matched. Check the orange box.', 5000);
      go('#/order/' + o.id);
    },
    drink: function (el) {
      var o = getOrder(el.getAttribute('data-id')), idx = +el.getAttribute('data-idx');
      if (!o) return;
      o.items[idx].done = !o.items[idx].done;
      putOrder(o);
      if (o.items[idx].done && itemsDone(o) === o.items.length) { go('#/ready/' + o.id); return; }
      render(true);
    },
    itemdone: function (el) {
      var o = getOrder(el.getAttribute('data-id')), idx = +el.getAttribute('data-idx');
      if (!o) return;
      o.items[idx].done = true;
      putOrder(o);
      if (itemsDone(o) === o.items.length) go('#/ready/' + o.id, true);
      else { toast('Done: ' + o.items[idx].qty + ' × ' + o.items[idx].name); go('#/order/' + o.id, true); }
    },
    goready: function (el) { go('#/ready/' + el.getAttribute('data-id')); },
    closeorder: function (el) {
      var o = getOrder(el.getAttribute('data-id'));
      if (!o) return;
      o.closed = true; o.closedAt = Date.now();
      putOrder(o);
      toast(orderLabel(o) + ' closed.');
      go('#/cook');
    },
    delorder: function (el) {
      var id = el.getAttribute('data-id'), o = getOrder(id);
      openSheet('<h2>Delete ' + esc(o ? orderLabel(o) : 'this order') + '?</h2><p>It disappears from this screen. The WhatsApp message is not touched.</p>' +
        '<div class="row-btns"><button class="btn warn wide" data-act="delyes" data-id="' + esc(id) + '">Yes, delete it</button></div>');
    },
    delyes: function (el) {
      var id = el.getAttribute('data-id');
      saveOrders(loadOrders().filter(function (o) { return o.id !== id; }));
      closeSheet(); go('#/cook');
    },
    taskdone: function (el) {
      var list = el.getAttribute('data-list'), id = el.getAttribute('data-id');
      setTick(list, id, true);
      var f = findTask(list, id);
      scrollToTask = id;
      go('#/' + list + '/' + (f ? f.sec.id : ''));
    },
    nav: function (el) { go(el.getAttribute('data-href'), true); },
    timer: function (el) {
      startTimer({ id: el.getAttribute('data-tid'), sec: +el.getAttribute('data-sec'), label: el.getAttribute('data-label'),
        title: el.getAttribute('data-title'), href: el.getAttribute('data-href') });
      toast('Timer started: ' + fmtDur(+el.getAttribute('data-sec')) + ' · ' + el.getAttribute('data-label'), 2200);
      render(true);
    },
    tray: function (el) {
      var id = el.getAttribute('data-id'), t = TIMERS.filter(function (x) { return x.id === id; })[0];
      if (!t) { render(true); return; }
      if (t.fired) { stopTimer(id); render(true); return; }
      openSheet('<h2>' + esc(t.label) + ' · ' + esc(t.title) + '</h2>' +
        '<p class="card-title" style="font-size:44px"><span data-left="' + esc(t.id) + '">' + fmtLeft(t.ends - Date.now()) + '</span> left</p>' +
        '<div class="row-btns"><button class="btn" data-act="plus" data-id="' + esc(id) + '">+1 min</button>' +
        (t.href ? '<button class="btn primary" data-act="nav" data-href="' + esc(t.href) + '">Go to the step</button>' : '') + '</div>' +
        '<div class="row-btns"><button class="btn warn wide" data-act="stoptimer" data-id="' + esc(id) + '">Stop this timer</button></div>');
    },
    plus: function (el) {
      var t = TIMERS.filter(function (x) { return x.id === el.getAttribute('data-id'); })[0];
      if (t) { t.ends += 60000; saveTimers(); drawTray(true); }
    },
    stoptimer: function (el) { stopTimer(el.getAttribute('data-id')); closeSheet(); render(true); },
    closesheet: function () { closeSheet(); },
    fixes: function () {
      var d = sheetCtx && sheetCtx.dish;
      if (!d) return;
      openSheet('<h2>Problem? · ' + esc(d.name) + '</h2><div class="stack">' + fixesHtml(d.fixes) + '</div>');
    },
    ingredients: function () {
      var d = sheetCtx && sheetCtx.dish;
      if (!d) return;
      openSheet('<h2>' + esc(d.name) + '</h2><p class="muted">Batch of 10 portions</p>' + linesHtml(d.ingredients, [], 'small'));
    }
  };
  function tileAccent(k) { var d = DISH[k]; return d.brand ? BRAND[d.brand].accent : '#ffffff'; }
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-act]') : null;
    if (!el) return;
    var fn = ACT[el.getAttribute('data-act')];
    if (!fn) return;
    e.preventDefault();
    fn(el, e);
  });
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') { wakeLock = null; keepAwake(); tick(); }
  });

  // ------------------------------------------------------------------ start
  function boot(data) {
    DATA = data;
    DATA.brands.forEach(function (b) { BRAND[b.id] = b; });
    DISH = DATA.dishes;
    buildIndex();
    render();
    setInterval(tick, 500);
    tick();
    keepAwake();
    warmCache();
  }
  function warmCache() {
    if (!navigator.serviceWorker || !navigator.serviceWorker.controller) return;
    var urls = [];
    Object.keys(DISH).forEach(function (k) { if (DISH[k].img) urls.push(new URL(DISH[k].img, location.href).href); });
    navigator.serviceWorker.controller.postMessage({ type: 'warm', urls: urls });
  }
  fetch('../../shared/site.json', { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : {}; }).then(function (s) { SITE = s || {}; }, function () {});
  fetch('kitchen-data.json', { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(boot)
    .catch(function () {
      main.innerHTML = '<p class="loading">Could not load the kitchen data. Check the connection once, then it works offline.</p>' +
        '<button class="btn primary" onclick="location.reload()">Try again</button>';
    });
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').then(function () {
        navigator.serviceWorker.ready.then(function () { setTimeout(warmCache, 1500); });
      }).catch(function () { /* offline cache not available - app still works */ });
    });
  }

  // test hook (read-only helpers)
  window.__kitchen = {
    parse: function (t) { return parseOrder(t); },
    receipt: function (o) { return receiptModel(o); },
    receiptText: function (o) { var r = receiptModel(o); return r ? receiptText(r) : null; },
    timers: function () { return TIMERS; },
    expire: function () { TIMERS.forEach(function (t) { t.ends = Date.now() - 1; }); saveTimers(); tick(); }
  };
})();
