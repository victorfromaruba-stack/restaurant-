/* Customer status. The link is /driver/v2/status/#t=TOKEN and &u= for a second order. */
import { client, loadConfig } from "../js/client.js";

const main = document.getElementById("screen");
let db = null;

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
  db = client(cfg);
  const seen = {};
  async function paint() {
    const orders = [];
    for (const token of tokens) {
      const { data, error } = await db.rpc("pidi_order_status", { token });
      if (error || !data) continue;
      orders.push(data);
      if (data.topic && !seen[data.topic]) {
        seen[data.topic] = true;
        db.channel(data.topic, { config: { private: false } })
          .on("broadcast", { event: "changed" }, paint)
          .subscribe();
      }
    }
    if (!orders.length) showProblem("We can't find that order.");
    else paintOrders(orders);
  }
  await paint();
  setInterval(paint, 8000);
});
