// Server-only policy. Knowing an owner UUID grants no access: GoTrue must
// validate the request's session before this predicate is evaluated.
import { createHash } from "node:crypto";
import { createServerClient, parseCookieHeader, serializeCookieHeader } from "@supabase/ssr";
import { betaEnabled } from "./beta";
import { supabaseUrl, publishableKey } from "./supabase/config";

export const betaAccessPolicy = {
  version: 1,
  owners: ["21b61ad1-bda4-4abd-ac35-7a0bf477ed69"],
  confirmed_email_required: true,
  anonymous_allowed: false,
  routing: "private-by-default-including-server-functions-v1",
};
export function betaAccessIdentity() {
  return {
    mode: "authenticated-owner-allowlist-v1",
    owners: betaAccessPolicy.owners.length,
    sha256: createHash("sha256").update(JSON.stringify(betaAccessPolicy)).digest("hex"),
  };
}
export function betaOwnerAllowed(
  user: { id: string; role?: string; is_anonymous?: boolean; email_confirmed_at?: string } | null,
) {
  return (
    !!user &&
    user.role === "authenticated" &&
    user.is_anonymous !== true &&
    !!user.email_confirmed_at &&
    betaAccessPolicy.owners.includes(user.id)
  );
}
// A new route cannot silently bypass the beta gate. Only the current public
// entry pages and build assets are exempt; server functions remain protected.
const publicPath =
  /^(?:\/$|\/(?:login|auth|signup|pricing)\/?$|\/auth\/callback\/?$|\/api\/release\/?$|\/assets\/|\/favicon\.(?:ico|png)$|\/robots\.txt$)/;

export async function authorizeBetaRequest(
  request: Request,
): Promise<{ response?: Response; request?: Request; cookies: string[] }> {
  const cookies: string[] = [];
  const url = new URL(request.url);
  const decodedPath = decodeURIComponent(url.pathname);
  const normalizedPath = new URL(decodedPath, url.origin).pathname;
  if (!betaEnabled() || (!/[?#]/.test(decodedPath) && publicPath.test(normalizedPath)))
    return { cookies };
  const headers = {
    "Cache-Control": "private, no-store",
    Vary: "Cookie",
    "X-Robots-Tag": "noindex, nofollow",
  };
  const signedOut = () => ({
    cookies,
    response: new Response(null, { status: 302, headers: { ...headers, Location: "/login" } }),
  });
  if (!request.headers.get("cookie")) return signedOut();
  const refreshed = new Map(
    parseCookieHeader(request.headers.get("cookie") ?? "").map(({ name, value }) => [
      name,
      value ?? "",
    ]),
  );
  const client = createServerClient(supabaseUrl, publishableKey, {
    cookieOptions: {
      secure: new URL(request.url).protocol === "https:",
      sameSite: "lax",
      path: "/",
    },
    cookies: {
      getAll: () => Array.from(refreshed, ([name, value]) => ({ name, value })),
      setAll: (values) =>
        values.forEach(({ name, value, options }) => {
          cookies.push(serializeCookieHeader(name, value, options));
          // Propagate refresh cookies into this request as well as the response
          // so SSR does not exchange the original refresh token a second time.
          refreshed.set(name, value);
        }),
    },
  });
  try {
    const { data, error } = await client.auth.getUser();
    if (
      error &&
      (error.name === "AuthRetryableFetchError" || error.status === 0 || (error.status ?? 0) >= 500)
    )
      throw new Error("Auth unavailable");
    if (error || !data.user) return signedOut();
    if (!betaOwnerAllowed(data.user))
      return {
        cookies,
        response: new Response("This account is not invited to the beta.", {
          status: 403,
          headers: { ...headers, "Content-Type": "text/plain; charset=utf-8" },
        }),
      };
    if (!cookies.length) return { cookies };
    const forwardedHeaders = new Headers(request.headers);
    forwardedHeaders.set(
      "cookie",
      Array.from(refreshed, ([name, value]) => `${name}=${encodeURIComponent(value)}`).join("; "),
    );
    return { cookies, request: new Request(request, { headers: forwardedHeaders }) };
  } catch {
    return {
      cookies,
      response: new Response("Authentication is temporarily unavailable. Please retry.", {
        status: 503,
        headers: { ...headers, "Content-Type": "text/plain; charset=utf-8" },
      }),
    };
  }
}
