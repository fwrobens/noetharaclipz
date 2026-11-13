import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  rpc: vi.fn(),
  options: {} as Record<string, unknown>,
}));
vi.mock("@/lib/supabase/client", () => ({
  supabase: { auth: { getSession: mocks.getSession }, rpc: mocks.rpc },
}));
vi.mock("tus-js-client", () => ({
  Upload: class {
    constructor(_file: File, options: Record<string, unknown>) {
      mocks.options = options;
    }
    findPreviousUploads() {
      return Promise.resolve([]);
    }
    start() {
      (mocks.options["onSuccess"] as () => void)();
    }
  },
}));
import { uploadVideo } from "@/lib/upload";
const video = new File(["transport unit test"], "sample.mp4", { type: "video/mp4" });
const prepared = {
  project_id: "new-project",
  video_id: "new-video",
  path: "owner/new-project/source.mp4",
};
beforeEach(() => {
  vi.stubEnv("VITE_NC_BETA_MODE", "false");
  mocks.getSession.mockResolvedValue({
    data: { session: { access_token: "owner-jwt", user: { id: "owner" } } },
  });
  mocks.rpc.mockReset();
});
afterEach(() => vi.unstubAllEnvs());
describe("dashboard resumable upload integration", () => {
  it("uses the authenticated server reservation, private TUS upload and normal server finalization", async () => {
    const prepare = vi.fn().mockResolvedValue(prepared);
    const finalize = vi.fn().mockResolvedValue({});
    await expect(
      uploadVideo(video, "gaming", "request", () => {}, new AbortController().signal, {
        prepare,
        finalize,
      }),
    ).resolves.toBe("new-project");
    expect(prepare).toHaveBeenCalledWith({
      requestId: "request",
      filename: "sample.mp4",
      mime: "video/mp4",
      bytes: video.size,
      instructions: "gaming",
    });
    expect(mocks.options).toMatchObject({
      headers: { authorization: "Bearer owner-jwt" },
      metadata: { bucketName: "source-videos", objectName: prepared.path },
      chunkSize: 6 * 1024 * 1024,
    });
    expect(await (mocks.options["fingerprint"] as () => Promise<string>)()).toContain(
      "owner:owner/new-project/source.mp4",
    );
    expect(finalize).toHaveBeenCalledExactlyOnceWith("new-project");
    expect(mocks.rpc).not.toHaveBeenCalled();
  });
  it("does not reserve or finalize a cancelled upload", async () => {
    const controller = new AbortController();
    controller.abort();
    const backend = { prepare: vi.fn(), finalize: vi.fn() };
    await expect(
      uploadVideo(video, "gaming", "request", () => {}, controller.signal, backend),
    ).rejects.toThrow("cancelled");
    expect(backend.prepare).not.toHaveBeenCalled();
    expect(backend.finalize).not.toHaveBeenCalled();
  });
});
