/* Shop receipts from the kitchen app straight into Book Keeper (Victor's bookkeeping app), with no login.
   Uses Book Keeper's intake API with a key Victor makes once per phone in Book Keeper (Settings → Connected apps).
   The key is kept only on that phone (localStorage kitchen.books.v1), never in this repo.
   A receipt lands in Book Keeper's review list and Victor checks it there; nothing is booked automatically. */
(function () {
  'use strict';
  var UI = window.__kitchenUI;
  if (!UI) return;
  var BK = 'https://bookingkeepingaruba.vercel.app';
  var KEY = 'kitchen.books.v1', SENT = 'kitchen.books.sent.v1';
  // Book Keeper's host refuses anything over 4.5 MB before Book Keeper sees it, and the browser only reports "network error".
  var MAX_BYTES = 4 * 1024 * 1024;
  var esc = UI.esc, main = UI.main, foot = UI.foot;
  var pending = null;   // the receipt on screen, not sent yet: { blob, name, preview, thumb, pdf }
  var busy = false;

  function key() { return (UI.store.get(KEY, {}) || {}).key || ''; }
  function sentList() { return UI.store.get(SENT, []) || []; }
  function remember(status, thumb) {
    var list = sentList();
    list.unshift({ t: Date.now(), s: status, th: thumb || '' });
    UI.store.set(SENT, list.slice(0, 12));
  }
  function onScreen() { return /^#\/receipts/.test(location.hash); }

  // ---------------------------------------------------------------- Book Keeper
  function post(form, ms) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, ms) : 0;
    return fetch(BK + '/api/intake/receipts', {
      method: 'POST', headers: { Authorization: 'Bearer ' + key() }, body: form, cache: 'no-store', signal: ctl ? ctl.signal : undefined
    }).then(function (r) {
      clearTimeout(timer);
      return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, body: j }; });
    }, function (e) { clearTimeout(timer); throw e; });
  }
  function problem(res) {
    if (res.status === 401) return 'This phone’s Book Keeper key doesn’t work (wrong, or switched off). Connect again with a new key.';
    if (res.status === 402) return 'Book Keeper’s subscription has ended. Ask Victor.';
    if (res.status === 503) return 'Book Keeper isn’t set up for the kitchen app yet. Ask Victor.';
    if (res.status >= 500) return 'Book Keeper had a problem and didn’t take it. Try again in a few minutes.';
    return (res.body && res.body.error) || 'Book Keeper didn’t take it (' + res.status + ').';
  }

  // ---------------------------------------------------------------- the photo
  function loadImage(file) {
    if (window.createImageBitmap) return createImageBitmap(file, { imageOrientation: 'from-image' }).catch(function () { return viaImg(file); });
    return viaImg(file);
  }
  function viaImg(file) {
    return new Promise(function (ok, bad) {
      var img = new Image();
      img.onload = function () { ok(img); }; img.onerror = function () { bad(new Error('That photo could not be read.')); };
      img.src = URL.createObjectURL(file);
    });
  }
  function scaled(img, longest) {
    var s = Math.min(1, longest / Math.max(img.width, img.height)), cv = document.createElement('canvas');
    cv.width = Math.round(img.width * s); cv.height = Math.round(img.height * s);
    var g = cv.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, cv.width, cv.height);
    g.drawImage(img, 0, 0, cv.width, cv.height);
    return cv;
  }
  /* Longest side 2000 px, JPEG at 80%: small enough to send, sharp enough for Book Keeper to read the total.
     This also turns an iPhone HEIC photo into a JPEG, which Book Keeper's reader needs. */
  function prepare(file) {
    if (file.type === 'application/pdf') {
      if (file.size > MAX_BYTES) return Promise.reject(new Error('That PDF is too big to send (over 4 MB). Take a photo of the receipt instead.'));
      return Promise.resolve({ blob: file, name: file.name || 'receipt.pdf', pdf: true, preview: '', thumb: '' });
    }
    return loadImage(file).then(function (img) {
      var big = scaled(img, 2000);
      return new Promise(function (ok) { big.toBlob(ok, 'image/jpeg', 0.8); }).then(function (blob) {
        if (!blob) throw new Error('That photo could not be read.');
        if (blob.size > MAX_BYTES) throw new Error('That photo is too big to send. Take it again a little further away.');
        return { blob: blob, name: 'receipt.jpg', pdf: false, preview: scaled(img, 900).toDataURL('image/jpeg', 0.8), thumb: scaled(img, 120).toDataURL('image/jpeg', 0.6) };
      });
    });
  }

  // ---------------------------------------------------------------- screens
  function show() {
    if (!key()) return connect();
    UI.setBar({ title: 'Receipts', sub: 'Straight into Book Keeper' });
    if (busy) { sending(); return; }
    if (pending) { check(); return; }
    main.innerHTML = '<div class="me-wrap">' +
      '<p>Bought something for the kitchen? Take a photo of the shop receipt. It goes into Book Keeper, and Victor checks it there.</p>' +
      '<div class="row-btns"><label class="btn primary wide bk-take"><input class="bk-file" type="file" accept="image/*" capture="environment" hidden>Take a photo of the receipt</label></div>' +
      '<div class="row-btns"><label class="btn wide"><input class="bk-file" type="file" accept="image/*,application/pdf" hidden>Pick a photo or PDF</label></div>' +
      '<p class="hint">Whole receipt in the picture, flat, with the total readable.</p>' +
      history() +
      '<div class="row-btns" style="margin-top:22px"><a class="btn" href="' + BK + '/dashboard/receipts" target="_blank" rel="noopener">Open Book Keeper</a>' +
      '<button class="btn warn" data-bact="disconnect">Disconnect this phone</button></div></div>';
    foot.innerHTML = '';
  }
  function check() {
    main.innerHTML = '<div class="me-wrap">' +
      (pending.pdf ? '<p class="bk-pdf">PDF: <b>' + esc(pending.name) + '</b></p>' : '<img class="bk-prev" src="' + pending.preview + '" alt="The receipt photo">') +
      '<p>Can you read the shop name and the total?</p>' +
      '<div class="row-btns"><button class="btn primary wide" data-bact="send">Send to Book Keeper</button></div>' +
      '<div class="row-btns"><button class="btn" data-bact="again">Take it again</button></div></div>';
    foot.innerHTML = '';
  }
  function sending() {
    main.innerHTML = '<div class="me-wrap"><p class="loading">Sending… Book Keeper reads the receipt as it arrives. This can take up to a minute.</p>' +
      '<p class="hint">Keep this screen open.</p></div>';
    foot.innerHTML = '';
  }
  var SAY = { ok: 'Sent. Waiting for Victor to check', manual: 'Sent. Victor types this one in', unsure: 'No answer: check Book Keeper before sending again' };
  function history() {
    var list = sentList();
    if (!list.length) return '';
    return '<h2>Sent from this phone</h2>' + list.map(function (x) {
      var d = new Date(x.t);
      return '<div class="me-row bk-row">' + (x.th ? '<img src="' + x.th + '" alt="">' : '<span class="bk-noimg">PDF</span>') +
        '<div class="me-t"><b>' + esc(d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' }) + ' · ' +
        d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })) + '</b><span' + (x.s === 'unsure' ? ' class="bk-warn"' : '') + '>' + esc(SAY[x.s] || '') + '</span></div></div>';
    }).join('');
  }
  function connect() {
    UI.setBar({ title: 'Connect Book Keeper', sub: 'One time per phone' });
    main.innerHTML = '<div class="me-wrap"><p>Shop receipts can go from this phone straight into Book Keeper, without logging in. The phone needs a key from Book Keeper, once.</p>' +
      '<ol class="me-steps"><li>Victor: in Book Keeper, open <a href="' + BK + '/dashboard/settings/apps" target="_blank" rel="noopener">Settings → Connected apps</a>.</li>' +
      '<li>Type a name for this phone, like <b>Kitchen phone</b>, and tap <b>Create key</b>.</li>' +
      '<li>Copy the key (Book Keeper shows it only once) and paste it below.</li></ol>' +
      '<label class="me-field"><span>Book Keeper key</span><input id="bk-key" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="bk_live_…"></label>' +
      '<div class="row-btns"><button class="btn primary wide" data-bact="savekey">Check and save</button></div>' +
      '<p class="hint">Lost a phone? Switch its key off in Book Keeper (Settings → Connected apps).</p>' +
      '<p class="hint">Rather log in? <a href="' + BK + '/dashboard/receipts" target="_blank" rel="noopener">Open Book Keeper</a></p></div>';
    foot.innerHTML = '';
  }

  // ---------------------------------------------------------------- actions
  var ACT = {
    savekey: function () {
      var k = (document.getElementById('bk-key').value || '').trim();
      if (!/^bk_live_[A-Za-z0-9_-]{43}$/.test(k)) { UI.toast('That doesn’t look like a Book Keeper key. It starts with bk_live_.', 4000); return; }
      UI.store.set(KEY, { key: k });
      UI.toast('Checking the key…', 20000);
      // An empty send: a good key gets "no file" (400) and nothing is stored in Book Keeper.
      post(new FormData(), 20000).then(function (res) {
        if (res.status === 400) { UI.toast('Connected. Receipts from this phone go straight into Book Keeper.', 3500); UI.render(); return; }
        UI.store.del(KEY); UI.toast(problem(res), 6000);
      }, function () {
        UI.store.del(KEY);
        UI.toast(navigator.onLine ? 'Book Keeper didn’t answer. Try again in a few minutes.' : 'No internet. Try again when the phone is online.', 5000);
      });
    },
    send: function () {
      if (!pending || busy) return;
      if (!navigator.onLine) { UI.toast('No internet. Send it when the phone is online.', 4000); return; }
      var r = pending, form = new FormData();
      form.append('file', r.blob, r.name);
      busy = true; sending();
      UI.toast('Sending…', 1500);   // replaces any earlier message still showing
      post(form, 90000).then(function (res) {
        busy = false;
        if (res.status === 201) {
          var manual = res.body && res.body.status === 'extraction_failed';
          remember(manual ? 'manual' : 'ok', r.thumb);
          pending = null;
          UI.toast(manual ? 'Sent. Book Keeper couldn’t read it, so Victor will type it in.' : 'Sent. Victor checks it in Book Keeper.', 4500);
        } else {
          if (res.status === 401) UI.store.del(KEY);
          UI.toast(problem(res), 7000);
        }
        if (onScreen()) UI.render();
      }, function () {
        busy = false;
        if (!navigator.onLine) { UI.toast('The internet dropped. Send it again when the phone is online.', 6000); if (onScreen()) UI.render(); return; }
        // Book Keeper saves the photo before reading it, so it may be there even without an answer.
        remember('unsure', r.thumb);
        pending = null;
        UI.openSheet('<h2>No answer from Book Keeper</h2><p>The receipt may have arrived anyway. Don’t send it again: ask Victor to look in Book Keeper’s receipt list first.</p>');
        if (onScreen()) show();   // not UI.render(): that would close the sheet
      });
    },
    again: function () { pending = null; UI.render(); },
    disconnect: function () {
      UI.openSheet('<h2>Disconnect this phone from Book Keeper?</h2><p>The key is removed from this phone. To make it useless everywhere, also switch it off in Book Keeper.</p>' +
        '<div class="row-btns"><button class="btn warn wide" data-bact="disconnectyes">Yes, disconnect</button></div>');
    },
    disconnectyes: function () { UI.store.del(KEY); UI.closeSheet(); UI.render(); }
  };
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-bact]') : null;
    if (!el || !ACT[el.getAttribute('data-bact')]) return;
    e.preventDefault();
    ACT[el.getAttribute('data-bact')](el);
  });
  document.addEventListener('change', function (e) {
    if (!e.target.classList || !e.target.classList.contains('bk-file') || !e.target.files || !e.target.files[0]) return;
    UI.toast('Getting the photo ready…', 8000);
    prepare(e.target.files[0]).then(function (p) {
      pending = p;
      UI.toast('Photo ready.', 1500);
      if (onScreen()) check();
    }, function (err) { UI.toast(err.message || 'That photo could not be read.', 5000); });
  });

  window.KitchenBooks = { show: show };
})();
