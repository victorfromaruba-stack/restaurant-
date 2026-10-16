/* One run from the database. Pickup, then each drop. */
import { clear, client, deliverAt, el, loadConfig, mapsHref, message, money, orderNo, savedToken, wazeHref } from "./client.js";

const main = document.getElementById("screen");
const dock = document.getElementById("dock");
let db = null;
let run = null;
let shown = "";
let locateTimer = null;

function toTop() {
  if (history.scrollRestoration) history.scrollRestoration = "manual";
  window.scrollTo(0, 0);
}

function deliveryNote(cents) {
  if (cents == null) return "Includes delivery";
  if (cents % 100 === 0) return "Includes ƒ" + (cents / 100) + " delivery";
  return "Includes " + money(cents) + " delivery";
}

function cashBox(stop) {
  const box = el("div", { class: "money" });
  if (stop.pay === "transfer") {
    box.appendChild(el("p", { class: "kicker", text: stop.transfer_status === "paid" ? "Paid by bank transfer" : "Awaiting transfer" }));
    box.appendChild(el("p", { class: "figure", text: "Don't collect cash" }));
    return box;
  }
  if (stop.pays_in_usd) {
    // The customer pays in US dollars: the driver tells the amount. No florin change line.
    box.appendChild(el("p", { class: "kicker", text: "Collect in US dollars" }));
    box.appendChild(el("p", { class: "figure", text: money(stop.total_cents) + " total" }));
    box.appendChild(el("p", { class: "small", text: "You tell the customer the amount in dollars. " + deliveryNote(stop.fee_cents) + "." }));
    return box;
  }
  box.appendChild(el("p", { class: "kicker", text: "Collect" }));
  box.appendChild(el("p", { class: "figure", text: money(stop.total_cents) }));
  if (stop.pays_with_cents != null) {
    box.appendChild(el("p", { class: "line", text: "Pays with " + money(stop.pays_with_cents) }));
    const change = stop.change_due_cents;
    box.appendChild(el("p", { class: "line", text: change >= 0 ? "Give " + money(change) + " change" : "Short " + money(-change) }));
  }
  box.appendChild(el("p", { class: "small", text: deliveryNote(stop.fee_cents) }));
  return box;
}

function actions(stop, withCall) {
  const rows = [
    el("div", { class: "row" }, [
      el("a", { class: "btn secondary", href: mapsHref(stop), target: "_blank", rel: "noopener", text: "Google Maps" }),
      el("a", { class: "btn secondary", href: wazeHref(stop), target: "_blank", rel: "noopener", text: "Waze" }),
    ]),
  ];
  if (withCall) {
    const phone = String(stop.phone || "").replace(/\D/g, "");
    rows.push(el("div", { class: "row" }, [
      el("a", { class: "btn secondary", href: "tel:+" + phone, text: "Call" }),
      el("a", {
        class: "btn secondary",
        href: "https://wa.me/" + phone + "?text=" + encodeURIComponent("Hi " + stop.name + ", your " + stop.restaurant + " order is outside."),
        target: "_blank",
        rel: "noopener",
        text: "WhatsApp",
      }),
    ]));
  }
  return el("div", { class: "actions" }, rows);
}

function paint() {
  const stops = (run && run.stops) || [];
  const pendingPickup = stops.some((stop) => stop.status === "assigned");
  const drop = stops.find((stop) => stop.status !== "delivered");
  const step = !run ? "empty" : pendingPickup ? "pickup" : drop ? "drop-" + drop.order_id : "done";
  if (step !== shown) {
    shown = step;
    toTop();
  }
  clear(main);
  clear(dock);
  if (!run) {
    main.appendChild(el("h1", { text: "No run right now" }));
    main.appendChild(el("p", { text: "Go back and wait for an offer." }));
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Back" }));
    return;
  }
  if (pendingPickup) {
    main.appendChild(el("h1", { text: "Pickup" }));
    const pickup = run.pickup || {};
    if (pickup.name) main.appendChild(el("p", { class: "place", text: pickup.name }));
    stops.forEach((stop) => {
      if (orderNo(stop)) main.appendChild(el("h2", { class: "stop-no", text: orderNo(stop) + (stop.name ? " · " + stop.name : "") }));
      const bags = stop.bags && stop.bags.length ? stop.bags : [{ restaurant: stop.restaurant, items: stop.items || [] }];
      bags.forEach((bag) => {
        main.appendChild(el("p", { class: "kicker", text: bag.restaurant }));
        (bag.items || []).forEach((item) => {
          main.appendChild(el("p", { text: item.qty + " × " + item.name }));
        });
      });
    });
    if (pickup.address || pickup.lat) main.appendChild(actions(pickup, false));
    const button = el("button", { class: "btn", type: "button", text: "Picked up" });
    button.addEventListener("click", pickupBags);
    dock.appendChild(button);
    return;
  }
  if (!drop) {
    main.appendChild(el("h1", { text: "Run finished" }));
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Back" }));
    return;
  }
  main.appendChild(el("p", { class: "quiet", text: "Drop " + drop.stop_index + " of " + stops.length + (orderNo(drop) ? " · " + orderNo(drop) : "") }));
  main.appendChild(el("h1", { text: drop.name }));
  if (drop.area) main.appendChild(el("p", { class: "place", text: drop.area }));
  if (deliverAt(drop)) main.appendChild(el("p", { class: "due", text: deliverAt(drop) }));
  main.appendChild(cashBox(drop));
  main.appendChild(actions(drop, true));
  if (drop.address) main.appendChild(el("p", { text: drop.address }));
  if (drop.note) main.appendChild(el("p", { text: drop.note }));
  (drop.items || []).forEach((item) => main.appendChild(el("p", { class: "small", text: item.qty + " × " + item.name })));
  const button = el("button", { class: "btn", type: "button", text: "Delivered" });
  button.addEventListener("click", () => delivered(drop));
  dock.appendChild(button);
}

async function load() {
  const { data, error } = await db.rpc("pidi_driver_run", { session: savedToken() });
  if (error) {
    clear(main);
    main.appendChild(el("p", { class: "err", text: message(error) }));
    return;
  }
  run = data;
  paint();
}

async function pickupBags() {
  const { error } = await db.rpc("pidi_driver_picked_up", { session: savedToken(), run_id: run.run_id });
  if (error) return;
  load();
}

async function delivered(stop) {
  const { error } = await db.rpc("pidi_driver_delivered", { session: savedToken(), order_id: stop.order_id });
  if (error) return;
  load();
}

function sendLocation() {
  if (!navigator.geolocation || !run) return;
  navigator.geolocation.getCurrentPosition((pos) => {
    db.rpc("pidi_driver_location", {
      session: savedToken(),
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
    });
  });
}

loadConfig().then((cfg) => {
  if (!cfg || !savedToken()) {
    location.href = "index.html";
    return;
  }
  db = client(cfg);
  load();
  setInterval(load, 8000);
  locateTimer = setInterval(sendLocation, 15000);
});
