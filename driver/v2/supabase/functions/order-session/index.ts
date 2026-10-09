import { createClient } from "npm:@supabase/supabase-js@2";
import { cors, json, signJwt } from "../_shared/jwt.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Use POST" }, 405);
  let body: { token?: string } = {};
  try {
    body = await req.json();
  } catch {
    return json({ error: "Bad request" }, 400);
  }
  const token = String(body.token || "");
  if (token.length < 20) return json({ error: "Unknown order" }, 404);
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL") || "",
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "",
    { auth: { persistSession: false } },
  );
  const { data, error } = await supabase.rpc("order_by_token", { token });
  if (error || !data) return json({ error: "Unknown order" }, 404);
  try {
    const access = await signJwt({ sub: data.id, order_token: token }, 6 * 60 * 60);
    return json({ token: access, order: data });
  } catch {
    return json({ error: "Signing key is not set" }, 500);
  }
});
