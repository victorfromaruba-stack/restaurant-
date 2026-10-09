/* Sign in, go online, accept a run. v1 is unchanged and stays the live app. */
import { clear, clearSession, client, el, loadConfig, message, money, saveSession, savedDriver, savedToken } from "./client.js";

const main = document.getElementById("screen");
const dock = document.getElementById("dock");
let cfg = null;
let db = null;
let timer = null;
let channel = null;

function banner(text) {
  return el("p", { class: "test-flag", text });
}

function showSignIn(note) {
  clear(main);
  clear(dock);
  if (!cfg) main.appendChild(banner("Not connected yet. Add the anon key in config.js."));
  main.appendChild(el("h1", { text: "Pidi" }));
  main.appendChild(el("p", { class: "quiet", text: "Driver sign in" }));
  if (note) main.appendChild(el("p", { class: "err", text: note }));
  const code = el("input", { id: "code", autocomplete: "username", placeholder: "Your name" });
  const pin = el("input", { id: "pin", inputmode: "numeric", autocomplete: "current-password", placeholder: "PIN", type: "password" });
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "Name" }), code]));
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "PIN" }), pin]));
  const button = el("button", { class: "btn", type: "button", text: "Sign in" });
  button.disabled = !cfg;
  button.addEventListener("click", signIn);
  dock.appendChild(button);
}

async function signIn() {
  const code = document.getElementById("code").value.trim();
  const pin = document.getElementById("pin").value.trim();
  const { data, error } = await db.rpc("pidi_driver_login", { driver_name_or_id: code, pin });
  if (error || !data || !data.token) {
    showSignIn(message(error) || "That PIN does not match.");
    return;
  }
  saveSession(data.token, data);
  showHome();
}

function showHome() {
  clear(main);
  clear(dock);
  const driver = savedDriver();
  main.appendChild(el("h1", { text: driver && driver.name ? driver.name : "Pidi" }));
  main.appendChild(el("p", { class: "quiet", id: "state", text: "Offline" }));
  main.appendChild(el("div", { id: "offers" }));
  const online = el("button", { class: "btn", type: "button", text: "Go online" });
  online.addEventListener("click", () => setOnline(true));
  const offline = el("button", { class: "btn secondary", type: "button", text: "Go offline" });
  offline.addEventListener("click", () => setOnline(false));
  dock.appendChild(online);
  dock.appendChild(offline);
  const out = el("button", { class: "text-link", type: "button", text: "Sign out" });
  out.addEventListener("click", () => {
    clearSession();
    if (channel) db.removeChannel(channel);
    location.reload();
  });
  main.appendChild(out);
  refresh();
  if (timer) clearInterval(timer);
  timer = setInterval(refresh, 8000);
  if (driver && driver.topic) {
    channel = db.channel(driver.topic, { config: { private: false } });
    channel.on("broadcast", { event: "changed" }, refresh).subscribe();
  }
}

async function setOnline(on) {
  const { error } = await db.rpc("pidi_driver_set_online", { session: savedToken(), online: on });
  const state = document.getElementById("state");
  if (error) {
    if (state) state.textContent = message(error);
    return;
  }
  if (state) state.textContent = on ? "Online. Waiting for a run." : "Offline";
  refresh();
}

async function refresh() {
  if (!db || !savedToken()) return;
  const { data, error } = await db.rpc("pidi_driver_offers", { session: savedToken() });
  const box = document.getElementById("offers");
  if (!box) return;
  clear(box);
  if (error) {
    if (String(message(error)).toLowerCase().indexOf("sign in") >= 0) {
      clearSession();
      showSignIn("Sign in again.");
      return;
    }
    box.appendChild(el("p", { class: "err", text: message(error) }));
    return;
  }
  const offers = data || [];
  if (!offers.length) {
    box.appendChild(el("p", { text: "No offer right now." }));
    return;
  }
  const state = document.getElementById("state");
  if (state) state.textContent = "Online";
  offers.forEach((offer) => box.appendChild(offerCard(offer)));
}

function offerCard(offer) {
  const wrap = el("div", { class: "stack" });
  const card = el("div", { class: "money" });
  (offer.stops || []).forEach((stop) => {
    card.appendChild(el("p", { class: "kicker", text: stop.restaurant }));
    card.appendChild(el("p", { class: "line", text: (stop.area ? stop.area + " · " : "") + stop.name }));
    card.appendChild(el("p", { text: stop.pay === "transfer" ? "Awaiting transfer. Don't collect cash." : "Collect " + money(stop.total_cents) }));
  });
  card.appendChild(el("p", { class: "figure", "data-seconds": String(offer.seconds_left), text: offer.seconds_left + "s" }));
  wrap.appendChild(card);
  const accept = el("button", { class: "btn", type: "button", text: "Accept" });
  accept.addEventListener("click", () => take(offer));
  const decline = el("button", { class: "btn secondary", type: "button", text: "Not this one" });
  decline.addEventListener("click", () => pass(offer));
  wrap.appendChild(accept);
  wrap.appendChild(decline);
  return wrap;
}

async function take(offer) {
  const { data, error } = await db.rpc("pidi_driver_accept", { session: savedToken(), offer_id: offer.offer_id });
  if (error || !data || !data.ok) {
    refresh();
    return;
  }
  location.href = "run.html";
}

async function pass(offer) {
  await db.rpc("pidi_driver_decline", { session: savedToken(), offer_id: offer.offer_id });
  refresh();
}

setInterval(() => {
  document.querySelectorAll("[data-seconds]").forEach((node) => {
    const left = Math.max(0, Number(node.getAttribute("data-seconds")) - 1);
    node.setAttribute("data-seconds", String(left));
    node.textContent = left + "s";
    if (left === 0 && node.getAttribute("data-fired") !== "1") {
      node.setAttribute("data-fired", "1");
      refresh();
    }
  });
}, 1000);

loadConfig().then((got) => {
  cfg = got;
  if (cfg && savedToken()) {
    db = client(cfg);
    showHome();
    return;
  }
  if (cfg) db = client(cfg);
  showSignIn("");
});
