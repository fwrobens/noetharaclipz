import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
const sdk = vi.hoisted(() => ({
  getUser: vi.fn(),
  options: null as Record<string, unknown> | null,
}));
vi.mock("@supabase/ssr", async (original) => ({
  ...(await original<typeof import("@supabase/ssr")>()),
  createServerClient: (_url: string, _key: string, options: Record<string, unknown>) => {
    sdk.options = options;
    return { auth: { getUser: sdk.getUser } };
  },
}));
import {
  authorizeBetaRequest,
  betaAccessIdentity,
  betaOwnerAllowed,
} from "@/lib/beta-access.server";
const owner = {
  id: "21b61ad1-bda4-4abd-ac35-7a0bf477ed69",
  role: "authenticated",
  email_confirmed_at: "2026-11-09",
  is_anonymous: false,
};
beforeEach(() => {
  vi.stubEnv("VITE_NC_BETA_MODE", "true");
  sdk.getUser.mockReset();
  sdk.options = null;
});
afterEach(() => vi.unstubAllEnvs());
const request = (path = "/library") =>
  new Request("https://noetharaclipz.lovable.app" + path, {
    headers: { cookie: "sb-test-auth-token=forged-browser-state" },
  });
describe("server beta owner access", () => {
  it("rejects anonymous, wrong-role, unconfirmed and uninvited identities", () => {
    expect(betaOwnerAllowed(owner)).toBe(true);
    for (const user of [
      null,
      { ...owner, id: "other-owner" },
      { ...owner, role: "service_role" },
      { ...owner, email_confirmed_at: "" },
      { ...owner, is_anonymous: true },
    ])
      expect(betaOwnerAllowed(user)).toBe(false);
  });
  it("redirects missing sessions without trusting client state or calling GoTrue", async () => {
    const value = await authorizeBetaRequest(
      new Request("https://noetharaclipz.lovable.app/library"),
    );
    expect(value.response?.status).toBe(302);
    expect(sdk.getUser).not.toHaveBeenCalled();
  });
  it("denies a forged cookie when native GoTrue rejects it", async () => {
    sdk.getUser.mockResolvedValue({ data: { user: null }, error: { status: 401 } });
    expect((await authorizeBetaRequest(request())).response?.status).toBe(302);
    expect(sdk.getUser).toHaveBeenCalledOnce();
  });
  it("returns 403 to a valid uninvited account for encoded and normal private paths", async () => {
    sdk.getUser.mockResolvedValue({ data: { user: { ...owner, id: "other-owner" } }, error: null });
    for (const path of ["/library", "/settings", "/project/a", "/editor/a", "/%6cibrary"])
      expect((await authorizeBetaRequest(request(path))).response?.status).toBe(403);
  });
  it("fails closed on an authentication outage", async () => {
    sdk.getUser.mockResolvedValue({
      data: { user: null },
      error: { name: "AuthRetryableFetchError", status: 503 },
    });
    const value = await authorizeBetaRequest(request());
    expect(value.response?.status).toBe(503);
    expect(value.response?.headers.get("cache-control")).toBe("private, no-store");
  });
  it("allows the verified owner and refreshes both request and response cookies securely", async () => {
    sdk.getUser.mockImplementation(async () => {
      const cookies = sdk.options!["cookies"] as { setAll: (values: unknown[]) => void };
      cookies.setAll([
        {
          name: "sb-test-auth-token",
          value: "refreshed",
          options: { secure: true, sameSite: "lax", path: "/" },
        },
      ]);
      return { data: { user: owner }, error: null };
    });
    const value = await authorizeBetaRequest(request());
    expect(value.response).toBeUndefined();
    expect(value.cookies[0]).toContain("Secure");
    expect(value.request?.headers.get("cookie")).toContain("refreshed");
    expect(sdk.options!["cookieOptions"]).toMatchObject({
      secure: true,
      sameSite: "lax",
      path: "/",
    });
  });
  it("keeps login, callback and release public while binding an exact access policy identity", async () => {
    for (const path of ["/login", "/auth/callback", "/api/release"])
      expect((await authorizeBetaRequest(request(path))).response).toBeUndefined();
    expect(sdk.getUser).not.toHaveBeenCalled();
    expect(betaAccessIdentity()).toMatchObject({
      mode: "authenticated-owner-allowlist-v1",
      owners: 1,
      sha256: expect.stringMatching(/^[a-f0-9]{64}$/),
    });
  });
});
