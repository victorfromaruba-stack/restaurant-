/* Menu editor for the kitchen app: sold out, prices, words, photos, new dishes, restaurant open/closed.
   Saves straight into the website's GitHub repo with a fine-grained GitHub key that is pasted once per phone
   (stored only on that phone). GitHub Pages then updates the live site in about a minute.
   Menus are read fresh from GitHub before every change, so two phones never overwrite each other's edits. */
(function () {
  'use strict';
  var UI = window.__kitchenUI;
  if (!UI) return;
  var GH = { api: 'https://api.github.com', owner: 'victorfromaruba-stack', repo: 'restaurant-', branch: 'main' };
  var KEY = 'kitchen.github.v1';
  // GitHub's "new key" page, pre-filled: name, 1 year, Contents read and write. The repository can't be pre-picked by link.
  var TOKEN_URL = 'https://github.com/settings/personal-access-tokens/new?name=Kitchen+app&description=Change+the+Order+Aruba+menu+from+the+chef+app' +
    '&target_name=' + GH.owner + '&expires_in=365&contents=write';
  var esc = UI.esc, main = UI.main, foot = UI.foot;
  var FLAGS = [['spicy', 'Spicy'], ['vegetarian', 'Vegetarian'], ['pork', 'Contains pork'], ['shrimp', 'Contains shrimp'], ['peanut', 'Contains peanuts']];
  var ALLERGENS = [['gluten', 'Gluten'], ['egg', 'Egg'], ['dairy', 'Milk'], ['soy', 'Soy'], ['shellfish', 'Shellfish'], ['sesame', 'Sesame'],
    ['peanut', 'Peanuts'], ['nuts', 'Tree nuts'], ['mustard', 'Mustard'], ['fish', 'Fish'], ['celery', 'Celery']];
  var STATUS = [['open', 'Open'], ['soon', 'Opening soon'], ['hidden', 'Hidden']];

  function token() { return (UI.store.get(KEY, {}) || {}).token || ''; }
  function cents(c) { return 'ƒ' + (c / 100).toFixed(2); }
  function site(path) { return '../../' + path; }

  // ---------------------------------------------------------------- GitHub
  function gh(method, path, body) {
    var h = { Authorization: 'Bearer ' + token(), Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' };
    if (body) h['Content-Type'] = 'application/json';
    return fetch(GH.api + path, { method: method, headers: h, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) { var e = new Error(j.message || 'GitHub ' + r.status); e.status = r.status; throw e; }
        return j;
      });
    });
  }
  function filePath(p) { return '/repos/' + GH.owner + '/' + GH.repo + '/contents/' + p.split('/').map(encodeURIComponent).join('/'); }
  function b64text(t) { return btoa(unescape(encodeURIComponent(t))); }
  function textb64(b) { return decodeURIComponent(escape(atob(String(b).replace(/\s/g, '')))); }
  function readJson(p) {
    return gh('GET', filePath(p) + '?ref=' + GH.branch).then(function (j) { return { sha: j.sha, data: JSON.parse(textb64(j.content)) }; });
  }
  function fileSha(p) {
    return gh('GET', filePath(p) + '?ref=' + GH.branch).then(function (j) { return j.sha; }, function (e) { if (e.status === 404) return null; throw e; });
  }
  function putFile(p, b64, sha, message) {
    var body = { message: message, content: b64, branch: GH.branch };
    if (sha) body.sha = sha;
    return gh('PUT', filePath(p), body);
  }
  /* Read the latest copy, change it, save it. If someone else saved in between, do it once more on their copy. */
  function updateJson(p, change, message, retried) {
    return readJson(p).then(function (f) {
      var err = change(f.data);
      if (err) throw new Error(err);
      return putFile(p, b64text(JSON.stringify(f.data, null, 1)), f.sha, message);
    }).catch(function (e) {
      if (!retried && (e.status === 409 || e.status === 422)) return updateJson(p, change, message, true);
      throw e;
    });
  }
  function explain(e) {
    if (e.status === 401) return 'The GitHub key is wrong or expired. Disconnect and paste a new one.';
    if (e.status === 403 || e.status === 404) return 'This GitHub key can’t save. It needs the restaurant- repo with Contents: Read and write.';
    if (!navigator.onLine) return 'No internet. Try again when the phone is online.';
    return e.message || 'Saving didn’t work. Try again.';
  }
  function saving(promise, done) {
    UI.toast('Saving…', 20000);
    return promise.then(function () {
      UI.toast('Saved. The website shows it in about a minute.', 4000);
      if (done) done();
    }, function (e) { UI.toast(explain(e), 6000); });
  }

  // ---------------------------------------------------------------- pictures from the phone camera
  function loadImage(file) {
    if (window.createImageBitmap) return createImageBitmap(file, { imageOrientation: 'from-image' }).catch(function () { return viaImg(file); });
    return viaImg(file);
  }
  function viaImg(file) {
    return new Promise(function (ok, bad) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () { ok(img); }; img.onerror = function () { bad(new Error('That photo could not be read.')); };
      img.src = url;
    });
  }
  function cover(src, w, h) {
    var cv = document.createElement('canvas'); cv.width = w; cv.height = h;
    var sw = src.width, sh = src.height, s = Math.max(w / sw, h / sh), dw = sw * s, dh = sh * s;
    cv.getContext('2d').drawImage(src, (w - dw) / 2, (h - dh) / 2, dw, dh);
    return cv;
  }
  function encode(cv, type, q) {
    return new Promise(function (ok) { cv.toBlob(function (b) { ok(b); }, type, q); });
  }
  function blob64(b) {
    return new Promise(function (ok, bad) { var r = new FileReader(); r.onload = function () { ok(String(r.result).split(',')[1]); }; r.onerror = bad; r.readAsDataURL(b); });
  }
  /* 780x446 for the dish, 360x360 for the menu row. WebP where the phone can make it, else JPEG (iPhones). */
  function makePictures(file) {
    return loadImage(file).then(function (img) {
      var full = cover(img, 780, 446), sq = document.createElement('canvas');
      sq.width = sq.height = 360;
      sq.getContext('2d').drawImage(full, (780 - 446) / 2, 0, 446, 446, 0, 0, 360, 360);
      return encode(full, 'image/webp', 0.8).then(function (b) {
        var webp = b && b.type === 'image/webp';
        return Promise.all([webp ? b : encode(full, 'image/jpeg', 0.82), encode(sq, webp ? 'image/webp' : 'image/jpeg', webp ? 0.76 : 0.8)]).then(function (bs) {
          return Promise.all([blob64(bs[0]), blob64(bs[1])]).then(function (x) { return { ext: webp ? 'webp' : 'jpg', full: x[0], thumb: x[1], preview: full.toDataURL('image/jpeg', 0.8) }; });
        });
      });
    });
  }
  function thumbOf(img) { return img.replace(/([^/]+)$/, 'thumbs/$1'); }
  /* Save the photo. Same file name as before when possible, so every screen that shows this dish updates. */
  function savePictures(brand, item, pics, message) {
    var path = item.img && item.img.split('.').pop().toLowerCase() === pics.ext ? item.img : brand + '/assets/dishes/' + item.id + '.' + pics.ext;
    var tpath = thumbOf(path);
    return Promise.all([fileSha(path), fileSha(tpath)]).then(function (s) {
      return putFile(tpath, pics.thumb, s[1], message + ' (row picture)').then(function () { return putFile(path, pics.full, s[0], message + ' (picture)'); });
    }).then(function () { return path; });
  }

  // ---------------------------------------------------------------- screens
  function show(args) {
    if (!token()) return connect();
    if (!args[0]) return brands();
    if (args[1] === 'new') return edit(args[0], null);
    if (args[1]) return edit(args[0], args[1]);
    return brandScreen(args[0]);
  }
  function loading(title) {
    UI.setBar({ title: title, sub: 'Menu' });
    main.innerHTML = '<p class="loading">Loading the menu from the website…</p>';
    foot.innerHTML = '';
  }
  function failed(e) {
    main.innerHTML = '<p class="loading">' + esc(explain(e)) + '</p><div class="row-btns"><button class="btn" data-mact="retry">Try again</button>' +
      '<button class="btn warn" data-mact="disconnect">Disconnect this phone</button></div>';
  }

  function connect() {
    UI.setBar({ title: 'Connect the menu', sub: 'One time per phone' });
    main.innerHTML = '<div class="me-wrap"><p>To change dishes from this phone, it needs a key from GitHub (where the website lives). Make one, paste it here, done. Only phones with the key can change the menu.</p>' +
      '<ol class="me-steps"><li>Logged in to GitHub as <b>victorfromaruba-stack</b>, open <a href="' + TOKEN_URL + '" target="_blank" rel="noopener">this ready-made key</a>. Name, 1 year and the permission are already filled in.</li>' +
      '<li>Repository access: <b>Only select repositories</b> → <b>restaurant-</b>. (GitHub doesn’t let a link choose this.)</li>' +
      '<li>Tap <b>Generate token</b>, copy it, paste it below.</li></ol>' +
      '<p class="hint">If the permission isn’t filled in: Permissions → Repository permissions → <b>Contents: Read and write</b>. For the chef’s phone, make a second key and call it <b>Kitchen app (chef)</b>.</p>' +
      '<label class="me-field"><span>GitHub key</span><input id="me-token" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="github_pat_…"></label>' +
      '<div class="row-btns"><button class="btn primary wide" data-mact="savetoken">Check and save</button></div>' +
      '<p class="hint">Lost a phone? Delete its key on GitHub (Settings → Developer settings → Fine-grained tokens) and the phone can’t change anything.</p></div>';
    foot.innerHTML = '';
  }

  function brands() {
    loading('Menu');
    readJson('shared/site.json').then(function (s) {
      UI.setBar({ title: 'Menu', sub: 'Sold out, prices, new dishes' });
      var rows = s.data.brands.map(function (b) {
        var st = STATUS.filter(function (x) { return x[0] === b.status; })[0];
        return '<a class="me-brand" href="#/menu/' + esc(b.id) + '"><img src="' + esc(site('shared/logos/' + b.id + '-mark.webp')) + '" alt=""><b>' + esc(nameOf(b.id)) + '</b>' +
          '<span class="me-st me-st--' + esc(b.status) + '">' + esc(st ? st[1] : b.status) + '</span></a>';
      }).join('');
      main.innerHTML = '<div class="me-wrap">' + rows + '<p class="hint">Changes show on the website about a minute after you save.</p>' +
        '<div class="row-btns" style="margin-top:28px"><button class="btn warn" data-mact="disconnect">Disconnect this phone</button></div></div>';
    }, failed);
  }
  function nameOf(id) { return id.replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); }).replace('Nonnas', 'Nonna’s'); }

  var current = null;   // { brand, menu, site }
  function brandScreen(brand) {
    loading(nameOf(brand));
    Promise.all([readJson(brand + '/menu.json'), readJson('shared/site.json')]).then(function (r) {
      var menu = r[0].data, siteData = r[1].data, b = siteData.brands.filter(function (x) { return x.id === brand; })[0] || { status: 'open' };
      current = { brand: brand, menu: menu };
      UI.setBar({ title: menu.name, sub: 'Menu', side: { label: 'Menu', href: '#/menu' } });
      var food = menu.items.filter(function (i) { return i.kind !== 'drink'; }), drinks = menu.items.filter(function (i) { return i.kind === 'drink'; });
      var h = '<div class="me-wrap"><h2>Restaurant is</h2><div class="me-seg">' + STATUS.map(function (s) {
        return '<button class="me-segb' + (b.status === s[0] ? ' on' : '') + '" data-mact="status" data-v="' + s[0] + '" aria-pressed="' + (b.status === s[0]) + '">' + s[1] + '</button>';
      }).join('') + '</div>';
      h += '<h2>Dishes <small>' + food.length + '</small></h2>';
      if (food.length < 6 || food.length > 8) h += '<p class="me-warn">Keep 6 to 8 dishes per restaurant, so one chef can make everything.</p>';
      h += food.map(row).join('');
      h += '<div class="row-btns"><a class="btn primary wide" href="#/menu/' + esc(brand) + '/new">+ New dish</a></div>';
      h += '<h2>Drinks</h2>' + drinks.map(row).join('') + '</div>';
      main.innerHTML = h;
      foot.innerHTML = '';
    }, failed);
  }
  function row(i) {
    var drink = i.kind === 'drink';
    return '<div class="me-row' + (i.soldOut ? ' out' : '') + '"><img src="' + esc(site(drink ? i.img : thumbOf(i.img))) + '" alt="" onerror="this.onerror=null;this.src=\'' + esc(site(i.img)) + '\'">' +
      '<div class="me-t"><b>' + esc(i.name) + '</b><span>' + cents(i.price) + (i.soldOut ? ' · <em>Sold out</em>' : '') + '</span></div>' +
      '<div class="me-b"><button class="btn small' + (i.soldOut ? ' go' : ' warn') + '" data-mact="soldout" data-id="' + esc(i.id) + '" data-v="' + (i.soldOut ? 'on' : 'out') + '">' + (i.soldOut ? 'Back on' : 'Sold out') + '</button>' +
      (drink ? '' : '<a class="btn small" href="#/menu/' + esc(current.brand) + '/' + esc(i.id) + '">Edit</a>') + '</div></div>';
  }

  var pics = null;
  function edit(brand, id) {
    loading(id ? 'Edit dish' : 'New dish');
    pics = null;
    readJson(brand + '/menu.json').then(function (r) {
      var menu = r.data, it = id ? menu.items.filter(function (i) { return i.id === id; })[0] : null;
      if (id && !it) { main.innerHTML = '<p class="loading">That dish isn’t on the menu any more.</p>'; return; }
      current = { brand: brand, menu: menu };
      it = it || { name: '', price: 0, desc: '', flags: [], allergens: [], section: busiest(menu) };
      UI.setBar({ title: id ? it.name : 'New dish', sub: menu.name, side: { label: 'Back', href: '#/menu/' + brand } });
      var secs = menu.sections.filter(function (s) { return s.id !== 'drinks'; });
      function boxes(list, on, name) {
        return '<div class="me-checks">' + list.map(function (x) {
          return '<label><input type="checkbox" name="' + name + '" value="' + x[0] + '"' + ((on || []).indexOf(x[0]) >= 0 ? ' checked' : '') + '><span>' + x[1] + '</span></label>';
        }).join('') + '</div>';
      }
      main.innerHTML = '<form class="me-wrap me-form" onsubmit="return false">' +
        '<div class="me-photo"><img id="me-prev" src="' + (it.img ? esc(site(it.img)) : '') + '" alt=""' + (it.img ? '' : ' hidden') + '>' +
        '<label class="btn wide"><input id="me-file" type="file" accept="image/*" capture="environment" hidden>' + (it.img ? 'Take a new photo' : 'Take the photo') + '</label>' +
        '<p class="hint">Photograph the real dish, exactly as it goes out. Nothing extra on the plate.</p></div>' +
        '<label class="me-field"><span>Name</span><input id="me-name" maxlength="60" value="' + esc(it.name) + '"></label>' +
        '<label class="me-field"><span>Price (ƒ)</span><input id="me-price" inputmode="decimal" value="' + (it.price ? (it.price / 100).toFixed(2) : '') + '" placeholder="14.50"></label>' +
        '<label class="me-field"><span>What’s in it</span><textarea id="me-desc" rows="3" maxlength="220">' + esc(it.desc || '') + '</textarea></label>' +
        '<label class="me-field"><span>Part of the menu</span><select id="me-sec">' + secs.map(function (s) {
          return '<option value="' + esc(s.id) + '"' + (s.id === it.section ? ' selected' : '') + '>' + esc(s.title) + '</option>';
        }).join('') + '</select></label>' +
        '<h2>Labels</h2>' + boxes(FLAGS, it.flags, 'flag') +
        '<h2>Allergens in the recipe</h2>' + boxes(ALLERGENS, it.allergens, 'allergen') +
        '<div class="me-checks"><label><input type="checkbox" id="me-fried"' + (it.fried ? ' checked' : '') + '><span>Goes in the fryer</span></label></div>' +
        (it.options && it.options.length ? '<p class="hint">Taps like “No onion” stay as they are.</p>' : '') +
        '<div class="row-btns"><button class="btn primary wide" data-mact="save" data-id="' + esc(id || '') + '">' + (id ? 'Save changes' : 'Add to the menu') + '</button></div>' +
        (id ? '<div class="row-btns"><button class="btn warn wide" data-mact="remove" data-id="' + esc(id) + '">Remove from the menu</button></div>' : '') +
        '</form>';
      foot.innerHTML = '';
    }, failed);
  }
  function busiest(menu) {   // a new dish starts in the part of the menu with the most dishes
    var n = {};
    menu.items.forEach(function (i) { if (i.kind !== 'drink' && i.kind !== 'side') n[i.section] = (n[i.section] || 0) + 1; });
    return Object.keys(n).sort(function (a, b) { return n[b] - n[a]; })[0] || menu.sections[0].id;
  }
  function inBundle(menu, id) { return menu.items.filter(function (i) { return (i.includes || []).indexOf(id) >= 0; })[0]; }
  function checked(name) { return Array.prototype.slice.call(main.querySelectorAll('input[name="' + name + '"]:checked')).map(function (i) { return i.value; }); }
  function readForm() {
    var v = function (id) { var el = document.getElementById(id); return el ? el.value.trim().replace(/\s+/g, ' ') : ''; };
    var price = Math.round(parseFloat(v('me-price').replace(',', '.')) * 100);
    var f = { name: v('me-name'), price: price, desc: v('me-desc'), section: v('me-sec'), flags: checked('flag'), allergens: checked('allergen'),
      fried: document.getElementById('me-fried').checked };
    if (f.name.length < 2) return { err: 'Give the dish a name.' };
    if (!(price >= 50 && price <= 50000)) return { err: 'Type a price like 14.50.' };
    if (f.desc.length < 5) return { err: 'Say what’s in it, so the picture and the words match.' };
    return f;
  }
  function newId(menu, name) {
    var w = name.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]/g, '').split(' ').filter(Boolean);
    var base = (w[0] || 'd').charAt(0) + (w[1] || w[0] || 'x').charAt(w[1] ? 0 : 1), id = base, n = 2;
    var ids = menu.items.map(function (i) { return i.id; });
    while (ids.indexOf(id) >= 0) id = base + n++;
    return id;
  }
  /* Keep the dish's own order (and anything this screen doesn't list); ticked ones that are new go at the end. */
  function merge(old, picked, list) {
    var shown = list.map(function (x) { return x[0]; });
    return (old || []).filter(function (v) { return picked.indexOf(v) >= 0 || shown.indexOf(v) < 0; })
      .concat(picked.filter(function (v) { return (old || []).indexOf(v) < 0; }));
  }
  function apply(item, f) {
    item.name = f.name; item.price = f.price; item.desc = f.desc; item.section = f.section;
    item.allergens = merge(item.allergens, f.allergens, ALLERGENS);
    var flags = merge(item.flags, f.flags, FLAGS);
    if (flags.length) item.flags = flags; else delete item.flags;
    if (f.fried) item.fried = true; else delete item.fried;
    if (f.section === 'sides') item.kind = 'side'; else if (item.kind === 'side') delete item.kind;
  }

  // ---------------------------------------------------------------- actions
  var ACT = {
    retry: function () { UI.render(); },
    savetoken: function () {
      var t = (document.getElementById('me-token').value || '').trim();
      if (!/^(github_pat_|ghp_)\w{20,}/.test(t)) { UI.toast('That doesn’t look like a GitHub key. It starts with github_pat_.', 4000); return; }
      UI.store.set(KEY, { token: t });
      UI.toast('Checking the key…', 10000);
      gh('GET', '/repos/' + GH.owner + '/' + GH.repo).then(function () {
        UI.toast('Connected. You can change the menu from this phone.', 3500); UI.go('#/menu');
      }, function (e) { UI.store.del(KEY); UI.toast(explain(e), 6000); });
    },
    disconnect: function () {
      UI.openSheet('<h2>Disconnect this phone from the menu?</h2><p>The key is removed from this phone. To make it useless everywhere, also delete it on GitHub.</p>' +
        '<div class="row-btns"><button class="btn warn wide" data-mact="disconnectyes">Yes, disconnect</button></div>');
    },
    disconnectyes: function () { UI.store.del(KEY); UI.closeSheet(); UI.go('#/menu'); },
    status: function (el) {
      var brand = current.brand, v = el.getAttribute('data-v');
      saving(updateJson('shared/site.json', function (s) {
        var b = s.brands.filter(function (x) { return x.id === brand; })[0];
        if (!b) return 'That restaurant isn’t in the website settings.';
        b.status = v;
      }, 'Menu (kitchen app): ' + current.menu.name + ' is now ' + v), UI.render);
    },
    soldout: function (el) {
      // Sets what the button says (not a toggle), so two phones tapping Sold out still leave it sold out.
      var brand = current.brand, id = el.getAttribute('data-id'), out = el.getAttribute('data-v') === 'out';
      saving(updateJson(brand + '/menu.json', function (m) {
        var it = m.items.filter(function (i) { return i.id === id; })[0];
        if (!it) return 'That dish isn’t on the menu any more.';
        if (out) it.soldOut = true; else delete it.soldOut;
      }, 'Menu (kitchen app): ' + current.menu.name + ' · ' + (out ? 'sold out: ' : 'back on: ') + (current.menu.items.filter(function (i) { return i.id === id; })[0] || {}).name), UI.render);
    },
    save: function (el) {
      var f = readForm();
      if (f.err) { UI.toast(f.err, 3500); return; }
      var brand = current.brand, id = el.getAttribute('data-id'), menu = current.menu;
      if (!id && !pics) { UI.toast('Take the photo first.', 3000); return; }
      var clash = menu.items.filter(function (i) { return i.id !== id && i.name.toLowerCase() === f.name.toLowerCase(); })[0];
      if (clash) { UI.toast('There’s already a dish called ' + clash.name + '.', 3500); return; }
      var item = id ? menu.items.filter(function (i) { return i.id === id; })[0] : { id: newId(menu, f.name), img: '' };
      var msg = 'Menu (kitchen app): ' + menu.name + ' · ' + (id ? 'changed ' : 'new dish ') + f.name;
      var picStep = pics ? savePictures(brand, item, pics, msg) : Promise.resolve(item.img);
      saving(picStep.then(function (imgPath) {
        return updateJson(brand + '/menu.json', function (m) {
          var it = id ? m.items.filter(function (i) { return i.id === id; })[0] : null;
          if (id && !it) return 'That dish was removed on another phone.';
          if (!it) {
            it = { id: item.id, name: '', section: f.section, price: 0, desc: '', img: imgPath, allergens: [] };
            var firstDrink = m.items.map(function (i) { return i.kind; }).indexOf('drink');
            if (firstDrink < 0) m.items.push(it); else m.items.splice(firstDrink, 0, it);
          }
          apply(it, f);
          // An iPhone photo lands at a new path (.jpg): the link-card picture ("hero") follows it to the new picture.
          if (imgPath && m.hero && m.hero === it.img) m.hero = imgPath;
          if (imgPath) it.img = imgPath;
        }, msg);
      }), function () { UI.go('#/menu/' + brand); });
    },
    remove: function (el) {
      var id = el.getAttribute('data-id'), it = current.menu.items.filter(function (i) { return i.id === id; })[0], b = inBundle(current.menu, id);
      // The bundle's picture shows this dish, so taking it out would make that picture wrong.
      if (b) { UI.openSheet('<h2>' + esc(it.name) + ' is part of the ' + esc(b.name) + '</h2><p>It can’t be removed while the ' + esc(b.name) + ' includes it. Tap Sold out instead, and ask Victor to change the ' + esc(b.name) + '.</p>'); return; }
      UI.openSheet('<h2>Remove ' + esc(it ? it.name : 'this dish') + ' from the menu?</h2><p>Customers won’t see it any more. Its photo stays saved, so it can come back later.</p>' +
        '<div class="row-btns"><button class="btn warn wide" data-mact="removeyes" data-id="' + esc(id) + '">Yes, remove it</button></div>');
    },
    removeyes: function (el) {
      var brand = current.brand, id = el.getAttribute('data-id'), was = current.menu.items.filter(function (i) { return i.id === id; })[0];
      UI.closeSheet();
      saving(updateJson(brand + '/menu.json', function (m) {
        var it = m.items.filter(function (i) { return i.id === id; })[0];
        if (!it) return 'That dish is already gone.';
        if (inBundle(m, id)) return it.name + ' is part of the ' + inBundle(m, id).name + '. Tap Sold out instead.';
        m.items = m.items.filter(function (i) { return i.id !== id; });
        if (m.cover === id) delete m.cover;
      }, 'Menu (kitchen app): ' + current.menu.name + ' · removed ' + (was ? was.name : id)), function () { UI.go('#/menu/' + brand); });
    }
  };
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-mact]') : null;
    if (!el || !ACT[el.getAttribute('data-mact')]) return;
    e.preventDefault();
    ACT[el.getAttribute('data-mact')](el);
  });
  document.addEventListener('change', function (e) {
    if (e.target.id !== 'me-file' || !e.target.files || !e.target.files[0]) return;
    UI.toast('Getting the photo ready…', 8000);
    makePictures(e.target.files[0]).then(function (p) {
      pics = p;
      var prev = document.getElementById('me-prev');
      if (prev) { prev.src = p.preview; prev.hidden = false; }
      UI.toast('Photo ready. It’s saved when you tap Save.', 3000);
    }, function (err) { UI.toast(err.message || 'That photo could not be read.', 4000); });
  });

  window.KitchenMenu = { show: show };
})();
