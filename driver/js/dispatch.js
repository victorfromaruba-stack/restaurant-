/* Build a run link and send it on WhatsApp. No account, no server. */
(function () {
  Pidi.registerSW();
  Pidi.watchSignal();

  var main = document.getElementById("screen");
  var dock = document.getElementById("dock");

  function field(label, attrs) {
    var wrap = Pidi.el("label", { class: "field" });
    wrap.appendChild(Pidi.el("span", { text: label }));
    wrap.appendChild(Pidi.el("input", attrs));
    return wrap;
  }

  function selectRestaurant(id) {
    var sel = Pidi.el("select", { id: id });
    Pidi.RESTAURANTS.forEach(function (r) {
      sel.appendChild(Pidi.el("option", { value: r.id, text: r.name }));
    });
    sel.appendChild(Pidi.el("option", { value: "other", text: WORDS.another }));
    return sel;
  }

  function choice(id, options, current) {
    var box = Pidi.el("div", { class: "choice", id: id });
    options.forEach(function (opt) {
      var b = Pidi.el("button", { type: "button", "data-value": opt.value, text: opt.label });
      if (opt.value === current) b.className = "on";
      b.addEventListener("click", function () {
        Array.prototype.forEach.call(box.querySelectorAll("button"), function (x) { x.className = ""; });
        b.className = "on";
        box.dispatchEvent(new Event("change", { bubbles: true }));
      });
      box.appendChild(b);
    });
    return box;
  }

  function chosen(id) {
    var on = document.querySelector("#" + id + " button.on");
    return on ? on.getAttribute("data-value") : "";
  }

  function itemRow(name, qty) {
    var row = Pidi.el("div", { class: "item-row" });
    row.appendChild(Pidi.el("input", { class: "qty", inputmode: "numeric", value: qty || "1", "aria-label": "Qty" }));
    row.appendChild(Pidi.el("input", { class: "iname", value: name || "", "aria-label": "Item", placeholder: "Chicken fried rice" }));
    var x = Pidi.el("button", { class: "x", type: "button", "aria-label": "Remove", text: "×" });
    x.addEventListener("click", function () { row.remove(); });
    row.appendChild(x);
    return row;
  }

  function dropBlock(n) {
    var box = Pidi.el("div", { class: "section", id: "drop-" + n });
    box.appendChild(Pidi.el("h2", { text: "Drop " + n }));
    var restLabel = Pidi.el("label", { class: "field" });
    restLabel.appendChild(Pidi.el("span", { text: "Restaurant" }));
    restLabel.appendChild(selectRestaurant("rest-" + n));
    box.appendChild(restLabel);
    var other = field("Restaurant name", { id: "other-" + n, autocomplete: "off" });
    other.id = "other-wrap-" + n;
    other.hidden = true;
    box.appendChild(other);
    box.appendChild(field("Customer", { id: "name-" + n, autocomplete: "name" }));
    box.appendChild(field("Phone", { id: "phone-" + n, inputmode: "tel", autocomplete: "tel", placeholder: "297…" }));
    var areaLabel = Pidi.el("label", { class: "field" });
    areaLabel.appendChild(Pidi.el("span", { text: "Area" }));
    var area = Pidi.el("select", { id: "area-" + n });
    ["Noord", "Palm Beach", "Eagle Beach", "Oranjestad", "Paradera", "Santa Cruz", "Other"].forEach(function (a) {
      area.appendChild(Pidi.el("option", { value: a, text: a }));
    });
    areaLabel.appendChild(area);
    box.appendChild(areaLabel);
    box.appendChild(field("Address", { id: "address-" + n, autocomplete: "street-address" }));
    box.appendChild(field("Pin latitude", { id: "lat-" + n, inputmode: "decimal", placeholder: "12.5696" }));
    box.appendChild(field("Pin longitude", { id: "lng-" + n, inputmode: "decimal", placeholder: "-70.0310" }));
    box.appendChild(field("Note", { id: "note-" + n }));
    box.appendChild(Pidi.el("p", { class: "who", text: "Items" }));
    var items = Pidi.el("div", { id: "items-" + n });
    items.appendChild(itemRow("", "1"));
    box.appendChild(items);
    var add = Pidi.el("button", { class: "btn secondary", type: "button", text: "Add an item" });
    add.addEventListener("click", function () { items.appendChild(itemRow("", "1")); });
    box.appendChild(add);
    box.appendChild(Pidi.el("p", { class: "who", style: "margin-top:14px", text: "How will they pay?" }));
    box.appendChild(choice("pay-" + n, [
      { value: "cash", label: "Cash" },
      { value: "transfer", label: "Bank transfer" }
    ], "cash"));
    box.appendChild(field("Food total, florins", { id: "food-" + n, inputmode: "decimal", placeholder: "28.95" }));
    var pays = field("They pay with, florins", { id: "pays-" + n, inputmode: "decimal", placeholder: "50" });
    pays.id = "pays-wrap-" + n;
    box.appendChild(pays);
    var transfer = choice("transfer-" + n, [
      { value: "awaiting", label: "Awaiting transfer" },
      { value: "paid", label: "Paid" }
    ], "awaiting");
    transfer.hidden = true;
    box.appendChild(transfer);
    var total = Pidi.el("p", { id: "total-" + n, class: "addr" });
    box.appendChild(total);
    return box;
  }

  main.appendChild(Pidi.el("h1", { text: "Send a run" }));
  main.appendChild(Pidi.el("p", { text: "One pickup, then one or two drops. The link holds the order. Nothing is stored on a server." }));

  var pickup = Pidi.el("div", { class: "section" });
  pickup.appendChild(Pidi.el("h2", { text: "Pickup" }));
  pickup.appendChild(field("Place name", { id: "pickup-name", placeholder: "Filled from the restaurants if you leave it blank" }));
  pickup.appendChild(field("Address", { id: "pickup-address", placeholder: "Leave blank if the driver already knows it" }));
  pickup.appendChild(field("Pin latitude", { id: "pickup-lat", inputmode: "decimal" }));
  pickup.appendChild(field("Pin longitude", { id: "pickup-lng", inputmode: "decimal" }));
  main.appendChild(pickup);

  main.appendChild(dropBlock(1));
  var second = Pidi.el("label", { class: "check" });
  var secondInput = Pidi.el("input", { type: "checkbox", id: "second" });
  second.appendChild(secondInput);
  second.appendChild(document.createTextNode(WORDS.secondDrop));
  main.appendChild(second);
  var drop2 = dropBlock(2);
  drop2.hidden = true;
  main.appendChild(drop2);

  main.appendChild(field("Send to this WhatsApp", { id: "driver-phone", inputmode: "tel", value: Pidi.ORDER_WHATSAPP }));
  var err = Pidi.el("p", { id: "form-err", class: "err", hidden: true });
  main.appendChild(err);
  var link = Pidi.el("textarea", { class: "linkbox", id: "run-link", readonly: "readonly" });
  main.appendChild(link);
  var copy = Pidi.el("button", { class: "btn secondary", type: "button", text: WORDS.copyLink, style: "margin-top:8px" });
  main.appendChild(copy);
  var open = Pidi.el("a", { class: "btn secondary", href: "run.html", text: WORDS.openHere, style: "margin-top:8px" });
  open.hidden = true;
  main.appendChild(open);

  function val(id) {
    var node = document.getElementById(id);
    return node ? node.value.trim() : "";
  }

  function wireDrop(n) {
    var rest = document.getElementById("rest-" + n);
    var pay = document.getElementById("pay-" + n);
    function sync() {
      document.getElementById("other-wrap-" + n).hidden = rest.value !== "other";
      var isCash = chosen("pay-" + n) !== "transfer";
      document.getElementById("pays-wrap-" + n).hidden = !isCash;
      document.getElementById("transfer-" + n).hidden = isCash;
      var food = Pidi.parseFlorin(val("food-" + n));
      var line = document.getElementById("total-" + n);
      if (food == null) { line.textContent = "ƒ5 delivery is added."; return; }
      var total = food + Pidi.FEE;
      line.textContent = "Food " + Pidi.money(food) + " + ƒ5 delivery = " + Pidi.money(total);
      if (food < Pidi.MIN_FOOD) {
        line.textContent = "Add " + Pidi.money(Pidi.MIN_FOOD - food) + " more. Delivery starts at ƒ24. " + line.textContent;
      }
    }
    rest.addEventListener("change", sync);
    pay.addEventListener("change", sync);
    document.getElementById("food-" + n).addEventListener("input", sync);
    sync();
  }
  wireDrop(1);
  wireDrop(2);
  secondInput.addEventListener("change", function () { drop2.hidden = !secondInput.checked; });

  function readItems(n) {
    var items = [];
    Array.prototype.forEach.call(document.querySelectorAll("#items-" + n + " .item-row"), function (row) {
      var name = row.querySelector(".iname").value.trim();
      var qty = parseInt(row.querySelector(".qty").value, 10);
      if (!name) return;
      items.push({ name: name, qty: qty > 0 ? qty : 1 });
    });
    return items;
  }

  function coord(id) {
    var s = val(id);
    if (!s) return "";
    if (!/^-?\d+(\.\d+)?$/.test(s)) return null;
    return s;
  }

  function readDrop(n) {
    var rest = val("rest-" + n);
    var otherName = val("other-" + n);
    var food = Pidi.parseFlorin(val("food-" + n));
    var pay = chosen("pay-" + n) === "transfer" ? "transfer" : "cash";
    var lat = coord("lat-" + n);
    var lng = coord("lng-" + n);
    var pinHalf = (lat === null || lng === null) || (!lat !== !lng);
    var drop = {
      name: val("name-" + n),
      phone: Pidi.digits(val("phone-" + n)),
      area: val("area-" + n),
      address: val("address-" + n),
      note: val("note-" + n),
      restaurant: rest === "other" ? slug(otherName) : rest,
      items: readItems(n),
      pay: pay,
      food: food,
      fee: Pidi.FEE,
      total: food == null ? null : food + Pidi.FEE
    };
    if (rest === "other") drop.restaurantName = otherName;
    if (lat && lng) { drop.lat = lat; drop.lng = lng; }
    if (pay === "cash") drop.paysWith = Pidi.parseFlorin(val("pays-" + n));
    else drop.transfer = chosen("transfer-" + n) === "paid" ? "paid" : "awaiting";
    drop._latBad = pinHalf;
    drop._food = food;
    return drop;
  }

  function slug(name) {
    var s = String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return s || "partner";
  }

  function problems(drops) {
    if (!drops.length) return "Add a drop.";
    if (drops.length > 2) return WORDS.tooMany;
    for (var i = 0; i < drops.length; i++) {
      var d = drops[i];
      var who = "Drop " + (i + 1) + ": ";
      if (!d.name) return who + "add the customer's name.";
      if (!d.phone || d.phone.length < 7) return who + "add the phone number.";
      if (!d.address) return who + "add the address.";
      if (d._latBad) return who + "the pin needs both latitude and longitude.";
      if (!d.items.length) return who + "add an item.";
      if (d.restaurantName === "") return who + "add the restaurant name.";
      if (d._food == null) return who + "add the food total.";
      if (d._food < Pidi.MIN_FOOD) return who + "add " + Pidi.money(Pidi.MIN_FOOD - d._food) + " more. Delivery starts at ƒ24.";
      if (d.pay === "cash" && (d.paysWith == null)) return who + "add what they pay with.";
    }
    var partner = drops.some(function (d) { return !!d.restaurantName; });
    if (partner && !val("pickup-address") && !(coord("pickup-lat") && coord("pickup-lng"))) {
      return "Add the pickup address for the other restaurant.";
    }
    var plat = coord("pickup-lat");
    var plng = coord("pickup-lng");
    if (plat === null || plng === null || (!plat !== !plng)) return "The pickup pin needs both latitude and longitude.";
    return "";
  }

  function newId() {
    var t = new Date(Date.now() - 4 * 3600000);
    var hh = String(t.getUTCHours()).padStart(2, "0");
    var mm = String(t.getUTCMinutes()).padStart(2, "0");
    var letters = "ABCDEFGHJKLMNPQRSTUVWXYZ";
    var a = letters[Math.floor(Math.random() * letters.length)];
    var b = letters[Math.floor(Math.random() * letters.length)];
    return hh + mm + "-" + a + b;
  }

  function buildObject() {
    var drops = [readDrop(1)];
    if (secondInput.checked) drops.push(readDrop(2));
    var msg = problems(drops);
    if (msg) return { error: msg };
    drops.forEach(function (d) {
      delete d._latBad;
      delete d._food;
    });
    var names = [];
    drops.forEach(function (d) {
      var name = d.restaurantName || Pidi.restaurantName(d.restaurant);
      if (names.indexOf(name) === -1) names.push(name);
    });
    var pickup = {
      name: val("pickup-name") || names.join(" and "),
      address: val("pickup-address")
    };
    var plat = coord("pickup-lat");
    var plng = coord("pickup-lng");
    if (plat && plng) { pickup.lat = plat; pickup.lng = plng; }
    return {
      run: { v: 1, id: newId(), pickup: pickup, drops: drops },
      drops: drops
    };
  }

  function showError(message) {
    err.hidden = !message;
    err.textContent = message || "";
  }

  function send() {
    var built = buildObject();
    if (built.error) { showError(built.error); return; }
    showError("");
    Pidi.encodeRun(built.run).then(function (body) {
      var url = Pidi.runUrl(body);
      if (url.length > Pidi.MAX_URL) {
        showError("This run is too long to send. Shorten a note or an address.");
        return;
      }
      link.value = url;
      open.href = "run.html#" + body;
      open.hidden = false;
      var lines = built.drops.map(function (d) { return d.name + ", " + d.area; }).join("\n");
      var text = "Pidi run\n" + lines + "\n" + url;
      var phone = Pidi.digits(val("driver-phone")) || Pidi.ORDER_WHATSAPP;
      location.href = "https://wa.me/" + phone + "?text=" + encodeURIComponent(text);
    }).catch(function () {
      showError(WORDS.damaged);
    });
  }

  copy.addEventListener("click", function () {
    var text = link.value;
    if (!text) {
      var built = buildObject();
      if (built.error) { showError(built.error); return; }
      Pidi.encodeRun(built.run).then(function (body) {
        link.value = Pidi.runUrl(body);
        open.href = "run.html#" + body;
        open.hidden = false;
        writeCopy(link.value);
      });
      return;
    }
    writeCopy(text);
  });

  function writeCopy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        copy.textContent = WORDS.copied;
      }).catch(function () { link.focus(); link.select(); });
    } else {
      link.focus();
      link.select();
    }
  }

  var go = Pidi.el("button", { class: "btn", type: "button", text: WORDS.sendDriver });
  go.addEventListener("click", send);
  dock.appendChild(go);
})();
