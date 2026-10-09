/* Home: tonight's run, or a plain empty state. */
(function () {
  Pidi.registerSW();
  Pidi.watchSignal();

  var body = Pidi.hashBody();
  if (Pidi.isPayload(body)) {
    location.replace("run.html#" + body);
    return;
  }

  var main = document.getElementById("screen");
  var dock = document.getElementById("dock");
  var runs = Pidi.tonightRuns();
  var active = null;
  runs.forEach(function (r) {
    if (r.step !== "done") active = r;
  });

  var collected = 0;
  runs.forEach(function (r) { collected += Pidi.cashCollected(r); });

  if (active) {
    var names = active.payload.drops.map(function (d) { return d.name; }).join(", then ");
    main.appendChild(Pidi.el("h1", { text: WORDS.tonight }));
    main.appendChild(Pidi.el("p", { class: "addr", text: names }));
    main.appendChild(Pidi.el("p", { class: "quiet", text: active.payload.drops.length + " " + (active.payload.drops.length === 1 ? "drop" : "drops") }));
  } else {
    main.appendChild(Pidi.el("h1", { text: WORDS.noRun }));
    main.appendChild(Pidi.el("p", { text: WORDS.noRunMore }));
  }

  var facts = Pidi.el("p", { class: "facts" });
  facts.appendChild(Pidi.el("span", { text: WORDS.hours }));
  facts.appendChild(Pidi.el("span", { text: WORDS.payWays }));
  facts.appendChild(Pidi.el("span", { text: WORDS.twoDrops }));
  main.appendChild(facts);

  if (collected > 0) {
    main.appendChild(Pidi.el("p", { text: WORDS.cashCollected + " " + Pidi.money(collected) }));
  }

  var links = Pidi.el("div", { class: "links" });
  function link(href, text) {
    links.appendChild(Pidi.el("a", { class: "text-link", href: href, text: text }));
  }

  if (active) {
    dock.appendChild(Pidi.el("a", { class: "btn", href: "run.html#run=" + encodeURIComponent(active.id), text: WORDS.continueRun }));
    link("cash.html", WORDS.countCash);
    link("install/", WORDS.addHome);
  } else if (collected > 0) {
    dock.appendChild(Pidi.el("a", { class: "btn", href: "cash.html", text: WORDS.countCash }));
    link("install/", WORDS.addHome);
  } else {
    dock.appendChild(Pidi.el("a", { class: "btn", href: "install/", text: WORDS.addHome }));
    link("cash.html", WORDS.countCash);
  }
  link("dispatch.html", WORDS.sendRun);
  main.appendChild(links);
})();
