import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/integrations/supabase/types";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requireCreatorAdmission } from "@/lib/creator-admission.server";

const owner = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69";
const current = {
  owner_id: owner,
  consent_id: "0e8f4eb3-53a9-4ad0-8aa0-d0b0a19dc2a2",
  approved_at: "2026-01-01T00:00:00Z",
  expires_at: "2099-01-01T00:00:00Z",
  revoked_at: null,
};
const rpc = vi.fn();
const client = { rpc } as unknown as SupabaseClient<Database>;
beforeEach(() => {
  vi.stubEnv("VITE_NC_BETA_MODE", "true");
  rpc.mockReset();
});
afterEach(() => vi.unstubAllEnvs());
describe("creator server upload admission", () => {
  it("rejects missing, unapproved, expired, revoked and mismatched-owner consent before reservation", async () => {
    for (const data of [
      null,
      { ...current, approved_at: null },
      { ...current, expires_at: "2026-01-01T00:00:00Z" },
      { ...current, revoked_at: "2026-01-01T00:00:00Z" },
      { ...current, owner_id: "11111111-1111-4111-8111-111111111111" },
    ]) {
      rpc.mockReset().mockResolvedValue({ data, error: null });
      await expect(requireCreatorAdmission(client, owner)).rejects.toThrow("active beta approval");
      expect(rpc).toHaveBeenCalledExactlyOnceWith("processing_consent");
    }
  });
  it("requires a ready scoped worker in addition to active consent", async () => {
    rpc
      .mockResolvedValueOnce({ data: current, error: null })
      .mockResolvedValueOnce({ data: { online: true, ai_ready: false }, error: null });
    await expect(requireCreatorAdmission(client, owner)).rejects.toThrow("temporarily unavailable");
    expect(rpc.mock.calls.map(([name]) => name)).toEqual(["processing_consent", "pipeline_health"]);
  });
  it("fails closed when the consent or readiness backend is unavailable", async () => {
    rpc.mockResolvedValue({ data: null, error: { message: "unavailable" } });
    await expect(requireCreatorAdmission(client, owner)).rejects.toThrow("could not be verified");
    rpc
      .mockResolvedValueOnce({ data: current, error: null })
      .mockResolvedValueOnce({ data: null, error: { message: "unavailable" } });
    await expect(requireCreatorAdmission(client, owner)).rejects.toThrow("temporarily unavailable");
  });
  it("accepts only the matching approved owner with a ready worker", async () => {
    rpc
      .mockResolvedValueOnce({ data: current, error: null })
      .mockResolvedValueOnce({ data: { online: true, ai_ready: true }, error: null });
    await expect(requireCreatorAdmission(client, owner)).resolves.toBeUndefined();
    expect(rpc.mock.calls.every((args) => args.length === 1)).toBe(true);
  });
});
