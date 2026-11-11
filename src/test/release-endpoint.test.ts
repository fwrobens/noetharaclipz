import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import handler from "@/server";
import { publicReleaseDocument } from "@/lib/release";

const owner = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69";
const forbidden = [
  owner,
  "sb_publishable_",
  "sb_secret_",
  "service_role",
  "access_token",
  "refresh_token",
  "SUPABASE_SERVICE",
  "password",
  "super-secret-token",
];

beforeEach(() => {
  vi.stubEnv("VITE_NC_BETA_MODE", "true");
  vi.stubEnv("VITE_NC_BUILD_SHA", "a".repeat(40));
});
afterEach(() => vi.unstubAllEnvs());

describe("public release identity", () => {
  it("returns an allowlisted document with no session, secrets, or owner id", async () => {
    const response = await handler.fetch(
      new Request("https://noetharaclipz.lovable.app/api/release?token=super-secret-token", {
        headers: { authorization: "Bearer super-secret-token", cookie: "sb=super-secret-token" },
      }),
      {},
      {},
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("set-cookie")).toBeNull();
    const body = await response.json();
    expect(body).toEqual(publicReleaseDocument());
    expect(Object.keys(body).sort()).toEqual(["access", "app", "build", "mode"]);
    expect(Object.keys(body.access).sort()).toEqual(["mode", "owners", "sha256"]);
    expect(body).toMatchObject({
      app: "NoetharaClipz",
      build: "a".repeat(40),
      mode: "owner-scoped-beta",
      access: { mode: "authenticated-owner-allowlist-v1", owners: 1 },
    });
    expect(body.access.sha256).toMatch(/^[a-f0-9]{64}$/);
    const serialized = JSON.stringify(body);
    for (const secret of forbidden) expect(serialized).not.toContain(secret);
  });

  it("hides a non-commit build value and reports an inactive access mode outside beta", async () => {
    vi.stubEnv("VITE_NC_BETA_MODE", "false");
    vi.stubEnv("VITE_NC_BUILD_SHA", "super-secret-token");
    const response = await handler.fetch(
      new Request("https://noetharaclipz.lovable.app/api/release/"),
      {},
      {},
    );
    const body = await response.json();
    expect(body).toEqual({
      app: "NoetharaClipz",
      build: "development",
      mode: "application",
      access: { mode: "inactive" },
    });
    expect(JSON.stringify(body)).not.toContain("super-secret-token");
  });

  it("allows HEAD and rejects other methods without a body", async () => {
    const head = await handler.fetch(
      new Request("https://noetharaclipz.lovable.app/api/release", { method: "HEAD" }),
      {},
      {},
    );
    expect(head.status).toBe(200);
    expect(await head.text()).toBe("");
    const post = await handler.fetch(
      new Request("https://noetharaclipz.lovable.app/api/release", { method: "POST" }),
      {},
      {},
    );
    expect(post.status).toBe(405);
    expect(post.headers.get("allow")).toBe("GET, HEAD");
    expect(await post.text()).toBe("");
  });
});
