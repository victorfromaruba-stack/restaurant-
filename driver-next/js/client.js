/* Supabase client for Pidi v2. No build step. The anon key lives in config.js.
   PART 2 PREVIEW (driver-next/, 19 Nov 2026): config.js here only points at the live app's own file
   (driver/v2/config.js), so no address or key is copied. Changes from v2: the preview's own offline cache,
   no-signal handling (the screen and the run stay, taps wait on the phone), and the plain-words helpers below. */
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

/* PREVIEW WORKER: the preview's own offline cache (driver-next/sw.js), scope driver-next/ only, caches named
   "next-driver-…"; it can't touch the live driver app's /driver/ worker or its "pidi-driver-…" caches.
   build/swap_part2.py puts back the /driver/ worker ("../../sw.js", scope "../../") at the swap. */
if ("serviceWorker" in navigator && /^https?:$/.test(location.protocol)) {
  navigator.serviceWorker.register(new URL("../sw.js", import.meta.url), { scope: new URL("../", import.meta.url).pathname }).catch(() => {});
}

export const TOKEN_KEY = "pidi.v2.token";
export const DRIVER_KEY = "pidi.v2.driver";

export function client(cfg) {
  return createClient(cfg.url, cfg.anonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

/* v2 stays off unless both values are set and pidi_ping() answers. */
export async function loadConfig() {
  let mod;
  try {
    mod = await import("../config.js");
  } catch (e) {
    return null;
  }
  const url = String(mod.url || "").trim();
  const anonKey = String(mod.anonKey || "").trim();
  if (!url || !anonKey) return null;
  const db = client({ url, anonKey });
  const { data, error } = await db.rpc("pidi_ping");
  if (error || !data || data.ok !== true) {
    // No signal is not "not connected": the app opens with what this phone has and catches up later.
    if (isOffline(error)) return { url, anonKey, offline: true };
    return null;
  }
  return { url, anonKey };
}

/* A call that never reached the database (no signal, a dead zone, the phone offline). */
export function isOffline(error) {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true;
  const m = String((error && (error.message || error.details)) || "");
  return /failed to fetch|networkerror|load failed|network request failed|fetcherror|no connection/i.test(m);
}

/* The bar at the top while the phone has no signal. Pages call it once. */
export function watchSignal(onBack) {
  const bar = el("div", { class: "signal", role: "status", hidden: "hidden" }, [
    el("b", { text: "No signal" }), el("span", { text: "The run stays on screen. Taps wait on this phone." }),
  ]);
  document.body.prepend(bar);
  const paint = () => {
    const off = navigator.onLine === false;
    if (off) bar.removeAttribute("hidden"); else bar.setAttribute("hidden", "hidden");
    document.documentElement.classList.toggle("is-offline", off);
  };
  window.addEventListener("offline", paint);
  window.addEventListener("online", () => { paint(); if (onBack) onBack(); });
  paint();
  return paint;
}

export function savedToken() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

export function saveSession(token, driver) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(DRIVER_KEY, JSON.stringify(driver));
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(DRIVER_KEY);
}

export function savedDriver() {
  try {
    return JSON.parse(sessionStorage.getItem(DRIVER_KEY) || "null");
  } catch (e) {
    return null;
  }
}

export function money(cents) {
  if (cents == null) return "";
  const neg = cents < 0;
  const n = Math.abs(cents);
  return (neg ? "-" : "") + "ƒ" + Math.floor(n / 100) + "." + String(n % 100).padStart(2, "0");
}

/* Times on staff screens are Aruba's, never the phone's. */
export function arubaTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Aruba" });
  } catch (e) {
    return "";
  }
}

/* "Order 14": the order's number tonight, the same one the kitchen sees on the bag. */
export function orderNo(stop) {
  return stop && stop.night_no ? "Order " + stop.night_no : "";
}

/* "Deliver at 11:00 PM" for a pre-order. Shown only when the stop carries due_at: due more than 20 min after it
   came in (created_at), or, without created_at, still ahead of now. An as-soon-as-possible order says nothing. */
export function deliverAt(stop) {
  const due = Date.parse((stop && stop.due_at) || "");
  if (isNaN(due)) return "";
  const made = Date.parse(stop.created_at || "");
  const pre = isNaN(made) ? due > Date.now() + 5 * 60000 : due - made > 20 * 60000;
  return pre ? "Deliver at " + arubaTime(due) : "";
}

/* What the driver collects at the door, in one line. US dollars: the driver tells the amount, no rate here. */
export function collectLine(stop) {
  if (stop.pay === "transfer") {
    // an old offer without transfer_status: say neither paid nor waiting
    if (stop.transfer_status == null) return "Bank transfer. Don't collect cash.";
    return stop.transfer_status === "paid" ? "Paid by bank transfer. Don't collect cash." : "Awaiting transfer. Don't collect cash.";
  }
  if (stop.pays_in_usd) return "Collect in US dollars: " + money(stop.total_cents) + " total";
  return "Collect " + money(stop.total_cents);
}

export function mapsHref(stop) {
  if (stop.lat != null && stop.lat !== "" && stop.lng != null && stop.lng !== "") {
    return "https://www.google.com/maps/dir/?api=1&destination=" + stop.lat + "," + stop.lng + "&travelmode=driving";
  }
  return "https://www.google.com/maps/dir/?api=1&destination=" + encodeURIComponent((stop.address || "") + ", Aruba") + "&travelmode=driving";
}

export function wazeHref(stop) {
  if (stop.lat != null && stop.lat !== "" && stop.lng != null && stop.lng !== "") {
    return "https://waze.com/ul?ll=" + stop.lat + "," + stop.lng + "&navigate=yes";
  }
  return "https://waze.com/ul?q=" + encodeURIComponent((stop.address || "") + ", Aruba") + "&navigate=yes";
}

export function el(tag, attrs, kids) {
  const node = document.createElement(tag);
  Object.keys(attrs || {}).forEach((key) => {
    const value = attrs[key];
    if (value == null || value === false) return;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  });
  (kids || []).forEach((kid) => {
    if (kid == null) return;
    node.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  });
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

export function message(error) {
  if (!error) return "";
  return error.message || error.details || "Try again.";
}
