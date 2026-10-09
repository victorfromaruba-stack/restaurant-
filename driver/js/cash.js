/* End of night: cash collected on delivered drops, compared with the count. */
(function () {
  Pidi.registerSW();
  Pidi.watchSignal();

  var main = document.getElementById("screen");
  var dock = document.getElementById("dock");
  var runs = Pidi.tonightRuns();
  var collected = 0;
  var rows = [];

  runs.forEach(function (r) {
    r.payload.drops.forEach(function (d, i) {
      if (!r.deliveredAt || !r.deliveredAt[i]) return;
      var cash = d.pay === "cash";
      if (cash) collected += d.total;
      rows.push({ drop: d, cash: cash, cents: cash ? d.total : 0 });
    });
  });

  main.appendChild(Pidi.el("h1", { text: WORDS.endNight }));

  if (!rows.length) {
    main.appendChild(Pidi.el("p", { text: WORDS.noCashYet }));
    dock.appendChild(Pidi.el("a", { class: "btn secondary", href: "index.html", text: "Home" }));
    return;
  }

  main.appendChild(Pidi.el("p", { class: "quiet", text: WORDS.cashCollected }));
  main.appendChild(Pidi.el("p", {
    class: "figure",
    "data-total": "collected",
    style: "font-size:48px;font-weight:800;margin:0 0 8px",
    text: Pidi.money(collected)
  }));
  var result = Pidi.el("div", { id: "result" });
  main.appendChild(result);

  var list = Pidi.el("ul", { class: "list" });
  rows.forEach(function (row) {
    var place = Pidi.restaurantName(row.drop.restaurant, row.drop.restaurantName);
    var sub = row.cash
      ? place + " · " + Pidi.money(row.cents)
      : place + " · " + (row.drop.transfer === "paid" ? WORDS.paid : WORDS.awaiting) + " · " + WORDS.noCash;
    var li = Pidi.el("li");
    li.appendChild(document.createTextNode(row.drop.name));
    li.appendChild(Pidi.el("span", { class: "sub", text: sub }));
    list.appendChild(li);
  });
  main.appendChild(list);

  var label = Pidi.el("label", { class: "field" });
  label.appendChild(Pidi.el("span", { text: WORDS.youCounted }));
  var input = Pidi.el("input", {
    id: "counted",
    "data-field": "counted",
    inputmode: "decimal",
    autocomplete: "off",
    placeholder: "0.00"
  });
  label.appendChild(input);
  main.appendChild(label);

  function band(diff) {
    var abs = Math.abs(diff);
    if (abs < 900) return WORDS.smallDiff;
    if (abs <= 3600) return WORDS.checkDay;
    return WORDS.checkNow;
  }

  function compare() {
    Pidi.clear(result);
    window.scrollTo(0, 0);
    var cents = Pidi.parseFlorin(input.value);
    if (input.value.trim() === "") {
      result.appendChild(Pidi.el("p", { class: "err", text: WORDS.typeFlorins }));
      return;
    }
    if (cents == null) {
      result.appendChild(Pidi.el("p", { class: "err", text: WORDS.badNumber }));
      return;
    }
    var diff = cents - collected;
    if (diff === 0) {
      var good = Pidi.el("p", { class: "result-good", "data-result": "match" });
      good.appendChild(document.createTextNode(WORDS.matches + " Counted "));
      good.appendChild(Pidi.el("span", { "data-total": "counted", text: Pidi.money(cents) }));
      good.appendChild(document.createTextNode(". " + WORDS.cashCollected + " " + Pidi.money(collected) + "."));
      result.appendChild(good);
      return;
    }
    var bad = Pidi.el("p", {
      class: "result-bad",
      "data-result": diff > 0 ? "over" : "short"
    });
    bad.textContent = band(diff) + " " + WORDS.countedWord + " " + Pidi.money(cents) + ". " + WORDS.cashCollected + " " + Pidi.money(collected) + ".";
    result.appendChild(bad);
  }

  var btn = Pidi.el("button", { class: "btn", type: "button", text: WORDS.compare });
  btn.addEventListener("click", compare);
  dock.appendChild(btn);
  input.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") compare();
  });
})();
