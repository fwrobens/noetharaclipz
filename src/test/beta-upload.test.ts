import { afterEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ rpc: vi.fn(), requireBetaAdmission: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({ supabase: { rpc: mocks.rpc } }));
vi.mock("@/lib/processing-consent", () => ({ requireBetaAdmission: mocks.requireBetaAdmission }));
import { uploadVideo } from "@/lib/upload";
afterEach(() => vi.unstubAllEnvs());
it("rejects an unapproved beta upload before storage reservation or TUS", async () => {
  vi.stubEnv("VITE_NC_BETA_MODE", "true");
  mocks.requireBetaAdmission.mockRejectedValue(new Error("active beta approval required"));
  await expect(
    uploadVideo(
      new File(["media"], "sample.mp4", { type: "video/mp4" }),
      "gaming",
      crypto.randomUUID(),
      () => {},
      new AbortController().signal,
    ),
  ).rejects.toThrow("approval required");
  expect(mocks.rpc).not.toHaveBeenCalled();
});
