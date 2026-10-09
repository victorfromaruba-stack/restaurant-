/* One run from the database. Same steps as v1: pickup, then each drop. */
import { clear, client, el, loadConfig, mapsHref, money, savedToken, wazeHref } from "./client.js";

const main = document.getElementById("screen");
const dock = document.getElementById("dock");
const runId = new URLSearchParams(location.search).get("run");
let db = null;
let run = null;
let locateTimer = null;

function toTop() {
  window.scrollTo(0, 0);
}

function cashBox(stops) {
  const cash = (stops || []).filter((stop) => stop.pay === "cash");
  const collect = cash.reduce((sum, stop) => sum + stop.total_cents, 0);
  const pays = cash.map((stop) => stop.pays_with_cents).find((value) => value != null);
  const box = el("div", { class: "money" });
  if (!cash.length) {
    box.appendChild(el("p", { class: "kicker", text: "Awaiting transfer" }));
    box.appendChild(el("p", { class: "figure", text: "Don't collect cash" }));
    return box;
  }
  box.appendChild(el("p", { class: "kicker", text: "Collect" }));
  box.appendChild(el("p", { class: "figure", text: money(collect) }));
  if (pays != null) {
    const change = pays - collect;
    box.appendChild(el("p", { class: "line", text: "Pays with " + money(pays) }));
    box.appendChild(el("p", { class: "line", text: change >= 0 ? "Give " + money(change) + " change" : "Short " + money(-change) }));
  }
  box.appendChild(el("p", { class: "small", text: "Includes ƒ5 delivery" }));
  return box;
}

function actions(stop) {
  return el("div", { class: "actions" }, [
    el("div", { class: "row" }, [
      el("a", { class: "btn secondary", href: mapsHref(stop), target: "_blank", rel: "noopener", text: "Google Maps" }),
      el("a", { class: "btn secondary", href: wazeHref(stop), target: "_blank", rel: "noopener", text: "Waze" }),
    ]),
    el("div", { class: "row" }, [
      el("a", { class: "btn secondary", href: "tel:+" + String(stop.phone || "").replace(/\D/g, ""), text: "Call" }),
      el("a", {
        class: "btn secondary",
        href: "https://wa.me/" + String(stop.phone || "").replace(/\D/g, "") + "?text=" + encodeURIComponent("Hi " + stop.name + ", your " + stop.restaurant + " order is outside."),
        target: "_blank",
        rel: "noopener",
        text: "WhatsApp",
      }),
    ]),
  ]);
}

function items(stop) {
  const list = el("ul");
  (stop.items || []).forEach((item) => {
    list.appendChild(el("li", { text: (item.qty ? item.qty + " " : "") + item.name }));
  });
  return el("div", { class: "bag" }, [
    el("img", { class: "logo", src: "../brand/" + stop.restaurant_slug + ".png", alt: stop.restaurant }),
    el("div", {}, [el("p", { class: "who", text: stop.restaurant }), list]),
  ]);
}

function render() {
  clear(main);
  clear(dock);
  if (!run) {
    main.appendChild(el("h1", { text: "Pidi" }));
    main.appendChild(el("p", { text: "This run is not on this phone." }));
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Back" }));
    toTop();
    return;
  }
  const stops = run.stops || [];
  if (run.step === "done" || run.status === "done") {
    main.appendChild(el("h1", { text: stops.length > 1 ? "Both drops done" : "Drop done" }));
    main.appendChild(cashBox(stops));
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Done" }));
    stopLocate();
    toTop();
    return;
  }
  if (run.step === "pickup") {
    main.appendChild(el("h1", { text: "Pick up" }));
    const seen = {};
    stops.forEach((stop) => {
      if (seen[stop.restaurant_slug]) return;
      seen[stop.restaurant_slug] = true;
      const merged = { ...stop, items: [] };
      stops.forEach((other) => {
        if (other.restaurant_slug === stop.restaurant_slug) merged.items = merged.items.concat(other.items || []);
      });
      main.appendChild(items(merged));
    });
    const pickup = run.pickup || {};
    if (pickup.name) main.appendChild(el("p", { class: "who", text: pickup.name }));
    if (pickup.address) main.appendChild(el("p", { class: "addr", text: pickup.address }));
    if (pickup.address || pickup.lat) {
      main.appendChild(el("div", { class: "row" }, [
        el("a", { class: "btn secondary", href: mapsHref(pickup), target: "_blank", rel: "noopener", text: "Google Maps" }),
        el("a", { class: "btn secondary", href: wazeHref(pickup), target: "_blank", rel: "noopener", text: "Waze" }),
      ]));
    }
    const button = el("button", { class: "btn", type: "button", text: "Picked up" });
    button.addEventListener("click", () => advance("picked_up"));
    dock.appendChild(button);
    toTop();
    return;
  }
  const drop = stops[run.drop_index] || stops[0];
  main.appendChild(el("p", { class: "quiet", text: "Drop " + (run.drop_index + 1) + " of " + stops.length }));
  main.appendChild(el("h1", { text: drop.name }));
  if (drop.area) main.appendChild(el("p", { class: "place", text: drop.area }));
  main.appendChild(cashBox(stops.length > 1 ? stops : [drop]));
  main.appendChild(actions(drop));
  main.appendChild(el("p", { class: "addr", text: drop.address }));
  if (drop.note) main.appendChild(el("p", { class: "note", text: drop.note }));
  main.appendChild(items(drop));
  const button = el("button", { class: "btn", type: "button", text: "Delivered" });
  button.addEventListener("click", () => advance("delivered"));
  dock.appendChild(button);
  toTop();
}

async function advance(action) {
  const { data, error } = await db.rpc("advance_run", { run_id: runId, action });
  if (error || !data || data.ok === false) return;
  run = data;
  render();
}

async function sendLocation() {
  if (!navigator.geolocation || !run || run.status !== "active") return;
  navigator.geolocation.getCurrentPosition((pos) => {
    db.rpc("push_location", { lat: pos.coords.latitude, lng: pos.coords.longitude });
  });
}

function stopLocate() {
  if (locateTimer) clearInterval(locateTimer);
}

async function load() {
  const cfg = await loadConfig();
  const token = savedToken();
  if (!cfg || !token || !runId) {
    main.appendChild(el("h1", { text: "Pidi" }));
    main.appendChild(el("p", { text: "Sign in on the driver page first." }));
    dock.appendChild(el("a", { class: "btn", href: "index.html", text: "Sign in" }));
    return;
  }
  db = client(cfg, token);
  const { data } = await db.rpc("run_detail", { run_id: runId });
  run = data;
  render();
  sendLocation();
  locateTimer = setInterval(sendLocation, 15000);
}

load();
