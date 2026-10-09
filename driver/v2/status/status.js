/* Customer status. The link is /driver/v2/status/#t=TOKEN and &u= for a second restaurant. */
import { client, loadConfig } from "../js/client.js";

const main = document.getElementById("screen");

function tokensFromHash() {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  return [params.get("t"), params.get("u")].filter(Boolean);
}

function showProblem(text) {
  main.textContent = "";
  const title = document.createElement("h1");
  title.textContent = "Your order";
  const p = document.createElement("p");
  p.textContent = text;
  main.appendChild(title);
  main.appendChild(p);
}

function paintOrders(orders) {
  main.textContent = "";
  orders.forEach((order) => {
    const block = document.createElement("section");
    block.className = "section";
    const title = document.createElement("h1");
    title.textContent = order.label;
    const where = document.createElement("p");
    where.textContent = order.restaurant || "";
    block.appendChild(title);
    block.appendChild(where);
    main.appendChild(block);
  });
}

loadConfig().then(async (cfg) => {
  const tokens = tokensFromHash();
  if (!tokens.length) {
    showProblem("Open the link from your order.");
    return;
  }
  if (!cfg) {
    showProblem("This page is not connected yet.");
    return;
  }
  const anon = client(cfg);
  async function paint() {
    const orders = [];
    for (const token of tokens) {
      const { data } = await anon.rpc("order_by_token", { token });
      if (data) orders.push(data);
    }
    if (!orders.length) showProblem("We can't find that order.");
    else paintOrders(orders);
  }
  tokens.forEach((token) => {
    fetch(cfg.url.replace(/\/$/, "") + "/functions/v1/order-session", {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: cfg.anonKey },
      body: JSON.stringify({ token }),
    }).then((res) => res.ok ? res.json() : null).then((body) => {
      if (!body || !body.token) return;
      client(cfg, body.token)
        .channel("order-" + token)
        .on("postgres_changes", {
          event: "UPDATE",
          schema: "public",
          table: "orders",
          filter: "public_token=eq." + token,
        }, paint)
        .subscribe();
    }).catch(() => {});
  });
  await paint();
  setInterval(paint, 5000);
});
