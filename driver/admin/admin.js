/* Admin PIN stays in this page's memory. It is not written to localStorage or sessionStorage. */
import { clear, client, el, loadConfig, message } from "../v2/js/client.js";

const main = document.getElementById("screen");
const dock = document.getElementById("dock");
let db = null;
let adminPin = "";

function showNote(text) {
  const old = document.getElementById("note");
  if (old) old.remove();
  if (!text) return;
  main.appendChild(el("p", { id: "note", class: "err", text }));
}

function disconnected() {
  clear(main);
  clear(dock);
  main.appendChild(el("p", { class: "test-flag", text: "Not connected yet. Add the anon key in config.js." }));
  main.appendChild(el("h1", { text: "Pidi" }));
  main.appendChild(el("p", { class: "quiet", text: "Admin" }));
}

function showPin() {
  clear(main);
  clear(dock);
  main.appendChild(el("h1", { text: "Pidi" }));
  main.appendChild(el("p", { class: "quiet", text: "Admin" }));
  const pin = el("input", {
    id: "admin-pin",
    inputmode: "numeric",
    autocomplete: "current-password",
    placeholder: "8 digits",
    type: "password",
  });
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "Admin PIN" }), pin]));
  const button = el("button", { class: "btn", type: "button", text: "Continue" });
  button.addEventListener("click", enter);
  dock.appendChild(button);
}

async function enter() {
  adminPin = document.getElementById("admin-pin").value.trim();
  const { data, error } = await db.rpc("pidi_admin_list_drivers", { admin_pin: adminPin });
  if (error || !data || data.ok === false) {
    adminPin = "";
    showPin();
    showNote((data && data.error) || message(error) || "That PIN does not match.");
    return;
  }
  showDesk(data.drivers || []);
}

function showDesk(drivers) {
  clear(main);
  clear(dock);
  main.appendChild(el("h1", { text: "Admin" }));

  const kitchen = el("input", {
    id: "kitchen-pin",
    inputmode: "numeric",
    autocomplete: "new-password",
    placeholder: "4 to 8 digits",
    type: "password",
  });
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "Kitchen PIN" }), kitchen]));
  const saveKitchen = el("button", { class: "btn", type: "button", text: "Save kitchen PIN" });
  saveKitchen.addEventListener("click", saveKitchenPin);
  main.appendChild(saveKitchen);

  main.appendChild(el("h2", { text: "Drivers" }));
  if (!drivers.length) main.appendChild(el("p", { text: "No drivers yet." }));
  drivers.forEach((driver) => {
    const block = el("div", { class: "stack" });
    const phone = driver.phone ? " · " + driver.phone : "";
    block.appendChild(el("p", { text: driver.name + phone }));
    const remove = el("button", { class: "btn secondary", type: "button", text: "Remove " + driver.name });
    remove.addEventListener("click", () => removeDriver(driver));
    block.appendChild(remove);
    main.appendChild(block);
  });

  main.appendChild(el("h2", { text: "Add a driver" }));
  const name = el("input", { id: "driver-name", autocomplete: "name", placeholder: "Ari" });
  const phone = el("input", { id: "driver-phone", inputmode: "tel", autocomplete: "tel", placeholder: "2975550000" });
  const pin = el("input", {
    id: "driver-pin",
    inputmode: "numeric",
    autocomplete: "new-password",
    placeholder: "4 to 8 digits",
    type: "password",
  });
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "Name" }), name]));
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "Phone" }), phone]));
  main.appendChild(el("label", { class: "field" }, [el("span", { text: "PIN" }), pin]));
  const add = el("button", { class: "btn", type: "button", text: "Add driver" });
  add.addEventListener("click", addDriver);
  dock.appendChild(add);
}

async function saveKitchenPin() {
  const pin = document.getElementById("kitchen-pin").value.trim();
  const { data, error } = await db.rpc("pidi_admin_set_kitchen_pin", { admin_pin: adminPin, new_pin: pin });
  if (error || !data || data.ok === false) {
    showNote((data && data.error) || message(error) || "Try again.");
    return;
  }
  showNote("");
  const old = document.getElementById("saved");
  if (old) old.remove();
  main.insertBefore(el("p", { id: "saved", text: "Kitchen PIN saved." }), main.children[1] || null);
}

async function addDriver() {
  const name = document.getElementById("driver-name").value.trim();
  const phone = document.getElementById("driver-phone").value.trim();
  const pin = document.getElementById("driver-pin").value.trim();
  const { data, error } = await db.rpc("pidi_admin_add_driver", {
    admin_pin: adminPin,
    name,
    phone,
    pin,
  });
  if (error || !data || data.ok === false) {
    showNote((data && data.error) || message(error) || "Try again.");
    return;
  }
  await reload();
}

async function removeDriver(driver) {
  const { data, error } = await db.rpc("pidi_admin_remove_driver", {
    admin_pin: adminPin,
    driver_id: driver.driver_id,
  });
  if (error || !data || data.ok === false) {
    showNote((data && data.error) || message(error) || "Try again.");
    return;
  }
  await reload();
}

async function reload() {
  const { data, error } = await db.rpc("pidi_admin_list_drivers", { admin_pin: adminPin });
  if (error || !data || data.ok === false) {
    adminPin = "";
    showPin();
    showNote((data && data.error) || message(error) || "Sign in again.");
    return;
  }
  showDesk(data.drivers || []);
}

loadConfig().then((cfg) => {
  if (!cfg) {
    disconnected();
    return;
  }
  db = client(cfg);
  showPin();
});
