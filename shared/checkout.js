/* Checkout (checkout/): one step per screen, then the order goes straight in through the order database
   (Pidi.rpc "pidi_place_order", shared/pidi.js) and the customer lands on its status page (order/#t=<token>).
   Built on window.OrderApp, the API at the top of shared/order-app.js. Delivery only. No minimum order.
     1 where   when (as soon as possible while open, else a 15-minute time tonight) and where (area, address, an
               optional map pin from the phone)
     2 you     name and a phone number for the driver, kept on this phone for next time
     3 pay     cash (florins, with the note they'll hand over so the driver brings change, or US dollars) or bank transfer
     4 check   the dishes by restaurant, one delivery fee, the total, Place order
   Every screen word goes through tr() and into shared/lang/*.json. The order database answers errors as short codes
   (MIN_FOOD, BAD_ITEM:2, REST_CLOSED:taco-brava ...); each one becomes a sentence here, in the visitor's language.
   A retry sends the same client_token, so an order that went in before the connection dropped never goes in twice. */
(function () {
  "use strict";
  var A = null, tr = null, esc = null, keep = null;
  var main = document.getElementById("oa-main");
  var STEPS = ["where", "you", "pay", "check"];
  var TITLE = { where: "Where do we bring it?", you: "Who’s it for?", pay: "How will you pay?", check: "Check your order" };
  var TRY_KEY = "pidi.try.v1";        // the last Place order that may have gone in: {token, sig, at}
  var VISIT_KEY = "pidi.checkout.v1"; // this visit's choices: {when, loc, paysFor, at}
  var AREA_BOX = { lat: [12.38, 12.66], lng: [-70.1, -69.85] };   // Aruba, roughly: a pin outside it is a phone somewhere else
  var visit = { when: "", loc: null, paysFor: 0, at: 0 }, step = "", busy = false, error = null, tried = {}, stack = [];

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function m$(c) { return A.money(c, true); }
  function clean(s) { return String(s || "").trim().replace(/\s+/g, " "); }
  function digits(s) { return String(s || "").replace(/\D/g, ""); }
  function load(k) { try { return JSON.parse(sessionStorage.getItem(k)); } catch (e) { return null; } }
  function save(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: kept for this page */ } }
  function keepVisit() { visit.at = Date.now(); save(VISIT_KEY, visit); }
  function lastTry() { try { var t = JSON.parse(localStorage.getItem(TRY_KEY)); return t && t.token ? t : null; } catch (e) { return null; } }
  function setTry(t) { try { if (t) localStorage.setItem(TRY_KEY, JSON.stringify(t)); else localStorage.removeItem(TRY_KEY); } catch (e) { /* private mode */ } }

  /* ---------------------------------------------------------------- where the customer came from */
  function from() {
    var m = /[?&]from=([a-z0-9-]+)/.exec(location.search), b = m && m[1];
    var known = (A.site().brands || []).map(function (x) { return x.id; });
    if (b && known.indexOf(b) >= 0) return b;
    var ls = A.lines();
    return ls.length ? ls[0].b : "";
  }
  function menuHref() { var b = from(); return "../" + (b ? b + "/#o" : ""); }

  /* ---------------------------------------------------------------- when */
  /* the times a customer can pick: never the first half hour after opening (the first orders are still cooking),
     and while open never sooner than the usual delivery time (as soon as possible is quicker) */
  function times() {
    var now = Date.now(), open = A.canOrderNow(), max = A.eta().max || 60;
    return A.slots().filter(function (s) { return !s.early && (!open || Date.parse(s.iso) >= now + max * 60000); });
  }
  function slotFor(iso) { return times().filter(function (s) { return s.iso === iso; })[0] || null; }
  /* "asap", a time from times(), or "" (nothing picked yet, or the picked time has passed) */
  function when() {
    if (visit.when === "asap") return A.canOrderNow() ? "asap" : "";
    if (visit.when && slotFor(visit.when)) return visit.when;
    return "";
  }
  function whenText(w) {
    if (w === "asap") return tr("As soon as possible ({eta})", { eta: A.eta().text });
    var s = slotFor(w);
    return s ? (A.canOrderNow() ? tr("Later tonight, {time}", { time: s.label }) : tr("Pre-order for tonight, {time}", { time: s.label })) : "";
  }

  /* ---------------------------------------------------------------- what's done, what's missing */
  function total() { return A.total(); }
  function paysWith(d) { return d.paysWith && visit.paysFor === total() ? d.paysWith : null; }
  function missing(st) {
    var d = A.details(), out = {};
    if (st === "where") {
      if (!when()) out.when = true;
      if (!d.area) out.area = true;
      if (!clean(d.addr)) out.addr = true;
    } else if (st === "you") {
      if (!clean(d.name)) out.name = true;
      var n = digits(d.phone).length;
      if (n < 7 || n > 15) out.phone = true;
    } else if (st === "pay") {
      if (d.pay !== "cash" && d.pay !== "transfer") out.pay = true;
      else if (d.pay === "cash" && !d.usd && !(paysWith(d) >= total())) out.cash = true;
    }
    return out;
  }
  function done(st) { return !Object.keys(missing(st)).length; }
  function firstOpen() { for (var i = 0; i < 3; i++) if (!done(STEPS[i])) return STEPS[i]; return "check"; }

  /* ---------------------------------------------------------------- drawing */
  var ICON = {
    pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3" fill="currentColor"/></svg>',
    wa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm4.52 11.99c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.13-.15.17-.25.25-.42.08-.16.04-.31-.02-.43-.06-.13-.56-1.35-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.29Z"/></svg>'
  };
  function head(st) {
    var n = STEPS.indexOf(st) + 1;
    return '<div class="steps" aria-hidden="true">' + STEPS.map(function (x, i) { return "<i" + (i < n ? ' class="on"' : "") + "></i>"; }).join("") + "</div>" +
      '<p class="step__n">' + esc(tr("Step {n} of {all}", { n: n, all: STEPS.length })) + "</p>" +
      '<h1 class="step__t" tabindex="-1">' + esc(tr(TITLE[st])) + "</h1>";
  }
  function err(f, text) { return '<p class="field__err" id="ck-' + f + '-err">' + esc(text) + "</p>"; }
  function bad(f) { return tried[step] && missing(step)[f]; }
  function errAttrs(f, help) {
    var ids = (help ? [help] : []).concat(bad(f) ? ["ck-" + f + "-err"] : []);
    return (bad(f) ? ' aria-invalid="true"' : "") + (ids.length ? ' aria-describedby="' + ids.join(" ") + '"' : "");
  }
  function pick(name, value, on, title, sub, attrs) {
    return '<label class="pick"><input type="radio" name="' + name + '" value="' + esc(value) + '"' + (on ? " checked" : "") + (attrs || "") + ">" +
      '<span class="pick__b"><span class="pick__t">' + keep(title) + "</span>" + (sub ? '<span class="pick__s">' + keep(sub) + "</span>" : "") + "</span></label>";
  }
  function go(label, attrs) {
    return '<div class="app__go"><button type="button" class="btn btn--accent" data-next' + (attrs || "") + ">" + label + "</button></div>";
  }
  function problem() {
    if (!error) return "";
    return '<div class="note note--warn ck-err" role="alert"><p>' + keep(error.text) + "</p>" +
      (error.wa ? '<a class="btn btn--wa" href="' + esc(error.wa) + '" target="_blank" rel="noopener" data-wa>' + ICON.wa + "<span>" + esc(tr("Send this order on WhatsApp")) + "</span></a>" : "") +
      (error.edit ? '<a class="btn btn--line btn--sm" href="' + esc(menuHref()) + '">' + esc(tr("Change the order")) + "</a>" : "") + "</div>";
  }

  function whereHTML() {
    var d = A.details(), w = when(), open = A.canOrderNow(), ts = times(), st = A.shopStatus();
    var later = !!visit.when && visit.when !== "asap";   // "Later tonight" picked, with or without a time yet
    var html = head("where");
    if (open) {
      html += '<fieldset class="field picks' + (bad("when") && !later ? " is-bad" : "") + '" data-err="' + (later ? "asap" : "when") + '"><legend>' + esc(tr("When")) + "</legend>" +
        pick("ck-when", "asap", w === "asap", tr("As soon as possible"), A.eta().text, later ? "" : errAttrs("when")) +
        (ts.length ? pick("ck-when", "later", later, tr("Later tonight"), tr("Pick a time"), later ? "" : errAttrs("when")) : "") +
        err("when", tr("Pick when you want it.")) + "</fieldset>";
    } else if (ts.length) {
      html += '<p class="note note--warn">' + keep(tr("We’re closed now.") + " " + st.label + ". " + tr("Pick a time and it’s a pre-order: we start on it when we open.")) + "</p>";
    } else {
      html += '<p class="note note--warn">' + keep(tr("We’re closed now.") + " " + st.label + ".") + "</p>";
    }
    if (ts.length && (!open || later)) {
      html += '<fieldset class="field' + (bad("when") ? " is-bad" : "") + '" data-err="when"><legend>' + esc(tr(open ? "Pick a time" : "Pick a time tonight")) + "</legend>" +
        '<div class="times">' + ts.map(function (s) {
          return '<label class="time"><input type="radio" name="ck-time" value="' + esc(s.iso) + '"' + (w === s.iso ? " checked" : "") + errAttrs("when") + "><span>" + esc(s.label) + "</span></label>";
        }).join("") + "</div>" + err("when", tr("Pick a time.")) + "</fieldset>";
    }
    if (!open && !ts.length) return html + '<a class="btn btn--line" href="' + esc(menuHref()) + '">' + esc(tr("Back to the menu")) + "</a>";
    var areas = A.site().areas || [];
    html += '<fieldset class="field field--areas' + (bad("area") ? " is-bad" : "") + '" data-err="area"><legend>' + esc(tr("Delivery area")) + '</legend><div class="chips">' +
      areas.map(function (a) {
        return '<label class="chip"><input type="radio" name="ck-area" value="' + esc(a) + '"' + (d.area === a ? " checked" : "") + errAttrs("area") + "><span>" + esc(tr(a)) + "</span></label>";
      }).join("") + "</div>" + err("area", tr("Pick your area.")) +
      '<p class="field__help">' + keep(tr("Elsewhere?")) + ' <a class="ck-ask" href="' + esc(A.waLink("Hi! Do you deliver to my area? I’m in ")) + '" target="_blank" rel="noopener">' + esc(tr("Ask us on WhatsApp")) + "</a></p></fieldset>";
    html += '<div class="field' + (bad("addr") ? " is-bad" : "") + '" data-err="addr"><label class="field__l" for="ck-addr">' + esc(tr("Address or landmark")) + "</label>" +
      '<textarea id="ck-addr" data-d="addr" rows="2" maxlength="160" autocomplete="street-address"' + errAttrs("addr", "ck-addr-help") + ">" + esc(d.addr) + "</textarea>" +
      '<p class="field__help" id="ck-addr-help">' + esc(tr("Street and house number, or a landmark. House colour helps the driver.")) + "</p>" +
      err("addr", tr("Add an address for the driver.")) + "</div>";
    html += locHTML();
    return html + problem() + go(esc(tr("Continue")));
  }
  function locHTML() {
    if (!("geolocation" in navigator)) return "";
    if (visit.loc) {
      return '<div class="loc loc--on"><span class="loc__i">' + ICON.pin + '</span><p class="loc__t">' + esc(tr("Your location is added for the driver.")) + "</p>" +
        '<button type="button" class="link" data-loc-off>' + esc(tr("Remove")) + "</button></div>";
    }
    return '<div class="loc"><button type="button" class="btn btn--line btn--loc" data-loc>' + ICON.pin + "<span>" + esc(tr("Add my location for the driver")) + "</span></button>" +
      '<p class="field__help" data-loc-msg aria-live="polite">' + esc(tr("Optional. The address is enough.")) + "</p></div>";
  }

  function youHTML() {
    var d = A.details();
    return head("you") +
      '<div class="field' + (bad("name") ? " is-bad" : "") + '" data-err="name"><label class="field__l" for="ck-name">' + esc(tr("Name")) + "</label>" +
      '<input id="ck-name" data-d="name" type="text" maxlength="40" autocomplete="name" value="' + esc(d.name) + '"' + errAttrs("name") + ">" + err("name", tr("Add your name.")) + "</div>" +
      '<div class="field' + (bad("phone") ? " is-bad" : "") + '" data-err="phone"><label class="field__l" for="ck-phone">' + esc(tr("Phone number")) + "</label>" +
      '<input id="ck-phone" data-d="phone" type="tel" maxlength="20" autocomplete="tel" inputmode="tel" value="' + esc(d.phone) + '"' + errAttrs("phone", "ck-phone-help") + ">" +
      '<p class="field__help" id="ck-phone-help">' + esc(tr("The driver calls or WhatsApps you on this number if they can’t find you.")) + "</p>" +
      err("phone", tr("Add a phone number the driver can reach.")) + "</div>" +
      '<p class="ck-saved">' + esc(tr("Saved on this phone for next time. No account needed.")) + "</p>" +
      problem() + go(esc(tr("Continue")));
  }

  /* cash: the notes someone would hand over for this total (Aruba has ƒ10, ƒ25, ƒ50, ƒ100 and ƒ200 notes) */
  function notes(t) {
    var out = [];
    [1000, 2500, 5000, 10000, 20000].forEach(function (n) { var v = Math.ceil(t / n) * n; if (v > t && out.indexOf(v) < 0) out.push(v); });
    return out.sort(function (a, b) { return a - b; }).slice(0, 3);
  }
  function payHTML() {
    var d = A.details(), t = total(), pw = paysWith(d), payWith = A.site().payWith || ["Cash", "Bank transfer"];
    var html = head("pay") + '<p class="ck-total">' + esc(tr("Total")) + " <b>" + m$(t) + "</b></p>";
    var hasCash = payWith.some(function (p) { return /cash/i.test(p); }), hasBank = payWith.some(function (p) { return /bank|transfer/i.test(p); });
    html += '<fieldset class="field picks' + (bad("pay") ? " is-bad" : "") + '" data-err="pay"><legend class="sr">' + esc(tr("How will you pay?")) + "</legend>" +
      (hasCash ? pick("ck-pay", "cash", d.pay === "cash", tr("Cash"), tr("Florins or US dollars, to the driver"), errAttrs("pay")) : "") +
      (hasBank ? pick("ck-pay", "transfer", d.pay === "transfer", tr("Bank transfer"), "", errAttrs("pay")) : "") +
      err("pay", tr("Pick how you’ll pay.")) + "</fieldset>";
    if (d.pay === "cash") {
      html += '<fieldset class="field"><legend>' + esc(tr("Paying in")) + '</legend><div class="chips">' +
        '<label class="chip"><input type="radio" name="ck-cur" value="awg"' + (!d.usd ? " checked" : "") + "><span>" + esc(tr("Florins")) + "</span></label>" +
        '<label class="chip"><input type="radio" name="ck-cur" value="usd"' + (d.usd ? " checked" : "") + "><span>" + esc(tr("US dollars")) + "</span></label></div></fieldset>";
      if (d.usd) {
        html += '<p class="field__help ck-usd">' + esc(tr("The driver tells you the amount in US dollars at the door.")) + "</p>";
      } else {
        var picks = notes(t);
        html += '<div class="field' + (bad("cash") ? " is-bad" : "") + '" data-err="cash"><label class="field__l" for="ck-cash">' + esc(tr("I’ll pay with")) + "</label>" +
          '<div class="cash"><span class="cash__f" aria-hidden="true">ƒ</span><input id="ck-cash" type="text" inputmode="decimal" autocomplete="off" maxlength="8" value="' +
          (pw ? esc((pw / 100).toFixed(pw % 100 ? 2 : 0)) : "") + '"' + errAttrs("cash", "ck-cash-help") + "></div>" +
          '<div class="chips chips--cash">' + '<button type="button" class="chip chip--btn" data-cash="' + t + '">' + esc(tr("Exact amount")) + "</button>" +
          picks.map(function (v) { return '<button type="button" class="chip chip--btn" data-cash="' + v + '">ƒ' + (v / 100) + "</button>"; }).join("") + "</div>" +
          '<p class="field__help" id="ck-cash-help" data-change aria-live="polite">' + changeText(pw, t) + "</p>" +
          err("cash", tr("That’s less than the total, {total}.", { total: A.money(t) })) + "</div>";
      }
    } else if (d.pay === "transfer") {
      html += transferHTML(t);
    }
    return html + problem() + go(esc(tr("Continue")));
  }
  function changeText(pw, t) {
    if (!pw || pw < t) return esc(tr("So the driver brings the right change."));
    if (pw === t) return esc(tr("No change needed."));
    return esc(tr("The driver brings {change} change.", { change: A.money(pw - t) }));
  }
  /* site.json "transfer": {"bank", "name", "account"} shows the details here; without it, they come once the order is confirmed */
  function transferHTML(t) {
    var x = A.site().transfer;
    if (x && x.account) {
      return '<div class="bank"><p>' + esc(tr("Send {total} to:", { total: A.money(t) })) + "</p><dl>" +
        (x.bank ? "<div><dt>" + esc(tr("Bank")) + "</dt><dd>" + esc(x.bank) + "</dd></div>" : "") +
        (x.name ? "<div><dt>" + esc(tr("Name")) + "</dt><dd>" + esc(x.name) + "</dd></div>" : "") +
        "<div><dt>" + esc(tr("Account")) + "</dt><dd>" + esc(x.account) + "</dd></div></dl>" +
        "<p>" + esc(tr("Put your order number in the description. You see it on the next screen.")) + "</p></div>";
    }
    return '<p class="field__help ck-usd">' + esc(tr("We send the bank details on WhatsApp when we confirm.")) + "</p>";
  }

  function payText(d) {
    if (d.pay === "transfer") return tr("Bank transfer");
    if (d.usd) return tr("Cash in US dollars");
    var pw = paysWith(d), t = total();
    return pw > t ? tr("Cash: you pay with {amount}, {change} change", { amount: A.money(pw), change: A.money(pw - t) }) : tr("Cash, the exact amount");
  }
  function linesHTML() {
    var ls = A.lines(), groups = [], seen = {};
    ls.forEach(function (l) {
      var key = l.drink ? "~drinks" : l.b;
      if (!seen[key]) { seen[key] = { t: l.drink ? tr("Drinks") : l.brand, lines: [] }; groups.push(seen[key]); }
      seen[key].lines.push(l);
    });
    groups.sort(function (a, b) { return (a.t === tr("Drinks")) - (b.t === tr("Drinks")); });
    if (groups.length === 2 && groups[1].t === tr("Drinks") && ls.every(function (l) { return l.drink || l.b === ls[0].b; })) {
      groups = [{ t: groups[0].t, lines: groups[0].lines.concat(groups[1].lines) }];   // one restaurant: its cans go with it
    }
    return groups.map(function (g) {
      return '<h2 class="lines__brand">' + esc(g.t) + '</h2><ul class="lines">' + g.lines.map(function (l) {
        // a small picture per line, so the order can be checked at a glance: the can for a drink, the restaurant's mark for a dish shown without one
        var menu = A.menu(l.b), item = menu && menu.byId[l.id];
        var pic = l.img ? '<img class="line__pic" src="' + esc(l.img) + '" alt="" width="360" height="360" loading="lazy" decoding="async">'
          : l.drink && item && item.img ? '<img class="line__pic line__pic--can" src="../' + esc(item.img) + '" alt="" width="360" height="360" loading="lazy" decoding="async">'
          : menu && menu.mark ? '<img class="line__pic line__pic--mark" src="../' + esc(menu.mark) + '" alt="" width="192" height="192" loading="lazy" decoding="async">' : "";
        return '<li class="line">' + pic + '<div class="line__main"><p class="line__n"><span class="line__q">' + l.q + " ×</span> <span lang=\"en\">" + keep(l.title) + "</span></p>" +
          (l.opts.length ? '<p class="line__d">' + esc(l.opts.join(" · ")) + "</p>" : "") +
          (l.soldOut ? '<p class="line__d line__d--warn">' + esc(tr("Can’t be ordered right now. Please remove.")) + "</p>" : "") +
          '</div><p class="line__t">' + m$(l.p * l.q) + "</p></li>";
      }).join("") + "</ul>";
    }).join("");
  }
  function checkHTML() {
    var d = A.details(), w = when(), ls = A.lines(), out = ls.some(function (l) { return l.soldOut; });
    var brands = []; ls.forEach(function (l) { if (!l.drink && brands.indexOf(l.b) < 0) brands.push(l.b); });
    var html = head("check");
    if (w && w !== "asap") html += '<p class="note note--warn">' + esc(whenText(w)) + "</p>";
    html += linesHTML() + '<a class="link ck-edit" href="' + esc(menuHref()) + '">' + esc(tr("Change the order")) + "</a>";
    html += '<dl class="recap">' +
      recap("where", tr("When"), whenText(w)) +
      recap("where", tr("Deliver to"), tr(d.area) + ", " + clean(d.addr) + (visit.loc ? " · " + tr("location added") : "")) +
      recap("you", tr("Name and phone"), clean(d.name) + ", " + clean(d.phone)) +
      recap("pay", tr("Pay"), payText(d)) + "</dl>";
    html += '<div class="field"><label class="field__l" for="ck-note">' + esc(tr("Note")) + " <em>" + esc(tr("optional")) + "</em></label>" +
      '<textarea id="ck-note" data-d="note" rows="2" maxlength="160" placeholder="' + esc(tr("Allergies, gate code")) + '">' + esc(d.note) + "</textarea></div>";
    if (brands.length > 1) {
      html += '<p class="order__mix">' + keep(tr("Order from several restaurants at once.")) + " <b>" + keep(tr("You pay {fee} delivery once.", { fee: "ƒ" + (A.site().deliveryFee / 100) })) + "</b></p>";
    }
    html += '<dl class="sum"><div><dt>' + esc(tr("Food")) + "</dt><dd>" + m$(A.food()) + "</dd></div>" +
      "<div><dt>" + esc(tr("Delivery")) + "</dt><dd>" + m$(A.fee()) + "</dd></div>" +
      '<div class="sum__total"><dt>' + esc(tr("Total")) + "</dt><dd>" + m$(total()) + "</dd></div></dl>";
    if (out) html += '<p class="note note--warn">' + esc(tr("Remove the dishes we can’t take right now first")) + "</p>";
    html += problem();
    var label = busy ? "<span>" + esc(tr("Placing your order…")) + "</span>"
      : "<span>" + esc(tr("Place order")) + '</span><span class="btn__total">' + m$(total()) + "</span>";
    return html + go(label, (busy || out ? " disabled" : "") + (busy ? ' aria-busy="true"' : "") + " data-place");
  }
  function recap(st, label, text) {
    return "<div><dt>" + esc(label) + "</dt><dd>" + keep(text) + '</dd><dd class="recap__go"><button type="button" class="link" data-goto="' + st + '" aria-label="' +
      esc(tr("Change: {what}", { what: label })) + '">' + esc(tr("Change")) + "</button></dd></div>";
  }
  function emptyHTML() {
    return '<div class="empty"><p class="empty__t">' + esc(tr("Your order is empty")) + "</p><p>" + esc(tr("Tap + on any dish.")) + "</p>" +
      '<a class="btn btn--accent" href="../">' + esc(tr("All restaurants")) + "</a></div>";
  }
  function offHTML() {
    return '<div class="empty"><p class="empty__t">' + esc(tr("Checkout")) + "</p><p>" + esc(tr("Orders go in on WhatsApp right now. Your order is still in the bag.")) + "</p>" +
      '<a class="btn btn--accent" href="' + esc(menuHref()) + '">' + esc(tr("Back to the menu")) + "</a></div>";
  }

  function render(focus) {
    var html;
    if (A.ordering() !== "app") html = offHTML();
    else if (!A.lines().length) html = emptyHTML();
    else html = { where: whereHTML, you: youHTML, pay: payHTML, check: checkHTML }[step]();
    main.innerHTML = html;
    var back = $("[data-oa-back]");
    if (back) {
      back.setAttribute("href", stack.length ? "#" + stack[stack.length - 1] : menuHref());
      back.setAttribute("aria-label", tr(stack.length ? "Back" : "Back to the menu"));
    }
    if (focus) {
      window.scrollTo(0, 0);
      var h = $(".step__t", main) || $(".empty__t", main);
      if (h && h.focus) h.focus({ preventScroll: true });
    }
  }

  /* ---------------------------------------------------------------- moving between steps */
  function show(st, push) {
    if (STEPS.indexOf(st) < 0) st = firstOpen();
    // a later step only once the ones before it are done
    for (var i = 0; i < STEPS.indexOf(st); i++) if (!done(STEPS[i])) { st = STEPS[i]; break; }
    if (push && step && step !== st) stack.push(step);
    step = st;
    error = null;
    var t = document.getElementById("oa-toast"); if (t) t.hidden = true;   // "Fill in the missing details" was about the last step
    if (location.hash !== "#" + st) {
      try { history[push ? "pushState" : "replaceState"](null, "", location.pathname + location.search + "#" + st); } catch (e) { location.hash = st; }
    }
    render(true);
  }
  function next() {
    if (!done(step)) {
      tried[step] = true;
      render(false);
      var first = $(".is-bad", main);
      if (first) {
        first.scrollIntoView({ behavior: "smooth", block: "center" });
        var inp = $("input:checked", first) || $("input,textarea", first);
        if (inp) inp.focus({ preventScroll: true });
      }
      A.toast(tr("Fill in the missing details"));
      return;
    }
    var at = STEPS.indexOf(step);
    var to = STEPS.slice(at + 1).filter(function (s) { return !done(s) || s === "check"; })[0] || "check";
    show(to, true);
  }
  window.addEventListener("popstate", function () {
    var st = location.hash.slice(1);
    if (stack.length && stack[stack.length - 1] === st) stack.pop();
    show(st, false);
  });

  /* ---------------------------------------------------------------- taps and typing */
  main.addEventListener("click", function (e) {
    var t = e.target;
    if (t.closest("[data-place]")) { place(); return; }
    if (t.closest("[data-next]")) { next(); return; }
    var g = t.closest("[data-goto]");
    if (g) { show(g.getAttribute("data-goto"), true); return; }
    var c = t.closest("[data-cash]");
    if (c) { setCash(+c.getAttribute("data-cash")); render(false); var i = $("#ck-cash"); if (i) i.focus({ preventScroll: true }); return; }
    if (t.closest("[data-loc]")) { locate(); return; }
    if (t.closest("[data-loc-off]")) { visit.loc = null; keepVisit(); render(false); return; }
  });
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-oa-back]");
    if (b && stack.length) { e.preventDefault(); history.back(); }
  });
  main.addEventListener("change", function (e) {
    var t = e.target;
    if (t.name === "ck-when") { visit.when = t.value === "asap" ? "asap" : (when() && when() !== "asap" ? when() : "later"); keepVisit(); render(false); }
    else if (t.name === "ck-time") { visit.when = t.value; keepVisit(); render(false); }
    else if (t.name === "ck-area") { A.saveDetails({ area: t.value }); render(false); }
    else if (t.name === "ck-pay") { A.saveDetails({ pay: t.value }); render(false); }
    else if (t.name === "ck-cur") { A.saveDetails({ usd: t.value === "usd" }); render(false); }
  });
  main.addEventListener("input", function (e) {
    var t = e.target, f = t.getAttribute("data-d");
    if (f) {
      var p = {}; p[f] = t.value; A.saveDetails(p);
      var field = t.closest("[data-err]");
      if (field && field.classList.contains("is-bad") && !missing(step)[field.getAttribute("data-err")]) unbad(field);
      return;
    }
    if (t.id === "ck-cash") {
      var v = parseFloat(String(t.value).replace(",", ".").replace(/[^\d.]/g, ""));
      setCash(isFinite(v) && v > 0 ? Math.round(v * 100) : null);
      var ch = $("[data-change]", main); if (ch) ch.innerHTML = changeText(paysWith(A.details()), total());
      var cf = t.closest("[data-err]");
      if (cf && cf.classList.contains("is-bad") && !missing("pay").cash) unbad(cf);
    }
  });
  function unbad(field) {
    field.classList.remove("is-bad");
    $$("[aria-invalid]", field).forEach(function (n) { n.removeAttribute("aria-invalid"); });
  }
  function setCash(c) { A.saveDetails({ paysWith: c }); visit.paysFor = total(); keepVisit(); }

  /* the phone's own location, as a map pin for the driver: optional, and only when asked */
  function locate() {
    var msg = $("[data-loc-msg]", main), btn = $("[data-loc]", main);
    if (btn) { btn.disabled = true; btn.setAttribute("aria-busy", "true"); }
    if (msg) msg.textContent = tr("Finding you…");
    navigator.geolocation.getCurrentPosition(function (p) {
      var lat = p.coords.latitude, lng = p.coords.longitude;
      if (lat < AREA_BOX.lat[0] || lat > AREA_BOX.lat[1] || lng < AREA_BOX.lng[0] || lng > AREA_BOX.lng[1]) {
        if (btn) { btn.disabled = false; btn.removeAttribute("aria-busy"); }
        if (msg) msg.textContent = tr("That location isn’t in Aruba, so we left it out. The address is enough.");
        return;
      }
      visit.loc = { lat: lat.toFixed(6), lng: lng.toFixed(6) };
      keepVisit();
      render(false);
    }, function () {
      if (btn) { btn.disabled = false; btn.removeAttribute("aria-busy"); }
      if (msg) msg.textContent = tr("We couldn’t get your location. The address is enough.");
    }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 });
  }

  /* ---------------------------------------------------------------- placing the order */
  function payload(token) {
    var d = A.details(), w = when();
    var p = { client_token: token, name: clean(d.name), phone: clean(d.phone), area: d.area, address: clean(d.addr), note: clean(d.note),
      // each line by its menu id: the order database works out the price itself (the phone's price goes along, and
      // the answer says "repriced" when they differ)
      items: A.lines().map(function (l) { return { restaurant: l.b, id: l.id, name: l.name, qty: l.q, price_cents: l.p }; }), pay: d.pay };
    if (d.pay === "cash") { if (d.usd) p.pays_in_usd = true; else p.pays_with_cents = paysWith(d); }
    if (visit.loc) { p.lat = visit.loc.lat; p.lng = visit.loc.lng; }
    if (w && w !== "asap") p.due_at = w;
    return p;
  }
  function sig(p) { var c = JSON.parse(JSON.stringify(p)); delete c.client_token; return JSON.stringify(c); }
  function newToken() {
    try { if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); } catch (e) { /* older phone */ }
    var s = ""; for (var i = 0; i < 32; i++) s += Math.floor(Math.random() * 16).toString(16);
    return s;
  }
  /* The token for this Place order. The same order sent again keeps its token: if the first try went in, the database
     answers with that order instead of making a second one. A changed order gets a new token, but first we ask whether
     the earlier try went in after all (pidi_find_order), so it isn't followed by a second, different order. */
  function tokenFor(p) {
    var t = lastTry(), s = sig(p);
    if (t && t.sig === s && Date.now() - t.at < 6 * 3600e3) return Promise.resolve({ token: t.token });
    if (!t || Date.now() - t.at >= 6 * 3600e3) return Promise.resolve({ token: newToken() });
    return window.Pidi.rpc("pidi_find_order", { client_token: t.token }).then(function (found) {
      if (found && found.public_token) return { token: t.token, earlier: found };
      return { token: newToken() };
    });
  }
  function place() {
    if (busy) return;
    for (var i = 0; i < 3; i++) if (!done(STEPS[i])) {
      var stopped = STEPS[i] === "where" && visit.when === "asap" && !A.canOrderNow(), passed = STEPS[i] === "where" && visit.when && !when();
      if (stopped || passed) { visit.when = ""; keepVisit(); }
      show(STEPS[i], true);
      error = { text: stopped ? tr("We just stopped taking orders for right now. Pick a time for later.")
        : passed ? tr("That time has passed. Pick a new time.") : tr("Fill in the missing details") };
      render(false);
      return;
    }
    if (A.lines().some(function (l) { return l.soldOut; })) { A.toast(tr("Remove the dishes we can’t take right now first")); return; }
    if (!window.Pidi) { error = fault({ offline: true }); render(false); return; }
    busy = true; error = null; render(false);
    var p = payload("");
    tokenFor(p).then(function (r) {
      if (r.earlier) return { res: r.earlier, earlier: true };
      p.client_token = r.token;
      setTry({ token: r.token, sig: sig(p), at: Date.now() });
      return window.Pidi.rpc("pidi_place_order", { payload: p }).then(function (res) { return { res: res }; });
    }).then(function (r) {
      var res = r.res;
      if (!res || !res.public_token) throw new Error("NO_ANSWER");
      setTry(null);
      A.rememberOrder(res);
      A.clear();
      try { sessionStorage.removeItem(VISIT_KEY); } catch (e) { /* private mode */ }
      location.replace("../order/#t=" + encodeURIComponent(res.public_token) + (r.earlier ? "&earlier=1" : "") + (res.repriced ? "&repriced=1" : ""));
    }).catch(function (e) {
      busy = false;
      error = fault(e);
      if (error.drop) setTry(null);
      if (error.step && error.step !== step) { var keepErr = error; show(error.step, true); error = keepErr; }
      render(false);
      var n = $(".ck-err", main);
      if (n) n.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }
  /* each answer from the order database, as a sentence in the visitor's language: {text, step (where to fix it),
     wa (a WhatsApp link with the whole order typed out), edit (a way back to change the dishes), drop (forget the token)} */
  function fault(e) {
    var code = String((e && e.message) || ""), m = /^([A-Z_]+)(?::(.*))?$/.exec(code), c = m ? m[1] : "", arg = m ? m[2] || "" : "";
    if (e && e.offline) return { text: tr("No connection. Check your internet and tap Place order again: it won’t go in twice.") };
    switch (c) {
      case "MISSING": return { text: tr("A detail is missing. Check your name, phone, area and address."), step: firstOpen() === "check" ? "where" : firstOpen(), drop: true };
      case "BAD_PHONE": return { text: tr("That phone number doesn’t look right. Check it and try again."), step: "you", drop: true };
      case "NO_ITEMS": return { text: tr("Your order is empty"), drop: true };
      case "BAD_ITEM":
        var l = A.lines()[+arg];
        return { text: l ? tr("{dish} changed on the menu. Take it out and add it again.", { dish: l.title }) : tr("A dish in your order changed on the menu. Take it out and add it again."), edit: true, drop: true };
      case "REST_CLOSED":
        var mm = A.menu(arg);
        return { text: tr("{restaurant} isn’t taking orders right now. Take its dishes out and try again.", { restaurant: mm ? mm.name : arg }), edit: true, drop: true };
      case "SOLD_OUT":
        var so = A.lines()[+arg];
        return { text: so ? tr("Sorry, {dish} just sold out tonight. Remove it to send the order.", { dish: so.title }) : tr("Sorry, a dish in your order just sold out tonight. Remove it to send the order."), edit: true, drop: true };
      case "MIN_FOOD": return { text: tr("Add a little more food to this order and try again."), edit: true, drop: true };
      case "CASH_SHORT": return { text: tr("The cash you pay with doesn\u2019t cover the whole total. Pick a bigger amount."), step: "pay", drop: true };
      case "BAD_PAY": return { text: tr("Pick how you’ll pay."), step: "pay", drop: true };
      case "BAD_PIN": visit.loc = null; keepVisit(); return { text: tr("Your location didn’t come through, so we took it out. Tap Place order again."), drop: true };
      case "BAD_TIME": visit.when = ""; keepVisit(); return { text: tr("That delivery time can’t be booked any more. Pick another time."), step: "where", drop: true };
      case "CLOSED": visit.when = ""; keepVisit(); return { text: tr("We just stopped taking orders for right now. Pick a time for later."), step: "where", drop: true };
      case "RATE_LIMIT": return { text: tr("This phone number already has orders waiting. To add something, message us on WhatsApp."), wa: A.waLink("Hi! I’d like to add to my order. "), drop: true };
      case "DELIVERY_ONLY": return { text: tr("We only deliver: there’s no pickup or dine-in."), drop: true };
    }
    if (/^No answer|^No connection/.test(code)) return { text: tr("No connection. Check your internet and tap Place order again: it won’t go in twice.") };
    return { text: tr("Something went wrong on our side. Try again in a minute, or send this order on WhatsApp."), wa: waOrder() };
  }
  /* the same order as a WhatsApp message (the way orders went in before the app), for when the database can't take it */
  function waOrder() {
    var d = A.details(), w = when(), s = slotFor(w);
    var ticketTime = !s ? "" : s.m === 0 ? "Midnight" : (function (m) { var h = Math.floor(m / 60) % 24, mm = m % 60; return (h % 12 || 12) + (mm ? ":" + String(mm).padStart(2, "0") : "") + " " + (h >= 12 ? "PM" : "AM"); })(s.m);
    // the ticket's own words, in English for the kitchen like every WhatsApp order: the pay line is "Cash" or
    // "Bank transfer", and what the driver needs to know goes in the note
    var cash = d.pay !== "cash" ? "" : d.usd ? "Pays in US dollars." : paysWith(d) ? "Pays with ƒ" + (paysWith(d) / 100).toFixed(2) + "." : "";
    A._set({ area: d.area, addr: clean(d.addr) + (visit.loc ? " (map pin " + visit.loc.lat + "," + visit.loc.lng + ")" : ""), name: clean(d.name),
      note: [clean(d.note), cash, d.phone ? "Phone " + clean(d.phone) + "." : ""].filter(Boolean).join(" "),
      pay: d.pay === "transfer" ? "Bank transfer" : "Cash", when: ticketTime });
    return A.checkoutLink().url;
  }

  /* ---------------------------------------------------------------- start */
  function start(app) {
    A = app; tr = A.tr; esc = A.esc; keep = A.keep;
    var v = load(VISIT_KEY);
    if (v && Date.now() - (v.at || 0) < 12 * 3600e3) visit = { when: v.when || "", loc: v.loc || null, paysFor: v.paysFor || 0, at: v.at };
    // while open, "as soon as possible" is picked to start with (a pre-order is always picked by hand)
    if (!visit.when && A.canOrderNow()) visit.when = "asap";
    show(location.hash.slice(1), false);
    A.onChange(function () { if (!busy) render(false); });
    setInterval(function () { if (!busy && document.activeElement === document.body) render(false); }, 60000);   // the clock moves on: times pass, ordering opens
  }
  function boot() {
    if (!window.OrderApp) return;
    OrderApp.ready.then(start, function () {
      main.innerHTML = '<p class="note note--warn">' + "The page didn’t load. Check your connection and refresh." + "</p>";
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
