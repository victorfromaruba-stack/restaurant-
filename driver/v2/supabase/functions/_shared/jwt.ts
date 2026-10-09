/* Signs a short-lived JWT the Data API will accept.
   Prefer PIDI_SIGNING_JWK (ES256 key the owner imported into Supabase).
   SUPABASE_JWT_SECRET is only the old shared secret, if the project still trusts it. */

function b64url(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function textBytes(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

export async function signJwt(claims: Record<string, unknown>, ttlSeconds: number): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    ...claims,
    role: "authenticated",
    aud: "authenticated",
    iss: (Deno.env.get("SUPABASE_URL") || "") + "/auth/v1",
    iat: now,
    exp: now + ttlSeconds,
  };
  const jwkRaw = Deno.env.get("PIDI_SIGNING_JWK");
  if (jwkRaw) {
    const jwk = JSON.parse(jwkRaw);
    const key = await crypto.subtle.importKey(
      "jwk",
      jwk,
      { name: "ECDSA", namedCurve: "P-256" },
      false,
      ["sign"],
    );
    const header = { alg: "ES256", typ: "JWT", kid: jwk.kid };
    const body = b64url(textBytes(JSON.stringify(header))) + "." + b64url(textBytes(JSON.stringify(payload)));
    const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, textBytes(body));
    return body + "." + b64url(new Uint8Array(sig));
  }
  const secret = Deno.env.get("SUPABASE_JWT_SECRET");
  if (!secret) throw new Error("no signing key");
  const header = { alg: "HS256", typ: "JWT" };
  const body = b64url(textBytes(JSON.stringify(header))) + "." + b64url(textBytes(JSON.stringify(payload)));
  const key = await crypto.subtle.importKey(
    "raw",
    textBytes(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, textBytes(body));
  return body + "." + b64url(new Uint8Array(sig));
}

export const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: cors });
}
