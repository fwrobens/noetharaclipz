// The live Supabase Redirect URL entry is this exact URL. Do not append
// sb_flow_id or any other query: GoTrue matches the full URL, and an extra
// parameter would miss the allow-listed callback and fall back to the site URL.
export const PRODUCTION_ORIGIN = "https://noetharaclipz.lovable.app";
export const PRODUCTION_AUTH_CALLBACK = `${PRODUCTION_ORIGIN}/auth/callback`;

export function authCallbackUrl(origin: string) {
  const base = new URL(origin);
  if (base.username || base.password || base.pathname !== "/" || base.search || base.hash) {
    throw new Error("Auth callback origin is invalid");
  }
  return new URL("/auth/callback", `${base.origin}/`).href;
}

export function readAuthCallback(href: string) {
  const url = new URL(href);
  const error = url.searchParams.get("error_description") || url.searchParams.get("error");
  return {
    code: url.searchParams.get("code"),
    flowId: url.searchParams.get("sb_flow_id"),
    error: error ? error.replace(/[\u0000-\u001f]+/g, " ").trim().slice(0, 180) : null,
  };
}

export function finishAuthCallback() {
  window.location.replace("/dashboard");
}
