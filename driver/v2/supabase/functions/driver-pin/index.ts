import { createClient } from "npm:@supabase/supabase-js@2";
import { cors, json, signJwt } from "../_shared/jwt.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Use POST" }, 405);
  let body: { code?: string; pin?: string } = {};
  try {
    body = await req.json();
  } catch {
    return json({ error: "Bad request" }, 400);
  }
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL") || "",
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    { auth: { persistSession: false } },
  );
  const { data, error } = await supabase.rpc("verify_driver_pin", {
    code: String(body.code || "").trim().toLowerCase(),
    pin: String(body.pin || ""),
  });
  if (error || !data || data.error) {
    const locked = data && data.error === "locked";
    return json({ error: locked ? "Too many tries. Wait 5 minutes." : "That PIN does not match." }, 401);
  }
  try {
    const token = await signJwt({ sub: data.id, driver_id: data.id }, 12 * 60 * 60);
    return json({ token, driver: { id: data.id, name: data.name, code: data.code } });
  } catch {
    return json({ error: "Signing key is not set" }, 500);
  }
});
