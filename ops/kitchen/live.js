/* Orders from the Pidi app, live in the kitchen.
   Sign in once with the kitchen PIN (Victor sets it on /driver/admin/). New orders then come in by
   themselves: the phone beeps and shows a bar on every screen. One big button per step:
   Accept, Start cooking, then "… is ready" per restaurant. When every bag is ready, the order is
   offered to the drivers by itself. The database decides what is allowed; this screen only asks. */
(function () {
  'use strict';
  var UI = window.__kitchenUI, P = window.Pidi;
  if (!UI || !P) return;
  var esc = UI.esc, main = UI.main, foot = UI.foot;
  var KEY = 'pidi.kitchen.session';      // { token, expires_at, topic } on this phone only
  var SEEN = 'pidi.kitchen.seen.v1';     // order ids this phone has already beeped for
  var POLL = 8000;

  var feed = null, lastAt = 0, lastErr = '', busy = {}, pinErr = '', stopListen = null, watching = 0;
  var menuPrice = null;                  // dish name -> menu price in cents, to catch a wrong price

  // ------------------------------------------------------------ session
  function session() {
    var s = UI.store.get(KEY, null);
    if (!s || !s.token) return null;
    if (s.expires_at && Date.parse(s.expires_at) < Date.now()) { UI.store.set(KEY, null); return null; }
    return s;
  }
  function signOut(msg) {
    UI.store.set(KEY, null);
    feed = null; pinErr = msg || '';
    if (stopListen) { stopListen(); stopListen = null; }
  }
  function onScreen() { return /^#\/live/.test(location.hash); }

  // ------------------------------------------------------------ sound and screen
  var audio = null;
  function unlockSound() {
    try {
      if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === 'suspended') audio.resume();
    } catch (e) { audio = null; }
  }
  document.addEventListener('click', unlockSound, { capture: true, passive: true });
  function beep() {
    try {
      if (!audio) return;
      [0, 0.22, 0.44].forEach(function (t, i) {
        var o = audio.createOscillator(), g = audio.createGain();
        o.frequency.value = i === 1 ? 660 : 880;
        g.gain.setValueAtTime(0.0001, audio.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.5, audio.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + t + 0.18);
        o.connect(g); g.connect(audio.destination);
        o.start(audio.currentTime + t); o.stop(audio.currentTime + t + 0.2);
      });
    } catch (e) { /* no sound on this phone */ }
    try { if (navigator.vibrate) navigator.vibrate([200, 100, 200]); } catch (e) { /* no vibrate */ }
  }
  var lock = null;
  function keepAwake(on) {
    try {
      if (on && !lock && navigator.wakeLock) navigator.wakeLock.request('screen').then(function (l) { lock = l; l.addEventListener('release', function () { lock = null; }); }, function () {});
      if (!on && lock) { lock.release(); lock = null; }
    } catch (e) { /* not supported */ }
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden && onScreen()) keepAwake(true); });

  // ------------------------------------------------------------ menu prices (a wrong price shows a warning)
  function loadPrices() {
    if (menuPrice) return;
    menuPrice = {};
    fetch('../../shared/site.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (site) {
      (site.brands || []).forEach(function (b) {
        fetch('../../' + b.id + '/menu.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (m) {
          (m.items || []).forEach(function (i) { menuPrice[b.id + '|' + i.name.toLowerCase()] = i.price; });
        }, function () {});
      });
    }, function () {});
  }
  function baseName(n) { return String(n || '').split(' · ')[0].trim(); }
  function priceWarnings(order) {
    var out = [];
    (order.restaurants || []).forEach(function (g) {
      (g.items || []).forEach(function (i) {
        var want = menuPrice && menuPrice[g.slug + '|' + baseName(i.name).toLowerCase()];
        if (want && i.price_cents < want) out.push(baseName(i.name) + ' came in at ' + P.money(i.price_cents) + ', the menu says ' + P.money(want) + '.');
      });
    });
    return out;
  }

  // ------------------------------------------------------------ the feed
  function seen() { return UI.store.get(SEEN, {}) || {}; }
  function markSeen(ids) {
    var s = seen(), now = Date.now();
    ids.forEach(function (id) { s[id] = now; });
    Object.keys(s).forEach(function (id) { if (now - s[id] > 2 * 86400000) delete s[id]; });
    UI.store.set(SEEN, s);
  }
  function refresh() {
    var s = session();
    if (!s) return Promise.resolve(null);
    return P.rpc('pidi_kitchen_feed', { session: s.token }).then(function (f) {
      feed = f || { orders: [] }; lastAt = Date.now(); lastErr = '';
      var fresh = (feed.orders || []).filter(function (o) { return o.status === 'new' && !seen()[o.id]; });
      if (fresh.length) {
        markSeen(fresh.map(function (o) { return o.id; }));
        beep();
        if (!onScreen()) {
          UI.toast('New order: ' + fresh[0].name + (fresh[0].area ? ' · ' + fresh[0].area : '') + '. Tap Orders.', 8000);
        }
      }
      if (!stopListen && feed.topic) stopListen = P.listen(feed.topic, function () { refresh(); });
      paintCount();
      if (onScreen()) draw();
      return feed;
    }, function (err) {
      if (/sign in again/i.test(err.message)) { signOut('Sign in again with the kitchen PIN.'); if (onScreen()) draw(); return null; }
      lastErr = err.message;
      if (onScreen()) draw();
      return null;
    });
  }
  // Runs on every screen while the app is open, so an order is never missed on the Prep screen.
  function watch() {
    if (watching) return;
    watching = setInterval(function () { if (!document.hidden && session()) refresh(); }, POLL);
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden && session()) refresh(); });

  // ------------------------------------------------------------ actions
  function act(id, name, args, okMsg) {
    var s = session();
    if (!s || busy[id]) return;
    busy[id] = true; draw();
    args.session = s.token;
    P.rpc(name, args).then(function () {
      busy[id] = false;
      if (okMsg) UI.toast(okMsg);
      return refresh();
    }, function (err) {
      busy[id] = false;
      if (/sign in again/i.test(err.message)) signOut('Sign in again with the kitchen PIN.');
      UI.toast(err.message, 6000);
      draw();
    });
  }
  function findOrder(id) { return ((feed && feed.orders) || []).filter(function (o) { return o.id === id; })[0] || null; }

  // A live order becomes a cook-along order on this phone (step by step, with timers and photos).
  function cookAlong(order) {
    var open = UI.loadOrders().filter(function (o) { return o.live === order.id && !o.closed; })[0];
    if (open) { UI.go('#/order/' + open.id); return; }
    var lines = ['*Order* · ' + order.name];
    (order.restaurants || []).forEach(function (g) {
      lines.push('*' + g.restaurant + '*');
      (g.items || []).forEach(function (i) {
        var parts = String(i.name).split(' · ');
        lines.push(i.qty + ' × ' + parts[0]);
        if (parts.length > 1) lines.push('   ' + parts.slice(1).join(' · '));
      });
    });
    lines.push('Delivery · ' + (order.area || ''));
    lines.push('Name: ' + order.name);
    if (order.note) lines.push('Note: ' + order.note);
    lines.push('Pay: ' + (order.pay === 'cash' ? 'Cash' : 'Bank transfer'));
    lines.push('Total ' + P.money(order.total_cents));
    var o = UI.parseOrder(lines.join('\n'));
    o.live = order.id;
    o.no = '';
    UI.putOrder(o);
    UI.go('#/order/' + o.id);
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-live]');
    if (!b) return;
    e.preventDefault();
    var what = b.getAttribute('data-live'), id = b.getAttribute('data-id'), o = findOrder(id);
    if (what === 'signin') return signIn();
    if (what === 'signout') { signOut(''); draw(); return; }
    if (what === 'retry') { refresh(); return; }
    if (!o) return;
    if (what === 'accept') act(id, 'pidi_kitchen_accept', { order_id: id }, 'Accepted. The customer sees Received.');
    else if (what === 'cooking') act(id, 'pidi_kitchen_set_status', { order_id: id, status: 'cooking' }, 'Cooking. The customer sees it.');
    else if (what === 'ready') act(id, 'pidi_kitchen_mark_ready', { order_id: id, restaurant: b.getAttribute('data-slug') });
    else if (what === 'paid') act(id, 'pidi_kitchen_transfer_paid', { order_id: id }, 'Marked: the transfer came in.');
    else if (what === 'cook') cookAlong(o);
    else if (what === 'cancel') {
      UI.openSheet('<h2>Can’t do this order?</h2><p>' + esc(o.name) + ' sees “Cancelled” on their phone. Call or message them to say sorry.</p>' +
        '<div class="row-btns"><button class="btn warn wide" data-live="cancel-yes" data-id="' + esc(id) + '">Yes, cancel the order</button></div>');
    } else if (what === 'cancel-yes') { UI.closeSheet(); act(id, 'pidi_kitchen_cancel', { order_id: id }, 'Cancelled.'); }
  });

  function signIn() {
    var input = document.getElementById('lv-pin');
    var pin = input ? input.value.replace(/\D/g, '') : '';
    if (pin.length < 4) { pinErr = 'Type the kitchen PIN (4 to 8 numbers).'; draw(); return; }
    busy.signin = true; pinErr = ''; draw();
    P.rpc('pidi_kitchen_login', { pin: pin }).then(function (r) {
      busy.signin = false;
      if (!r || r.ok === false || !r.token) { pinErr = (r && r.error) || 'That PIN does not match.'; draw(); return; }
      UI.store.set(KEY, { token: r.token, expires_at: r.expires_at, topic: r.topic });
      // orders already waiting do not beep again after signing in on a second phone
      refresh().then(function () { watch(); });
    }, function (err) { busy.signin = false; pinErr = err.message; draw(); });
  }

  // ------------------------------------------------------------ drawing
  var STEP = { new: 0, accepted: 1, cooking: 2, ready: 3, assigned: 4, picked_up: 4 };
  function ago(ts) {
    var m = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 60000));
    return m < 1 ? 'just now' : m === 1 ? '1 min ago' : m + ' min ago';
  }
  function money(c) { return '<span class="fl">' + esc(P.money(c)) + '</span>'; }
  function phoneLink(p) {
    var d = String(p || '').replace(/\D/g, '');
    if (d.length === 7) d = '297' + d;
    return d ? '<a class="lv-call" href="tel:+' + d + '">Call</a><a class="lv-call" href="https://wa.me/' + d + '" target="_blank" rel="noopener">WhatsApp</a>' : '';
  }
  function card(o) {
    var b = !!busy[o.id], step = STEP[o.status];
    var single = (o.restaurants || []).length === 1;
    var h = '<article class="lv-card lv-' + esc(o.status) + '">';
    h += '<div class="ohead">';
    if (o.test) h += '<span class="badge">TEST</span>';
    h += '<div class="mode">' + esc(o.area || 'Delivery') + '</div>';
    h += '<div class="lv-when">' + ago(o.created_at) + '</div>';
    h += o.pay === 'cash'
      ? '<div class="pay">Pays cash ' + money(o.pays_with_cents) + (o.change_due_cents > 0 ? ' · bring ' + money(o.change_due_cents) + ' change' : ' · no change needed') + '</div>'
      : '<div class="pay pay--bank">' + (o.transfer_status === 'paid' ? 'Bank transfer · came in' : 'Bank transfer · not in yet') + '</div>';
    h += '<div class="who">' + esc(o.name) + ' <span class="lv-phone">' + esc(o.phone || '') + '</span></div>';
    h += '<div class="addr">' + esc(o.address || '') + '</div>';
    h += '<div class="lv-contact">' + phoneLink(o.phone) + '</div>';
    if (o.note) h += '<div class="notebox"><small>Customer note</small>' + esc(o.note) + '</div>';
    h += '</div>';
    priceWarnings(o).forEach(function (w) { h += '<div class="banner allergy">Check the price: ' + esc(w) + '</div>'; });
    (o.restaurants || []).forEach(function (g) {
      var br = UI.brand(g.slug) || {};
      h += '<div class="brand-h lv-brand" style="background:' + esc(br.accent || '#26406A') + ';color:' + esc(br.ink || '#fff') + '">' +
        '<span>' + esc(g.restaurant) + '</span>' + (g.ready ? '<span class="lv-tick">Ready</span>' : '') + '</div>';
      h += '<ul class="lv-items">' + (g.items || []).map(function (i) {
        var parts = String(i.name).split(' · ');
        return '<li><b>' + esc(i.qty) + ' ×</b> <span>' + esc(parts[0]) + (parts.length > 1 ? '<em>' + esc(parts.slice(1).join(' · ')) + '</em>' : '') + '</span></li>';
      }).join('') + '</ul>';
      if (o.status === 'cooking' && !g.ready) {
        h += '<button class="btn go wide lv-big" data-live="ready" data-id="' + esc(o.id) + '" data-slug="' + esc(g.slug) + '"' + (b ? ' disabled' : '') + '>' +
          (single ? 'Food is ready' : esc(g.restaurant) + ' is ready') + '</button>';
      }
    });
    h += '<div class="lv-total">Food ' + money(o.food_cents) + ' · Delivery ' + money(o.fee_cents) + ' · <b>Total ' + money(o.total_cents) + '</b></div>';
    if (o.status === 'new') {
      h += '<button class="btn primary wide lv-big" data-live="accept" data-id="' + esc(o.id) + '"' + (b ? ' disabled' : '') + '>Accept</button>';
    } else if (o.status === 'accepted') {
      h += '<button class="btn primary wide lv-big" data-live="cooking" data-id="' + esc(o.id) + '"' + (b ? ' disabled' : '') + '>Start cooking</button>';
    } else if (o.status === 'ready') {
      h += '<div class="lv-wait">Ready. Waiting for a driver to take it.</div>';
    } else if (step === 4) {
      h += '<div class="lv-wait">' + (o.status === 'picked_up' ? 'The driver has it.' : 'A driver took it and is coming for the bags.') + '</div>';
    }
    if (step === 1 || step === 2) h += '<button class="btn wide" data-live="cook" data-id="' + esc(o.id) + '">Cook step by step</button>';
    var small = '';
    if (o.pay === 'transfer' && o.transfer_status !== 'paid') small += '<button class="btn small" data-live="paid" data-id="' + esc(o.id) + '">The transfer came in</button>';
    if (step <= 3) small += '<button class="btn small warn" data-live="cancel" data-id="' + esc(o.id) + '">Can’t do this order</button>';
    if (small) h += '<div class="row-btns lv-small">' + small + '</div>';
    return h + '</article>';
  }
  function draw() {
    if (!onScreen()) return;
    var s = session();
    if (!s) {
      UI.setBar({ title: 'Orders', sub: 'Sign in once on this phone' });
      main.innerHTML = '<div class="lv-pin"><h1>Kitchen PIN</h1>' +
        '<p class="muted">Ask Victor for it. You stay signed in on this phone for 12 hours.</p>' +
        '<input id="lv-pin" type="password" inputmode="numeric" pattern="[0-9]*" autocomplete="off" maxlength="8" placeholder="PIN" aria-label="Kitchen PIN">' +
        (pinErr ? '<div class="banner allergy">' + esc(pinErr) + '</div>' : '') +
        '<button class="btn primary wide lv-big" data-live="signin"' + (busy.signin ? ' disabled' : '') + '>' + (busy.signin ? 'Checking…' : 'Open orders') + '</button></div>';
      foot.innerHTML = '';
      var pinBox = document.getElementById('lv-pin');
      if (pinBox) pinBox.addEventListener('keydown', function (e) { if (e.key === 'Enter') signIn(); });
      return;
    }
    keepAwake(true);
    var orders = ((feed && feed.orders) || []).slice().sort(function (a, b) {
      return (STEP[a.status] - STEP[b.status]) || (Date.parse(a.created_at) - Date.parse(b.created_at));
    });
    UI.setBar({ title: 'Orders', sub: lastAt ? 'Live · checked ' + UI.clock(lastAt) : 'Loading…' });
    var h = '';
    if (lastErr) h += '<div class="banner allergy">' + esc(lastErr) + ' <button class="btn small" data-live="retry">Try again</button></div>';
    if (!feed) h += '<p class="loading">Loading orders…</p>';
    else if (!orders.length) h += '<div class="lv-empty"><b>No orders right now.</b><span>Keep this screen open. New orders beep and show up here by themselves.</span></div>';
    else h += orders.map(card).join('');
    h += '<div class="row-btns lv-out"><button class="btn small" data-live="signout">Sign out on this phone</button></div>';
    main.innerHTML = h;
    foot.innerHTML = '';
  }
  function paintCount() {
    var el = document.getElementById('liveCount');
    if (!el) return;
    var n = ((feed && feed.orders) || []).filter(function (o) { return o.status === 'new'; }).length;
    var open = ((feed && feed.orders) || []).length;
    el.textContent = !session() ? 'Sign in with the kitchen PIN' : n ? n + ' new order' + (n > 1 ? 's' : '') + ' · tap to accept' : open ? open + ' open order' + (open > 1 ? 's' : '') : 'No orders right now';
    var tile = el.closest('.big-mode');
    if (tile) tile.classList.toggle('lv-has-new', n > 0);
  }

  window.KitchenLive = {
    show: function () { loadPrices(); draw(); if (session()) { refresh(); watch(); } },
    count: function () { paintCount(); }
  };
  window.addEventListener('hashchange', function () { if (!onScreen()) keepAwake(false); });
  if (session()) { loadPrices(); refresh(); watch(); }
})();
