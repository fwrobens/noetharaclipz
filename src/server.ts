import "./lib/error-capture";

import { consumeLastCapturedError } from "./lib/error-capture";
import { renderErrorPage } from "./lib/error-page";
import { betaEnabled, releaseInfo } from "./lib/beta";
import { authorizeBetaRequest, betaAccessIdentity } from "./lib/beta-access.server";

type ServerEntry = {
  fetch: (request: Request, env: unknown, ctx: unknown) => Promise<Response> | Response;
};

let serverEntryPromise: Promise<ServerEntry> | undefined;

async function getServerEntry(): Promise<ServerEntry> {
  if (!serverEntryPromise) {
    serverEntryPromise = import("@tanstack/react-start/server-entry").then(
      (m) => (m.default ?? m) as ServerEntry,
    );
  }
  return serverEntryPromise;
}

// h3 swallows in-handler throws into a normal 500 Response with body
// {"unhandled":true,"message":"HTTPError"} — try/catch alone never fires for those.
async function normalizeCatastrophicSsrResponse(response: Response): Promise<Response> {
  if (response.status < 500) return response;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return response;

  const body = await response.clone().text();
  if (!isH3SwallowedErrorBody(body)) return response;

  console.error(consumeLastCapturedError() ?? new Error(`h3 swallowed SSR error: ${body}`));
  return new Response(renderErrorPage(), {
    status: 500,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

function isH3SwallowedErrorBody(body: string): boolean {
  try {
    const payload = JSON.parse(body) as { unhandled?: unknown; message?: unknown };
    return payload.unhandled === true && payload.message === "HTTPError";
  } catch {
    return false;
  }
}

// Hosting compresses every response at the edge. Never compress a body (gzip, brotli,
// CompressionStream) or set content-encoding here or in a server route: the body gets encoded
// twice and renders garbled.
export default {
  async fetch(request: Request, env: unknown, ctx: unknown) {
    if (new URL(request.url).pathname === "/api/release") {
      const headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex, nofollow",
        Allow: "GET, HEAD",
      };
      if (!["GET", "HEAD"].includes(request.method))
        return new Response(null, { status: 405, headers });
      return new Response(
        request.method === "HEAD"
          ? null
          : JSON.stringify({
              ...releaseInfo(),
              access: betaEnabled() ? betaAccessIdentity() : { mode: "inactive" },
            }),
        {
          headers,
        },
      );
    }
    try {
      const access = await authorizeBetaRequest(request);
      if (access.response) {
        for (const cookie of access.cookies) access.response.headers.append("Set-Cookie", cookie);
        return access.response;
      }
      const handler = await getServerEntry();
      const response = await handler.fetch(access.request ?? request, env, ctx);
      const normalized = await normalizeCatastrophicSsrResponse(response);
      if (!betaEnabled()) return normalized;
      const headers = new Headers(normalized.headers);
      headers.set("X-Robots-Tag", "noindex, nofollow");
      headers.set("Cache-Control", "private, no-store");
      headers.append("Vary", "Cookie");
      for (const cookie of access.cookies) headers.append("Set-Cookie", cookie);
      return new Response(normalized.body, {
        status: normalized.status,
        statusText: normalized.statusText,
        headers,
      });
    } catch (error) {
      console.error(error);
      return new Response(renderErrorPage(), {
        status: 500,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
  },
};
