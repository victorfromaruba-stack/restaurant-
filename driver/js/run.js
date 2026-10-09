/* One step: intro, pickup, each drop, then done. */
(function () {
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  Pidi.registerSW();
  Pidi.watchSignal();

  var main = document.getElementById("screen");
  var dock = document.getElementById("dock");
  var record = null;

  function bagCount(payload) {
    var ids = {};
    var n = 0;
    payload.drops.forEach(function (d) {
      if (!ids[d.restaurant]) { ids[d.restaurant] = 1; n += 1; }
    });
    return n;
  }

  function navRow(stop) {
    return Pidi.el("div", { class: "row" }, [
      Pidi.el("a", {
        class: "btn secondary",
        href: Pidi.mapsHref(stop),
        target: "_blank",
        rel: "noopener",
        "data-nav": "google",
        text: WORDS.google
      }),
      Pidi.el("a", {
        class: "btn secondary",
        href: Pidi.wazeHref(stop),
        target: "_blank",
        rel: "noopener",
        "data-nav": "waze",
        text: WORDS.waze
      })
    ]);
  }

  function contactRow(drop) {
    return Pidi.el("div", { class: "row" }, [
      Pidi.el("a", {
        class: "btn secondary",
        href: Pidi.telHref(drop.phone),
        "data-act": "call",
        text: WORDS.call
      }),
      Pidi.el("a", {
        class: "btn secondary",
        href: Pidi.waHref(drop.phone, Pidi.outsideText(drop)),
        target: "_blank",
        rel: "noopener",
        "data-act": "whatsapp",
        text: WORDS.whatsapp
      })
    ]);
  }

  function actions(stop) {
    return Pidi.el("div", { class: "actions" }, [navRow(stop), contactRow(stop)]);
  }

  function items(drop) {
    var name = Pidi.restaurantName(drop.restaurant, drop.restaurantName);
    var src = Pidi.logo(drop.restaurant);
    var img = src
      ? Pidi.el("img", { class: "logo", src: src, alt: name })
      : Pidi.el("div", { class: "logo-fallback", text: name });
    var list = Pidi.el("ul");
    drop.items.forEach(function (item) {
      var qty = item.qty ? String(item.qty) + " " : "";
      list.appendChild(Pidi.el("li", { text: qty + item.name }));
    });
    var text = Pidi.el("div", {}, [
      Pidi.el("p", { class: "who", text: name }),
      list
    ]);
    return Pidi.el("div", { class: "bag" }, [img, text]);
  }

  function moneyBox(drop) {
    var box = Pidi.el("div", { class: "money" });
    if (drop.pay === "transfer") {
      var waiting = drop.transfer !== "paid";
      box.appendChild(Pidi.el("p", { class: "kicker", text: waiting ? WORDS.awaiting : WORDS.paid }));
      box.appendChild(Pidi.el("p", { class: "figure", "data-money": "transfer", text: WORDS.noCash }));
      box.appendChild(Pidi.el("p", { class: "small", text: WORDS.orderWord + " " + Pidi.money(drop.total) + ". " + WORDS.includesFee }));
      return box;
    }
    var change = drop.paysWith - drop.total;
    box.appendChild(Pidi.el("p", { class: "kicker", text: WORDS.collect }));
    box.appendChild(Pidi.el("p", { class: "figure", "data-money": "collect", text: Pidi.money(drop.total) }));
    var payLine = Pidi.el("p", { class: "line" });
    payLine.appendChild(document.createTextNode(WORDS.paysWith + " "));
    payLine.appendChild(Pidi.el("span", { "data-money": "pays", text: Pidi.money(drop.paysWith) }));
    box.appendChild(payLine);
    var changeLine = Pidi.el("p", { class: "line" });
    if (change > 0) {
      changeLine.appendChild(document.createTextNode(WORDS.giveChange + " "));
      changeLine.appendChild(Pidi.el("span", { "data-money": "change", text: Pidi.money(change) }));
      changeLine.appendChild(document.createTextNode(" " + WORDS.changeWord));
    } else if (change === 0) {
      changeLine.textContent = WORDS.exact;
    } else {
      changeLine.textContent = WORDS.short + " " + Pidi.money(-change) + ". " + WORDS.askRest;
    }
    box.appendChild(changeLine);
    box.appendChild(Pidi.el("p", { class: "small", text: WORDS.includesFee }));
    return box;
  }

  function render() {
    Pidi.clear(main);
    Pidi.clear(dock);
    if (!record) {
      Pidi.toTop();
      return;
    }
    var p = record.payload;
    main.setAttribute("data-step", record.step);
    if (p.test) main.appendChild(Pidi.el("p", { class: "test-flag", text: WORDS.testRun }));

    if (record.step === "intro") {
      main.setAttribute("data-drop", "");
      main.appendChild(Pidi.el("h1", { text: WORDS.tonight }));
      var n = p.drops.length;
      main.appendChild(Pidi.el("p", { class: "addr", text: "1 pickup, then " + n + (n === 1 ? " drop" : " drops") }));
      p.drops.forEach(function (d, i) {
        main.appendChild(Pidi.el("p", { text: (i + 1) + ". " + d.name + " · " + (d.area || "") }));
      });
      dock.appendChild(Pidi.el("button", { class: "btn", type: "button", "data-action": "start", text: WORDS.startPickup }));
      Pidi.toTop();
      return;
    }

    if (record.step === "pickup") {
      main.setAttribute("data-drop", "");
      var bags = bagCount(p);
      main.appendChild(Pidi.el("h1", { text: WORDS.pickUp }));
      main.appendChild(Pidi.el("p", { class: "quiet", text: bags + " " + (bags === 1 ? WORDS.bag : WORDS.bags) }));
      var seen = {};
      p.drops.forEach(function (d) {
        if (seen[d.restaurant]) return;
        seen[d.restaurant] = 1;
        var merged = {
          restaurant: d.restaurant,
          restaurantName: d.restaurantName,
          items: []
        };
        p.drops.forEach(function (other) {
          if (other.restaurant === d.restaurant) {
            other.items.forEach(function (item) { merged.items.push(item); });
          }
        });
        main.appendChild(items(merged));
      });
      if (p.pickup && (p.pickup.address || (p.pickup.lat && p.pickup.lng))) {
        if (p.pickup.name) main.appendChild(Pidi.el("p", { class: "who", text: p.pickup.name }));
        if (p.pickup.address) main.appendChild(Pidi.el("p", { class: "addr", text: p.pickup.address }));
        main.appendChild(navRow(p.pickup));
      }
      dock.appendChild(Pidi.el("button", { class: "btn", type: "button", "data-action": "picked-up", text: WORDS.pickedUp }));
      Pidi.toTop();
      return;
    }

    if (record.step === "drop") {
      var i = record.dropIndex;
      var d = p.drops[i];
      main.setAttribute("data-drop", String(i));
      main.appendChild(Pidi.el("p", { class: "quiet", text: WORDS.drop + " " + (i + 1) + " " + WORDS.of + " " + p.drops.length }));
      main.appendChild(Pidi.el("h1", { text: d.name }));
      if (d.area) main.appendChild(Pidi.el("p", { class: "place", text: d.area }));
      main.appendChild(moneyBox(d));
      main.appendChild(actions(d));
      main.appendChild(Pidi.el("p", { class: "addr", text: d.address }));
      if (d.note) main.appendChild(Pidi.el("p", { class: "note", text: d.note }));
      main.appendChild(items(d));
      dock.appendChild(Pidi.el("button", { class: "btn", type: "button", "data-action": "delivered", text: WORDS.delivered }));
      Pidi.toTop();
      return;
    }

    main.setAttribute("data-drop", "");
    var doneTitle = p.drops.length > 1 ? WORDS.bothDone : WORDS.oneDone;
    main.appendChild(Pidi.el("h1", { text: doneTitle }));
    var got = Pidi.cashCollected(record);
    main.appendChild(Pidi.el("p", { class: "quiet", text: WORDS.cashThisRun }));
    main.appendChild(Pidi.el("p", { class: "figure", style: "font-size:40px;font-weight:800;margin:0", text: Pidi.money(got) }));
    dock.appendChild(Pidi.el("a", { class: "btn", href: "cash.html", text: WORDS.countCash }));
    Pidi.toTop();
  }

  function fail(msg) {
    Pidi.clear(main);
    main.appendChild(Pidi.el("h1", { text: "Pidi" }));
    main.appendChild(Pidi.el("p", { text: msg || WORDS.damaged }));
    dock.appendChild(Pidi.el("a", { class: "btn", href: "index.html", text: "Home" }));
  }

  dock.addEventListener("click", function (ev) {
    var btn = ev.target.closest("button");
    if (!btn || !record) return;
    var action = btn.getAttribute("data-action");
    if (action === "start") {
      record = Pidi.updateRun(record.id, function (r) { r.step = "pickup"; });
      Pidi.wake();
      render();
    } else if (action === "picked-up") {
      record = Pidi.updateRun(record.id, function (r) {
        r.pickedUpAt = new Date().toISOString();
        r.step = "drop";
        r.dropIndex = 0;
      });
      render();
    } else if (action === "delivered") {
      record = Pidi.updateRun(record.id, function (r) {
        r.deliveredAt[r.dropIndex] = new Date().toISOString();
        if (r.dropIndex + 1 < r.payload.drops.length) {
          r.dropIndex += 1;
        } else {
          r.step = "done";
        }
      });
      render();
    }
  });

  function showId(id) {
    record = Pidi.getRun(id);
    if (!record) { fail(WORDS.damaged); return; }
    if (record.step === "pickup" || record.step === "drop") Pidi.wake();
    render();
  }

  var body = Pidi.hashBody();
  if (Pidi.isPayload(body)) {
    main.appendChild(Pidi.el("p", { text: WORDS.opening }));
    Pidi.decodeBody(body).then(function (payload) {
      var got = Pidi.intake(payload);
      if (got.error) { fail(got.error); return; }
      history.replaceState(null, "", "run.html#run=" + encodeURIComponent(got.record.id));
      record = got.record;
      render();
    }).catch(function () { fail(WORDS.damaged); });
    return;
  }
  if (body.indexOf("run=") === 0) {
    showId(decodeURIComponent(body.slice(4)));
    return;
  }
  fail("Open the link they sent you.");
})();
