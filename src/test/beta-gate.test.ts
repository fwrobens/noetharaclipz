import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/integrations/supabase/types";
import { afterEach, describe, expect, it, vi } from "vitest";
import { betaEnabled, releaseInfo } from "@/lib/beta";
import { authorizeBetaRequest } from "@/lib/beta-access.server";
import { betaOwnerAllowed } from "@/lib/beta-policy";
import { requireCreatorAdmission } from "@/lib/creator-admission.server";

const owner = {
  id: "21b61ad1-bda4-4abd-ac35-7a0bf477ed69",
  role: "authenticated",
  email_confirmed_at: "2026-11-09",
  is_anonymous: false,
};
const qa = { ...owner, id: "c7ade7f9-2003-4a38-ae19-393fffae8452" };
const production = { PROD: true, DEV: false } as const;

afterEach(() => vi.unstubAllEnvs());

describe("production beta gate", () => {
  it("stays on in production when the mode flag is missing or explicitly false", () => {
    expect(betaEnabled(production)).toBe(true);
    expect(betaEnabled({ ...production, VITE_NC_BETA_MODE: "false" })).toBe(true);
    expect(releaseInfo(production)).toMatchObject({
      build: "unknown",
      mode: "owner-scoped-beta",
    });
    expect(releaseInfo({ ...production, VITE_NC_BUILD_SHA: "a".repeat(40) }).build).toBe("a".repeat(40));
  });

  it("allows an explicit local opt-out and keeps a dev server unrestricted by default", () => {
    expect(betaEnabled({ PROD: false, DEV: true })).toBe(false);
    expect(betaEnabled({ PROD: false, DEV: true, VITE_NC_BETA_MODE: "false" })).toBe(false);
    expect(betaEnabled({ PROD: false, DEV: true, VITE_NC_BETA_MODE: "true" })).toBe(true);
    expect(releaseInfo({ PROD: false, DEV: true, VITE_NC_BUILD_SHA: "not-a-sha" }).build).toBe(
      "development",
    );
  });
});

describe("allowlist fail closed", () => {
  it("denies a missing or invalid config", () => {
    expect(betaOwnerAllowed(owner, null)).toBe(false);
    expect(betaOwnerAllowed(owner, {})).toBe(false);
    expect(betaOwnerAllowed(owner, { owners: [] })).toBe(false);
    expect(betaOwnerAllowed(owner, { owners: ["not-a-uuid"] })).toBe(false);
    expect(betaOwnerAllowed(owner, { owners: [owner.id, 12] })).toBe(false);
  });

  it("allows only the invited owner", () => {
    expect(betaOwnerAllowed(owner)).toBe(true);
    expect(betaOwnerAllowed(qa)).toBe(false);
  });

  it("denies protected requests when the allowlist cannot be read", async () => {
    vi.stubEnv("VITE_NC_BETA_MODE", "true");
    const response = await authorizeBetaRequest(
      new Request("https://noetharaclipz.lovable.app/dashboard", {
        headers: { cookie: "sb-test-auth-token=present" },
      }),
      null,
    );
    expect(response.response?.status).toBe(403);
    const missing = await authorizeBetaRequest(
      new Request("https://noetharaclipz.lovable.app/dashboard"),
      { owners: [] },
    );
    expect(missing.response?.status).toBe(403);
  });
});

describe("admission lookup", () => {
  it("denies a lookup error and a non-allowlisted account", async () => {
    vi.stubEnv("VITE_NC_BETA_MODE", "true");
    const rpc = vi.fn().mockRejectedValue(new Error("network down"));
    const client = { rpc } as unknown as SupabaseClient<Database>;
    await expect(requireCreatorAdmission(client, owner.id)).rejects.toThrow("could not be verified");
    rpc.mockClear();
    await expect(requireCreatorAdmission(client, qa.id)).rejects.toThrow("invited account");
    expect(rpc).not.toHaveBeenCalled();
  });
});
