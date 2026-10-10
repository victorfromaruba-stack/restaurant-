/* Orders from the Pidi app, live in the kitchen.
   Sign in once with the kitchen PIN (Victor sets it on /driver/admin/). New orders then come in by
   themselves: the phone beeps and shows a bar on every screen. One big button per step:
   Accept, Start cooking, then "… is ready" per restaurant. When every bag is ready, the order is
   offered to the drivers by itself. The database decides what is allowed; this screen only asks.
   Each card leads with the night's order number ("Order 14"). Pre-orders not due yet wait under
   "Later tonight" with the time to start. "Kitchen busy?" adds 15 or 30 minutes to the delivery time
   new customers see. A line whose price doesn't match the menu gets a red warning (nothing is blocked). */
(function () {
  'use strict';
  var UI = window.__kitchenUI, P = window.Pidi;
  if (!UI || !P) return;
  var esc = UI.esc, main = UI.main, foot = UI.foot;
  var KEY = 'pidi.kitchen.session';      // { token, expires_at, topic } on this phone only
  var SEEN = 'pidi.kitchen.seen.v1';     // order ids this phone has already beeped for
  var POLL = 8000;

  var feed = null, lastAt = 0, lastErr = '', busy = {}, pinErr = '', stopListen = null, watching = 0;
  var menus = null, menusAt = 0, menusLoading = false;   // restaurant slug -> its menu.json, to catch a wrong price
  var busyMin = null, busySaving = false, busySetAt = 0, busyAskedAt = 0;   // "Kitchen busy?": 0, 15 or 30

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
  // Each line of an order is "Dish name · option · option" with the unit price the phone sent. It is checked
  // against that restaurant's own menu.json: the dish price plus the extra of each chosen option. Nothing is
  // blocked; a line that doesn't match says so in red.
  // Read again every 10 minutes while the screen is open, so a price changed tonight is the one checked.
  function loadMenus() {
    if (menusLoading || (menus && Date.now() - menusAt < 10 * 60000)) return;
    menusLoading = true;
    var next = {};
    fetch('../../shared/site.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (site) {
      return Promise.all((site.brands || []).map(function (b) {
        return fetch('../../' + b.id + '/menu.json', { cache: 'no-cache' }).then(function (r) { return r.json(); })
          .then(function (m) { next[b.id] = m; }, function () { if (menus && menus[b.id]) next[b.id] = menus[b.id]; });
      }));
    }).then(function () {
      menus = next; menusAt = Date.now(); menusLoading = false;
      if (onScreen()) draw();
    }, function () { menusLoading = false; });
  }
  function key(s) { return String(s == null ? '' : s).replace(/[‘’]/g, "'").replace(/\s+/g, ' ').trim().toLowerCase(); }
  // The choices one option text stands for, as [{ g: group, c: choice }]: "No onion", "Sauce: On the side",
  // "Leave out: No onion, No egg", "No pickles, No mayo". null when the text names no choice on the menu.
  function choicesFor(dish, text) {
    var groups = dish.options || [], m = /^([^:]+):\s*(.+)$/.exec(text);
    function one(t, only) {
      var hit = null;
      groups.forEach(function (g) {
        if (only && g !== only) return;
        (g.choices || []).forEach(function (c) {
          if (!hit && (key(c.label) === key(t) || key(g.label + ' ' + c.label) === key(t))) hit = { g: g, c: c };
        });
      });
      return hit;
    }
    function all(list, only) {
      var hits = list.map(function (t) { return one(t, only); });
      return hits.every(Boolean) ? hits : null;
    }
    var found = null;
    if (m) groups.forEach(function (g) { if (!found && key(g.label) === key(m[1])) found = all(m[2].split(/\s*,\s*/), g); });
    return found || (one(text) ? [one(text)] : all(text.split(/\s*,\s*/)));
  }
  // null: that restaurant's menu isn't here (can't check). Else { found, cents } for one of the dish.
  function menuPrice(slug, name) {
    var menu = menus && menus[slug];
    if (!menu) return null;
    var parts = String(name || '').split(' · '), dishName = parts.shift();
    var dish = (menu.items || []).filter(function (i) { return key(i.name) === key(dishName); })[0];
    if (!dish) return { found: false, menu: menu.name || slug };
    var cents = dish.price || 0, named = {};
    parts.forEach(function (p) {
      (choicesFor(dish, p) || []).forEach(function (h) { named[h.g.id] = true; cents += h.c.price || 0; });
    });
    (dish.options || []).forEach(function (g) {   // a one-choice option nobody named is the menu's default
      if (g.type !== 'one' || named[g.id]) return;
      var d = (g.choices || []).filter(function (c) { return c.id === g['default']; })[0];
      if (d && d.price) cents += d.price;
    });
    return { found: true, cents: cents };
  }
  function priceProblem(slug, item) {
    var want = menuPrice(slug, item.name);
    if (!want) return '';
    if (!want.found) return 'Check this dish: it is not on the ' + esc(want.menu) + ' menu.';
    if (want.cents !== item.price_cents) return 'Check the price: ' + money(item.price_cents) + ' here, the menu says ' + money(want.cents) + '.';
    return '';
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
    var asked = Date.now();
    return P.rpc('pidi_kitchen_feed', { session: s.token }).then(function (f) {
      feed = f || { orders: [] }; lastAt = Date.now(); lastErr = '';
      readBusy(feed, asked);
      loadMenus();
      var fresh = (feed.orders || []).filter(function (o) { return o.status === 'new' && !seen()[o.id]; });
      if (fresh.length) {
        markSeen(fresh.map(function (o) { return o.id; }));
        beep();
        if (!onScreen()) {
          UI.toast('New order' + (fresh[0].night_no ? ' ' + fresh[0].night_no : '') + ': ' + fresh[0].name + (fresh[0].area ? ' · ' + fresh[0].area : '') + '. Tap Orders.', 8000);
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
  // "Kitchen busy?": the feed carries the current minutes on every order. With no orders open, the public
  // state says it (at most every 30 s). A feed asked for before a change is older than the change: ignored.
  function readBusy(f, asked) {
    if (asked < busySetAt) return;
    var v = f && f.busy_min != null ? f.busy_min : null;
    if (v == null) ((f && f.orders) || []).some(function (o) { v = o.busy_min; return v != null; });
    var n = parseInt(v, 10);
    if (!isNaN(n)) { busyMin = n; return; }
    if (Date.now() - busyAskedAt < 30000) return;
    busyAskedAt = Date.now();
    P.rpc('pidi_public_state', {}).then(function (st) {
      var m = parseInt(st && st.busy_min, 10);
      if (!isNaN(m) && busyAskedAt >= busySetAt) { busyMin = m; if (onScreen()) draw(); }
    }, function () { /* the switch shows "Checking…" until the next try */ });
  }
  function setBusy(n) {
    var s = session();
    if (!s || busySaving) return;
    busySaving = true; draw();
    P.rpc('pidi_kitchen_set_busy', { session: s.token, minutes: n }).then(function (r) {
      busySaving = false; busySetAt = Date.now();
      var got = parseInt(r && r.busy_min, 10);
      busyMin = isNaN(got) ? n : got;
      UI.toast(busyMin ? 'Kitchen busy: new customers see a delivery time ' + busyMin + ' min later.' : 'Back to normal. New customers see the usual delivery time.', 5000);
      draw();
    }, function (err) {
      busySaving = false;
      if (/sign in again/i.test(err.message)) signOut('Sign in again with the kitchen PIN.');
      UI.toast(err.message, 6000);
      draw();
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
    var lines = ['*Order*' + (order.night_no ? ' #' + order.night_no : '') + ' · ' + order.name];
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
    lines.push('Pay: ' + (order.pay === 'cash' ? (order.pays_in_usd ? 'Cash in US dollars' : 'Cash') : 'Bank transfer'));
    lines.push('Total ' + P.money(order.total_cents));
    var o = UI.parseOrder(lines.join('\n'));
    o.live = order.id;
    o.no = order.night_no ? String(order.night_no) : '';
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
    if (what === 'busy' || what === 'busy-yes') {
      var n = +b.getAttribute('data-min');
      if (what === 'busy' && n === busyMin) return;
      if (what === 'busy' && n === 30) {
        UI.openSheet('<h2>Very busy: +30 min?</h2><p>New customers see a delivery time 30 minutes later. Orders already in keep their time.</p>' +
          '<div class="row-btns"><button class="btn go wide lv-big" data-live="busy-yes" data-min="30">Yes, +30 min</button></div>');
        return;
      }
      UI.closeSheet();
      setBusy(n);
      return;
    }
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
  // Times on this screen are Aruba's, whatever zone the phone is set to.
  function arubaTime(ts) {
    try { return new Date(ts).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Aruba' }); }
    catch (e) { return UI.clock(typeof ts === 'number' ? ts : Date.parse(ts)); }
  }
  function phoneLink(p) {
    var d = String(p || '').replace(/\D/g, '');
    if (d.length === 7) d = '297' + d;
    return d ? '<a class="lv-call" href="tel:+' + d + '">Call</a><a class="lv-call" href="https://wa.me/' + d + '" target="_blank" rel="noopener">WhatsApp</a>' : '';
  }
  // A pre-order (due more than 20 minutes after it came in) waits in "Later tonight" until it is time to
  // start: its delivery time minus the order's own longest delivery promise. Times are Aruba's, never the phone's.
  function isPre(o) { return !!o.due_at && Date.parse(o.due_at) - Date.parse(o.created_at) > 20 * 60000; }
  function startAt(o) { return isPre(o) ? Date.parse(o.due_at) - (parseInt(o.eta_max, 10) || 60) * 60000 : Date.parse(o.created_at); }
  function isLater(o, now) { return isPre(o) && STEP[o.status] <= 1 && now < startAt(o); }
  function payLine(o) {
    if (o.pay === 'transfer') {
      return '<div class="pay pay--bank"><span class="lv-nw">Bank transfer ·</span> <span class="lv-nw">' + (o.transfer_status === 'paid' ? 'came in' : 'not in yet') + '</span></div>';
    }
    // each half stays on one line, so a narrow phone breaks the line at the dot
    if (o.pays_in_usd) return '<div class="pay pay--usd"><span class="lv-nw">Pays in US dollars ·</span> <span class="lv-nw">' + money(o.total_cents) + ' total</span></div>';
    return '<div class="pay"><span class="lv-nw">Pays ' + money(o.pays_with_cents) + ' cash ·</span> <span class="lv-nw">' +
      (o.change_due_cents > 0 ? money(o.change_due_cents) + ' change' : 'no change') + '</span></div>';
  }
  function card(o) {
    var b = !!busy[o.id], step = STEP[o.status];
    var single = (o.restaurants || []).length === 1;
    var h = '<article class="lv-card lv-' + esc(o.status) + (o.test ? ' lv-is-test' : '') + '">';
    h += '<div class="ohead">';
    h += '<div class="lv-top"><span class="lv-no">' + esc(o.night_no ? 'Order ' + o.night_no : 'Order · ' + arubaTime(o.created_at)) + '</span>' +
      (o.test ? '<span class="lv-test">TEST</span>' : '') + '</div>';
    if (o.test) h += '<div class="lv-testnote">Test order: not a real customer.</div>';
    h += '<div class="lv-when">Came in ' + esc(arubaTime(o.created_at)) + ' · ' + ago(o.created_at) + '</div>';
    if (isPre(o)) {
      h += '<div class="when when--set">Deliver at ' + esc(arubaTime(o.due_at)) + '</div>';
      if (isLater(o, Date.now())) h += '<div class="lv-start">Start cooking at ' + esc(arubaTime(startAt(o))) + '</div>';
    }
    h += '<div class="mode">' + esc(o.area || 'Delivery') + '</div>';
    h += payLine(o);
    h += '<div class="who">' + esc(o.name) + ' <span class="lv-phone">' + esc(o.phone || '') + '</span></div>';
    h += '<div class="addr">' + esc(o.address || '') + '</div>';
    h += '<div class="lv-contact">' + phoneLink(o.phone) + '</div>';
    if (o.note) h += '<div class="notebox"><small>Customer note</small>' + esc(o.note) + '</div>';
    h += '</div>';
    (o.restaurants || []).forEach(function (g) {
      var br = UI.brand(g.slug) || {};
      h += '<div class="brand-h lv-brand" style="background:' + esc(br.accent || '#26406A') + ';color:' + esc(br.ink || '#fff') + '">' +
        '<span>' + esc(g.restaurant) + '</span>' + (g.ready ? '<span class="lv-tick">Ready</span>' : '') + '</div>';
      h += '<ul class="lv-items">' + (g.items || []).map(function (i) {
        var parts = String(i.name).split(' · '), bad = priceProblem(g.slug, i);
        return '<li' + (bad ? ' class="lv-bad"' : '') + '><b>' + esc(i.qty) + ' ×</b> <span>' + esc(parts[0]) +
          (parts.length > 1 ? '<em>' + esc(parts.slice(1).join(' · ')) + '</em>' : '') +
          (bad ? '<strong class="lv-price">' + bad + '</strong>' : '') + '</span></li>';
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
      // a pre-order that isn't due yet can start early, but it isn't the loud next step
      h += '<button class="btn' + (isLater(o, Date.now()) ? '' : ' primary') + ' wide lv-big" data-live="cooking" data-id="' + esc(o.id) + '"' + (b ? ' disabled' : '') + '>Start cooking</button>';
    } else if (o.status === 'ready') {
      h += '<div class="lv-wait">Ready. Waiting for a driver to take it.</div>';
    } else if (step === 4) {
      h += '<div class="lv-wait">' + (o.status === 'picked_up' ? 'The driver has it.' : 'A driver took it and is coming for the bags.') + '</div>';
    }
    if (step === 1 || step === 2) h += '<button class="btn wide" data-live="cook" data-id="' + esc(o.id) + '">Cook step by step</button>';
    var small = '';
    if (o.pay === 'transfer' && o.transfer_status !== 'paid') small += '<button class="btn small" data-live="paid" data-id="' + esc(o.id) + '"' + (b ? ' disabled' : '') + '>The transfer came in</button>';
    if (step <= 3) small += '<button class="btn small warn" data-live="cancel" data-id="' + esc(o.id) + '">Can’t do this order</button>';
    if (small) h += '<div class="row-btns lv-small">' + small + '</div>';
    return h + '</article>';
  }
  // "Kitchen busy?": three big choices. The database adds the minutes to the time new customers see.
  function busyBox() {
    var h = '<section class="lv-busy"><h2 id="lv-busy-t">Kitchen busy?</h2><div class="lv-seg" role="group" aria-labelledby="lv-busy-t">';
    h += [[0, 'Normal'], [15, '+15 min'], [30, '+30 min']].map(function (c) {
      var on = busyMin === c[0];
      return '<button class="lv-segb' + (on ? ' on' : '') + '" data-live="busy" data-min="' + c[0] + '" aria-pressed="' + on + '"' + (busySaving ? ' disabled' : '') + '>' + c[1] + '</button>';
    }).join('');
    var line = busySaving ? 'Saving…' : busyMin == null ? 'Checking…'
      : busyMin ? 'On: new customers see a delivery time ' + busyMin + ' min later. Tap Normal when the rush is over.'
      : 'Rush on? Tap +15 or +30. New customers see a later delivery time.';
    return h + '</div><p class="lv-busy-p">' + esc(line) + '</p></section>';
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
    var now = Date.now(), all = (feed && feed.orders) || [];
    // cook now: by step, then by when it had to start; later tonight: by when to start
    var soon = all.filter(function (o) { return !isLater(o, now); }).sort(function (a, b) {
      return (STEP[a.status] - STEP[b.status]) || (startAt(a) - startAt(b));
    });
    var later = all.filter(function (o) { return isLater(o, now); }).sort(function (a, b) { return startAt(a) - startAt(b); });
    UI.setBar({ title: 'Orders', sub: lastAt ? 'Live · checked ' + arubaTime(lastAt) : 'Loading…' });
    var h = '';
    if (lastErr) h += '<div class="banner allergy">' + esc(lastErr) + ' <button class="btn small" data-live="retry">Try again</button></div>';
    h += busyBox();
    if (!feed) h += '<p class="loading">Loading orders…</p>';
    else if (!all.length) h += '<div class="lv-empty"><b>No orders right now.</b><span>Keep this screen open. New orders beep and show up here by themselves.</span></div>';
    else {
      h += soon.length ? soon.map(card).join('') : '<div class="lv-empty lv-empty--now"><b>Nothing to cook right now.</b></div>';
      if (later.length) {
        h += '<section class="lv-later"><h2>Later tonight</h2><p class="lv-later-p">Pre-orders. Each one says when to start cooking.</p>' + later.map(card).join('') + '</section>';
      }
    }
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
    show: function () { loadMenus(); draw(); if (session()) { refresh(); watch(); } },
    count: function () { paintCount(); }
  };
  window.addEventListener('hashchange', function () { if (!onScreen()) keepAwake(false); });
  if (session()) { loadMenus(); refresh(); watch(); }
})();
