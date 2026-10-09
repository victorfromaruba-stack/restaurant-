/* Supabase client for Pidi v2. No build step. The anon key lives in config.js. */
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

export const TOKEN_KEY = "pidi.v2.token";
export const DRIVER_KEY = "pidi.v2.driver";

export async function loadConfig() {
  try {
    return await import("../config.js");
  } catch (e) {
    return null;
  }
}

export function client(cfg, token) {
  const options = { auth: { persistSession: false, autoRefreshToken: false } };
  if (token) options.accessToken = async () => token;
  return createClient(cfg.url, cfg.anonKey, options);
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
