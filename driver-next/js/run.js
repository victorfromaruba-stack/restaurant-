/* One run from the database. Pickup, then each drop.
   Part 2 preview: without signal the run stays on screen (this tab keeps its last copy), and Picked up /
   Delivered taps wait on the phone and go out in order when the signal is back. A tap the database refuses
   says why on screen (v2 said nothing). */
import { clear, client, deliverAt, el, isOffline, loadConfig, mapsHref, message, money, orderNo, savedToken, watchSignal, wazeHref } from "./client.js";

const main = document.getElementById("screen");
const dock = document.getElementById("dock");
const RUN_KEY = "pidi.v2.lastrun";   // the last run this tab saw, for a reload without signal
const OUT_KEY = "pidi.v2.outbox";    // taps made without signal, sent in order later
let db = null;
let run = null;
let shown = "";
let locateTimer = null;
let loadErr = "";
let tapErr = "";
let sending = false;

function readJson(key, fallback) {
  try { return JSON.parse(sessionStorage.getItem(key) || "null") || fallback; } catch (e) { return fallback; }
}
function outbox() { return readJson(OUT_KEY, []); }
function saveOutbox(list) {
  if (list.length) sessionStorage.setItem(OUT_KEY, JSON.stringify(list));
  else sessionStorage.removeItem(OUT_KEY);
}
/* The run as the driver left it: the database's copy with the taps still waiting on the phone applied. */
function withOutbox(r) {
  const list = outbox();
  if (!r || !list.length) return r;
  const copy = JSON.parse(JSON.stringify(r));
  list.forEach((t) => (copy.stops || []).forEach((s) => {
    if (t.fn === "pidi_driver_picked_up" && s.status === "assigned") s.status = "picked_up";
    if (t.fn === "pidi_driver_delivered" && s.order_id === t.args.order_id) s.status = "delivered";
  }));
  return copy;
}

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
    box.classList.add("is-transfer");
    box.appendChild(el("p", { class: "kicker", text: stop.transfer_status === "paid" ? "Paid by bank transfer" : "Awaiting transfer" }));
    box.appendChild(el("p", { class: "figure", text: "Don't collect cash" }));
    return box;
  }
  if (stop.pays_in_usd) {
    // The customer pays in US dollars: the driver tells the amount. No florin change line.
    box.classList.add("is-usd");
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
    box.appendChild(el("p", { class: "line change", text: change >= 0 ? "Give " + money(change) + " change" : "Short " + money(-change) }));
  }
  box.appendChild(el("p", { class: "small", text: deliveryNote(stop.fee_cents) }));
  return box;
}

function actions(stop, withCall) {
  const links = [
    el("a", { class: "btn secondary", href: mapsHref(stop), target: "_blank", rel: "noopener", text: "Google Maps" }),
    el("a", { class: "btn secondary", href: wazeHref(stop), target: "_blank", rel: "noopener", text: "Waze" }),
  ];
  if (withCall) {
    const phone = String(stop.phone || "").replace(/\D/g, "");
    links.push(el("a", { class: "btn secondary", href: "tel:+" + phone, text: "Call" }));
    links.push(el("a", {
      class: "btn secondary",
      href: "https://wa.me/" + phone + "?text=" + encodeURIComponent("Hi " + stop.name + ", your " + stop.restaurant + " order is outside."),
      target: "_blank",
      rel: "noopener",
      text: "WhatsApp",
    }));
  }
  return el("div", { class: "actions" }, links);
}

/* What went wrong or is still waiting, at the top of the screen. */
function notices() {
  const out = [];
  if (tapErr) out.push(el("p", { class: "err", role: "alert", text: tapErr }));
  if (loadErr) out.push(el("p", { class: "err", role: "alert", text: "Couldn't update the run: " + loadErr + " Trying again by itself." }));
  const waiting = outbox().length;
  if (waiting) out.push(el("p", { class: "pending", role: "status", text: waiting === 1 ? "1 tap saved on this phone. It sends when the signal is back." : waiting + " taps saved on this phone. They send when the signal is back." }));
  return out;
}

function bigButton(label, onTap) {
  const button = el("button", { class: "btn", type: "button", text: label });
  button.addEventListener("click", () => {
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = "Sending…";
    onTap();
  });
  return button;
}

