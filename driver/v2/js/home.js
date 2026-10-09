/* Sign in, go online, accept a run. v1 is unchanged and stays the live app. */
import { clear, clearSession, client, el, loadConfig, money, saveSession, savedDriver, savedToken } from "./client.js";

const main = document.getElementById("screen");
const dock = document.getElementById("dock");
let cfg = null;
let db = null;
let timer = null;

function banner(text) {
  return el("p", { class: "test-flag", text });
}

function showSignIn(message) {
  clear(main);
  clear(dock);
  if (!cfg) main.appendChild(banner("Not connected yet. Add the Supabase keys in config.js."));
  main.appendChild(el("h1", { text: "Pidi" }));
  main.appendChild(el("p", { class: "quiet", text: "Driver sign in" }));
  if (message) main.appendChild(el("p", { class: "err", text: message }));
  const code = el("input", { id: "code", autocomplete: "username", placeholder: "Your code" });
  const pin = el("input", { id: "pin", inputmode: "numeric", autocomplete: "current-password", placeholder: "PIN", type: "password" });
  const codeLabel = el("label", { class: "field" }, [el("span", { text: "Code" }), code]);
  const pinLabel = el("label", { class: "field" }, [el("span", { text: "PIN" }), pin]);
  main.appendChild(codeLabel);
  main.appendChild(pinLabel);
  const button = el("button", { class: "btn", type: "button", text: "Sign in" });
  button.disabled = !cfg;
  button.addEventListener("click", signIn);
  dock.appendChild(button);
}

async function signIn() {
  const code = document.getElementById("code").value.trim().toLowerCase();
  const pin = document.getElementById("pin").value.trim();
  const res = await fetch(cfg.url.replace(/\/$/, "") + "/functions/v1/driver-pin", {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: cfg.anonKey },
    body: JSON.stringify({ code, pin }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    showSignIn(body.error || "That PIN does not match.");
    return;
  }
  saveSession(body.token, body.driver);
  db = client(cfg, body.token);
  showHome();
}

function showHome() {
  clear(main);
  clear(dock);
  const driver = savedDriver();
  main.appendChild(el("h1", { text: driver && driver.name ? driver.name : "Pidi" }));
  main.appendChild(el("p", { class: "quiet", id: "state", text: "Offline" }));
  const list = el("div", { id: "offers" });
  main.appendChild(list);
  const online = el("button", { class: "btn", type: "button", id: "online", text: "Go online" });
  online.addEventListener("click", () => setOnline(true));
  const offline = el("button", { class: "btn secondary", type: "button", text: "Go offline" });
  offline.addEventListener("click", () => setOnline(false));
  dock.appendChild(online);
  dock.appendChild(offline);
  const out = el("button", { class: "text-link", type: "button", text: "Sign out" });
  out.addEventListener("click", () => {
    clearSession();
    location.reload();
  });
  main.appendChild(out);
  refresh();
  if (timer) clearInterval(timer);
  timer = setInterval(refresh, 3000);
  db.channel("driver-offers")
    .on("postgres_changes", { event: "*", schema: "public", table: "offers" }, refresh)
    .subscribe();
}

async function setOnline(on) {
  const { error } = await db.rpc(on ? "go_online" : "go_offline");
  if (error) {
    document.getElementById("state").textContent = "Could not update. Try again.";
    return;
  }
  document.getElementById("state").textContent = on ? "Online. Waiting for a run." : "Offline";
  refresh();
}

async function refresh() {
  if (!db) return;
  const { data, error } = await db.rpc("my_offers");
  const box = document.getElementById("offers");
  if (!box) return;
  clear(box);
  if (error) {
    box.appendChild(el("p", { class: "err", text: "Could not load offers." }));
    return;
  }
  const offers = data || [];
  if (!offers.length) {
    box.appendChild(el("p", { text: "No offer right now." }));
    return;
  }
  document.getElementById("state").textContent = "Online";
  offers.forEach((offer) => box.appendChild(offerCard(offer)));
}

function offerCard(offer) {
  const wrap = el("div", { class: "stack" });
  const card = el("div", { class: "money" });
  (offer.stops || []).forEach((stop) => {
    card.appendChild(el("p", { class: "kicker", text: stop.restaurant }));
    card.appendChild(el("p", { class: "line", text: (stop.area ? stop.area + " · " : "") + stop.name }));
    if (stop.pay === "transfer") {
      card.appendChild(el("p", { text: "Awaiting transfer. Don't collect cash." }));
    } else {
      card.appendChild(el("p", { text: "Collect " + money(stop.total_cents) }));
    }
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
  const { data, error } = await db.rpc("accept_offer", { offer_id: offer.offer_id });
  if (error || !data || !data.ok) {
    refresh();
    return;
  }
  location.href = "run.html?run=" + data.run_id;
}

async function pass(offer) {
  await db.rpc("decline_offer", { offer_id: offer.offer_id });
  refresh();
}

setInterval(() => {
  document.querySelectorAll("[data-seconds]").forEach((node) => {
    const left = Math.max(0, Number(node.getAttribute("data-seconds")) - 1);
    node.setAttribute("data-seconds", String(left));
    node.textContent = left + "s";
  });
}, 1000);

loadConfig().then((got) => {
  cfg = got;
  const token = savedToken();
  if (cfg && token) {
    db = client(cfg, token);
    showHome();
    return;
  }
  showSignIn("");
});
