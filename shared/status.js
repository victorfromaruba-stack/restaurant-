/* Order status (order/#t=<token>): where the order is, Received → Cooking → On the way → Delivered (or cancelled), with
   the time of each step, the dishes, the total, how they pay, when it should arrive and a WhatsApp link for questions.
   It asks the order database again about every 15 seconds while the page is open (Pidi.rpc "pidi_order_status"), and
   at once when the phone comes back to it. Under it, the other orders this phone placed (OrderApp.orders()).
   Built on window.OrderApp, the API at the top of shared/order-app.js. The token in the link is all it needs: the
   database never hands this page an address, a phone number or a note. */
(function () {
  "use strict";
  var A = null, tr = null, esc = null, keep = null;
  var main = document.getElementById("oa-main");
  var STAGES = [
    { label: "Received", from: ["new", "accepted"] },
    { label: "Cooking", from: ["cooking", "ready"] },
    { label: "On the way", from: ["assigned", "picked_up"] },
    { label: "Delivered", from: ["delivered"] }
  ];
  var DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var POLL = 15000;
  var WA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38a9.9 9.9 0 0 0 4.74 1.21h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm4.52 11.99c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.02-.38.11-.51.11-.11.25-.29.37-.43.13-.15.17-.25.25-.42.08-.16.04-.31-.02-.43-.06-.13-.56-1.35-.76-1.84-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.14-1.18-.06-.1-.22-.16-.47-.29Z"/></svg>';
  var token = "", earlier = false, repriced = false, order = null, missing = false, offline = false, timer = 0, asking = false;

  function m$(c) { return A.money(c, true); }
  /* Aruba wall clock for a moment from the database: minutes after Aruba midnight, its date and weekday */
  function aw(iso) {
    var ms = Date.parse(iso || "");
    if (!isFinite(ms)) return null;
    var off = (typeof A.site().utcOffset === "number" ? A.site().utcOffset : -4) * 3600e3, d = new Date(ms + off);
    return { mins: d.getUTCHours() * 60 + d.getUTCMinutes(), date: d.toISOString().slice(0, 10), day: d.getUTCDay(), ms: ms };
  }
  function at(iso, plus) { var t = aw(iso); return t ? A.clock(t.mins + (plus || 0)) : ""; }
  /* "12:05 AM" and "12:20 AM" read as "12:05" and "12:20 AM": the same half of the day is said once */
  function range(a, b) { var m = /(\s\S+)$/.exec(a); return m && / [AP]M$/.test(m[1].replace(/\s/, " ")) && b.slice(-m[1].length) === m[1] ? a.slice(0, -m[1].length) : a; }
  function stageOf(st) { for (var i = 0; i < STAGES.length; i++) if (STAGES[i].from.indexOf(st) >= 0) return i; return st === "cancelled" ? -1 : 0; }
  function when(o, i) {
    var ev = (o.events || []).filter(function (e) { return STAGES[i].from.indexOf(e.status) >= 0; })[0];
    return ev ? at(ev.at) : "";
  }
  function preorder(o) { return Date.parse(o.due_at || "") - Date.parse(o.created_at || "") > 5 * 60000; }
  function names(o) {
    var list = (o.restaurants || []).map(function (r) { var m = A.menu(r.slug); return m ? m.name : r.name; });
    return list.length ? A.listAnd(list) : o.restaurant || "";
  }
  function saved(t) { return A.orders().filter(function (x) { return x.t === t; })[0] || null; }

  /* ---------------------------------------------------------------- drawing */
  function topHTML(o) {
    var i = stageOf(o.status), done = o.status === "delivered", off = o.status === "cancelled";
    var big = off ? tr("Cancelled") : tr(STAGES[i].label);
    var line = off ? tr("This order was cancelled. If that’s news to you, WhatsApp us.")
      : done ? tr("Delivered at {time}. Danki.", { time: when(o, 3) || at(new Date().toISOString()) })
      : i === 2 ? tr("The driver has your order. Keep your phone close.")
      : i === 1 ? tr("Your order is being made right now.")
      : preorder(o) ? tr("{names} got your pre-order.", { names: names(o) })
      : tr("{names} got your order.", { names: names(o) });
    var eta = off || done ? "" : preorder(o) ? tr("Arrives around {time}", { time: at(o.due_at) })
      : (function (a, b) { return tr("Arrives between {from} and {to}", { from: range(a, b), to: b }); })(at(o.created_at, o.eta_min || A.eta().min), at(o.created_at, o.eta_max || A.eta().max));
    var head = [[o.night_no ? tr("Order {no}", { no: o.night_no }) : "", o.first_name ? tr("for {name}", { name: o.first_name }) : ""].filter(Boolean).join(" "),
      o.area ? tr(o.area) : ""].filter(Boolean).join(" \u00b7 ");
    return '<section class="st' + (off ? " st--off" : done ? " st--done" : "") + '" aria-live="polite">' +
      (head ? '<p class="st__k">' + esc(head) + "</p>" : "") +
      '<h1 class="st__t" tabindex="-1">' + esc(big) + "</h1>" +
      (eta ? '<p class="st__eta">' + keep(eta) + "</p>" : "") +
      '<p class="st__line">' + keep(line) + "</p>" + "</section>" +
      (repriced || o.repriced ? '<p class="note note--warn">' + keep(tr("A price changed since you added the dishes. The total below is what you pay.")) + "</p>" : "") +
      (earlier ? '<p class="note note--warn">' + keep(tr("Your order went in the first time, so we didn’t send it again. To change it, WhatsApp us.")) + "</p>" : "") +
      (off ? "" : trackHTML(o));
  }
  function trackHTML(o) {
    var now = stageOf(o.status);
    return '<ol class="track">' + STAGES.map(function (s, i) {
      var t = when(o, i), state = i < now || o.status === "delivered" ? "done" : i === now ? "now" : "todo";
      return '<li class="track__s is-' + state + '"' + (state === "now" ? ' aria-current="step"' : "") + '><span class="track__dot" aria-hidden="true"></span>' +
        '<span class="track__l">' + esc(tr(s.label)) + "</span>" + (t && state !== "todo" ? '<span class="track__t">' + esc(t) + "</span>" : "") + "</li>";
    }).join("") + "</ol>";
  }
  function itemsHTML(o) {
    var rec = saved(token), lines = rec && Array.isArray(rec.lines) ? rec.lines : [];
    var groups = [], by = {};
    (o.items || []).forEach(function (it) {
      var l = lines.filter(function (x) { return x.name === it.name && x.b === it.restaurant; })[0];
      var drink = l ? !!l.drink : / \(can\)$/.test(it.name);
      var key = drink ? "~" : it.restaurant;
      if (!by[key]) {
        var r = (o.restaurants || []).filter(function (x) { return x.slug === it.restaurant; })[0], m = A.menu(it.restaurant);
        // (the restaurant's own name from its menu, else the one the database gave)
        by[key] = { t: drink ? tr("Drinks") : m ? m.name : r ? r.name : it.restaurant, lines: [], drinks: drink };
        groups.push(by[key]);
      }
      by[key].lines.push({ it: it, l: l, b: it.restaurant, drink: drink });
    });
    groups.sort(function (a, b) { return a.drinks - b.drinks; });
    if (groups.length === 2 && groups[1].drinks) groups = [{ t: groups[0].t, lines: groups[0].lines.concat(groups[1].lines) }];   // one restaurant: its cans go with it
    return '<section class="st-sec" aria-labelledby="st-food"><h2 class="st-sec__t" id="st-food">' + esc(tr("Your food")) + "</h2>" +
      groups.map(function (g) {
        return '<h3 class="lines__brand">' + esc(g.t) + '</h3><ul class="lines">' + g.lines.map(function (x) {
          var parts = String(x.it.name).split(" · "), title = parts.shift();
          // its picture from the menu (by the dish's name, so it works for an order placed on another phone too); a
          // dish shown without its picture gets the restaurant's mark, the same as on its page
          var m = A.menu(x.b), item = m && ((x.l && m.byId[x.l.id]) || m.items.filter(function (i) { return i.name === title; })[0]);
          var pic = item && item.img && !item.hidePhoto ? (item.kind === "drink" || x.drink
              ? '<img class="line__pic line__pic--can" src="../' + esc(item.img) + '" alt="" width="360" height="360" loading="lazy" decoding="async">'
              : '<img class="line__pic" src="../' + esc(item.img.replace(/([^/]+)$/, "thumbs/$1")) + '" data-full="../' + esc(item.img) + '" alt="" width="360" height="360" loading="lazy" decoding="async">')
            : m && m.mark ? '<img class="line__pic line__pic--mark" src="../' + esc(m.mark) + '" alt="" width="192" height="192" loading="lazy" decoding="async">' : "";
          return '<li class="line">' + pic + '<div class="line__main"><p class="line__n"><span class="line__q">' + x.it.qty + " ×</span> <span lang=\"en\">" + keep(title) + "</span></p>" +
            (parts.length ? '<p class="line__d" lang="en">' + esc(parts.join(" · ")) + "</p>" : "") +
            '</div><p class="line__t">' + m$(x.it.qty * x.it.price_cents) + "</p></li>";
        }).join("") + "</ul>";
      }).join("") +
      '<dl class="sum"><div><dt>' + esc(tr("Food")) + "</dt><dd>" + m$(o.food_cents) + "</dd></div>" +
      "<div><dt>" + esc(tr("Delivery")) + "</dt><dd>" + m$(o.fee_cents) + "</dd></div>" +
      '<div class="sum__total"><dt>' + esc(tr("Total")) + "</dt><dd>" + m$(o.total_cents) + "</dd></div></dl></section>";
  }
  function payHTML(o) {
    var text, x = A.site().transfer;
    if (o.pay === "transfer") {
      if (o.transfer_status === "paid") text = tr("Bank transfer: received. Danki.");
      else if (x && x.account) {
        return '<div class="bank"><p>' + esc(tr("Bank transfer: send {total} to:", { total: A.money(o.total_cents) })) + "</p><dl>" +
          (x.bank ? "<div><dt>" + esc(tr("Bank")) + "</dt><dd>" + esc(x.bank) + "</dd></div>" : "") +
          (x.name ? "<div><dt>" + esc(tr("Name")) + "</dt><dd>" + esc(x.name) + "</dd></div>" : "") +
          "<div><dt>" + esc(tr("Account")) + "</dt><dd>" + esc(x.account) + "</dd></div>" +
          "<div><dt>" + esc(tr("Description")) + "</dt><dd>" + esc(tr("Order {no}", { no: o.night_no || "" })) + "</dd></div></dl></div>";
      } else text = tr("Bank transfer. We send the bank details on WhatsApp when we confirm.");
    } else if (o.pays_in_usd) text = tr("Cash in US dollars. The driver tells you the amount at the door.");
    else if (o.change_due_cents > 0) text = tr("Cash: you pay with {amount}, the driver brings {change} change.", { amount: A.money(o.pays_with_cents), change: A.money(o.change_due_cents) });
    else text = tr("Cash, the exact amount.");
    return '<p class="st-pay">' + keep(text) + "</p>";
  }
  function moreHTML(o) {
    var hi = "Hi! About my order" + (o.night_no ? " " + o.night_no : "") + (o.first_name ? " (" + o.first_name + ")" : "") + ": ";
    return '<section class="st-sec" aria-labelledby="st-pay"><h2 class="st-sec__t" id="st-pay">' + esc(tr("Pay")) + "</h2>" + payHTML(o) +
      '<a class="btn btn--wa st-wa" href="' + esc(A.waLink(hi)) + '" target="_blank" rel="noopener">' + WA + '<span>' +
      esc(tr("Questions about this order?")) + "</span></a></section>";
  }
  function listHTML(skip) {
    var list = A.orders().filter(function (o) { return o.t !== skip; });
    if (!list.length) return "";
    var today = aw(new Date().toISOString());
    return '<section class="st-sec" aria-labelledby="st-mine"><h2 class="st-sec__t" id="st-mine">' + esc(tr(skip ? "Your other orders" : "Your orders")) + '</h2><div class="mine-list">' +
      list.map(function (o) {
        var t = aw(new Date(o.at).toISOString()), day = t && today && t.date !== today.date ? tr(DAYS[t.day]) + " " : "";
        return '<a class="ord" href="#t=' + esc(encodeURIComponent(o.t)) + '"><span class="ord__t">' + esc((o.restaurants || []).join(", ")) + "</span>" +
          '<span class="ord__d">' + esc([o.no ? tr("Order {no}", { no: o.no }) : "", t ? day + A.clock(t.mins) : ""].filter(Boolean).join(" · ")) + "</span>" +
          '<span class="ord__p">' + m$(o.total_cents || 0) + "</span></a>";
      }).join("") + "</div></section>";
  }
  function render(focus) {
    var html;
    if (!token) {
      html = '<h1 class="st-t" tabindex="-1">' + esc(tr("Your orders")) + "</h1>" + (A.orders().length ? listHTML("") :
        '<div class="empty"><p>' + esc(tr("No orders on this phone yet.")) + '</p><a class="btn btn--accent" href="../">' + esc(tr("All restaurants")) + "</a></div>");
    } else if (missing) {
      html = '<h1 class="st-t" tabindex="-1">' + esc(tr("We can’t find this order")) + "</h1>" +
        '<p class="st-p">' + keep(tr("Check the link, or WhatsApp us and we’ll look it up.")) + "</p>" +
        '<a class="btn btn--wa" href="' + esc(A.waLink("Hi! I can’t find my order. ")) + '" target="_blank" rel="noopener">' + WA + "<span>" + esc(tr("WhatsApp us")) + "</span></a>" + listHTML(token);
    } else if (!order) {
      html = offline ? '<p class="note note--warn" role="status">' + esc(tr("No connection. We keep trying.")) + "</p>" : '<div class="oa-skel" aria-hidden="true"><div></div><div></div><div></div></div>';
    } else {
      html = topHTML(order) + (offline ? '<p class="note note--warn" role="status">' + esc(tr("No connection. We keep trying.")) + "</p>" : "") +
        itemsHTML(order) + moreHTML(order) + listHTML(token);
    }
    // only touch the page when something changed, so a screen reader doesn't read it all again every 15 seconds
    if (main._html !== html) { main._html = html; main.innerHTML = html; }
    if (focus) { window.scrollTo(0, 0); var h = main.querySelector("h1"); if (h) h.focus({ preventScroll: true }); }
  }

  /* ---------------------------------------------------------------- asking the database */
  function finished() { return order && (order.status === "delivered" || order.status === "cancelled"); }
  function ask(first) {
    clearTimeout(timer);
    if (!token || asking) return;
    if (!window.Pidi) { offline = true; render(first); return; }
    asking = true;
    var t = token;
    window.Pidi.rpc("pidi_order_status", { token: t }).then(function (o) {
      if (!o) throw new Error("NOT_FOUND");
      return o;
    }).then(function (o) {
      if (t !== token) return;
      order = o; missing = false; offline = false;
      // its restaurants' menus, for the dishes' pictures (an order opened from a link on another phone has none loaded)
      var need = (o.restaurants || []).map(function (r) { return r.slug; }).filter(function (b) { return b && !A.menu(b); });
      if (need.length) Promise.all(need.map(function (b) { return A.loadMenu(b).catch(function () { return null; }); })).then(function () { if (t === token) render(false); });
    }, function (e) {
      if (t !== token) return;
      if (/NOT_FOUND/.test(String(e && e.message))) missing = true;
      else offline = true;
    }).then(function () {
      asking = false;
      if (t !== token) return;
      render(first);
      if (!missing && !finished() && document.visibilityState !== "hidden") timer = setTimeout(ask, POLL);
    });
  }
  function readHash() {
    var p = {};
    location.hash.replace(/^#/, "").split("&").forEach(function (kv) { var i = kv.indexOf("="); if (i > 0) p[kv.slice(0, i)] = kv.slice(i + 1); });
    try { token = p.t ? decodeURIComponent(p.t) : ""; } catch (e) { token = ""; }
    earlier = p.earlier === "1";
    repriced = p.repriced === "1";
    order = null; missing = false; offline = false;
  }
  function start(app) {
    A = app; tr = A.tr; esc = A.esc; keep = A.keep;
    readHash();
    render(true);
    ask(true);
    window.addEventListener("hashchange", function () { readHash(); render(true); ask(true); });
    document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible" && !finished()) ask(false); });
  }
  function boot() {
    if (!window.OrderApp) return;
    OrderApp.ready.then(start, function () {
      main.innerHTML = '<p class="note note--warn">' + "The page didn’t load. Check your connection and refresh." + "</p>";
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