function paint() {
  const now = withOutbox(run);
  const stops = (now && now.stops) || [];
  const pendingPickup = stops.some((stop) => stop.status === "assigned");
  const drop = stops.find((stop) => stop.status !== "delivered");
  const step = !now ? "empty" : pendingPickup ? "pickup" : drop ? "drop-" + drop.order_id : "done";
  if (step !== shown) {
    shown = step;
    toTop();
  }
  clear(main);
  clear(dock);
  main.setAttribute("data-step", step === "pickup" ? "pickup" : step === "done" || step === "empty" ? step : "drop");
  notices().forEach((n) => main.appendChild(n));
  if (!now) {
    main.appendChild(el("h1", { text: "No run right now" }));
    main.appendChild(el("p", { text: "Go back and wait for an offer." }));
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Back" }));
    return;
  }
  if (pendingPickup) {
    main.appendChild(el("h1", { text: "Pickup" }));
    const pickup = now.pickup || {};
    if (pickup.name) main.appendChild(el("p", { class: "place", text: pickup.name }));
    stops.forEach((stop) => {
      const slip = el("section", { class: "bagslip" });
      if (orderNo(stop)) slip.appendChild(el("h2", { class: "stop-no", text: orderNo(stop) + (stop.name ? " · " + stop.name : "") }));
      const bags = stop.bags && stop.bags.length ? stop.bags : [{ restaurant: stop.restaurant, items: stop.items || [] }];
      bags.forEach((bag) => {
        slip.appendChild(el("p", { class: "kicker", text: bag.restaurant }));
        (bag.items || []).forEach((item) => {
          slip.appendChild(el("p", { class: "item", text: item.qty + " × " + item.name }));
        });
      });
      main.appendChild(slip);
    });
    if (pickup.address || pickup.lat) main.appendChild(actions(pickup, false));
    dock.appendChild(bigButton("Picked up", pickupBags));
    return;
  }
  if (!drop) {
    main.appendChild(el("h1", { text: "Run finished" }));
    if (stops.some((s) => s.pay !== "transfer")) {
      const sum = el("div", { class: "money done" }, [el("p", { class: "kicker", text: "Cash from this run" })]);
      stops.forEach((s) => sum.appendChild(el("p", { class: "line", text: (orderNo(s) || s.name) + ": " +
        (s.pay === "transfer" ? "bank transfer, no cash" : s.pays_in_usd ? "US dollars, " + money(s.total_cents) + " total" : money(s.total_cents) + " cash") })));
      main.appendChild(sum);
    }
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Back" }));
    return;
  }
  main.appendChild(el("p", { class: "quiet", text: "Drop " + drop.stop_index + " of " + stops.length + (orderNo(drop) ? " · " + orderNo(drop) : "") }));
  main.appendChild(el("h1", { text: drop.name }));
  if (drop.area) main.appendChild(el("p", { class: "place", text: drop.area }));
  if (deliverAt(drop)) main.appendChild(el("p", { class: "due", text: deliverAt(drop) }));
  main.appendChild(cashBox(drop));
  main.appendChild(actions(drop, true));
  if (drop.address) main.appendChild(el("p", { class: "addr", text: drop.address }));
  if (drop.note) main.appendChild(el("p", { class: "note", text: drop.note }));
  (drop.items || []).forEach((item) => main.appendChild(el("p", { class: "small", text: item.qty + " × " + item.name })));
  dock.appendChild(bigButton("Delivered", () => delivered(drop)));
}

/* Taps made without signal go out first, in the order they were made. */
async function flush() {
  if (sending || !db) return;
  const list = outbox();
  if (!list.length) return;
  sending = true;
  while (list.length) {
    const t = list[0];
    const { error } = await db.rpc(t.fn, Object.assign({ session: savedToken() }, t.args));
    if (error && isOffline(error)) break;   // still no signal: the next try sends it
    list.shift();
    saveOutbox(list);
    if (error) tapErr = "A tap saved without signal didn't go through: " + message(error);
  }
  sending = false;
}

async function load() {
  await flush();
  const { data, error } = await db.rpc("pidi_driver_run", { session: savedToken() });
  if (error) {
    // No signal: the bar at the top says it and the run stays. Anything else is said in words.
    loadErr = isOffline(error) ? "" : message(error);
    if (!run) run = readJson(RUN_KEY, null);
    if (!run && !loadErr) loadErr = "No signal, and this phone has no copy of the run yet.";
    paint();
    return;
  }
  loadErr = "";
  run = data;
  if (run) sessionStorage.setItem(RUN_KEY, JSON.stringify(run));
  else sessionStorage.removeItem(RUN_KEY);
  paint();
}

async function tap(fn, args) {
  const { error } = await db.rpc(fn, Object.assign({ session: savedToken() }, args));
  if (error && isOffline(error)) {
    const list = outbox();
    list.push({ fn, args, at: Date.now() });
    saveOutbox(list);
    tapErr = "";
    paint();
    return;
  }
  tapErr = error ? message(error) : "";
  if (error) { paint(); return; }
  load();
}

function pickupBags() { return tap("pidi_driver_picked_up", { run_id: run.run_id }); }
function delivered(stop) { return tap("pidi_driver_delivered", { order_id: stop.order_id }); }

function sendLocation() {
  if (!navigator.geolocation || !run || navigator.onLine === false) return;
  navigator.geolocation.getCurrentPosition((pos) => {
    db.rpc("pidi_driver_location", {
      session: savedToken(),
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
    });
  });
}

watchSignal(() => { if (db) load(); });

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
