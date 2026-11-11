import { beforeEach, expect, it, vi } from "vitest";
const native = vi.hoisted(() => ({ getSession: vi.fn(), createSignedUrl: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({
  supabase: {
    auth: { getSession: native.getSession },
    storage: { from: () => ({ createSignedUrl: native.createSignedUrl }) },
  },
}));
import { clearMediaCache, signedMedia } from "@/lib/media";
beforeEach(() => {
  clearMediaCache();
  vi.clearAllMocks();
});
it("requires a session even when an earlier owner cached a download URL", async () => {
  native.getSession.mockResolvedValue({
    data: { session: { user: { id: "owner-a" } } },
    error: null,
  });
  native.createSignedUrl.mockResolvedValue({ data: { signedUrl: "private-a" }, error: null });
  expect(await signedMedia("rendered-clips", "a/clip.mp4")).toBe("private-a");
  native.getSession.mockResolvedValue({ data: { session: null }, error: null });
  await expect(signedMedia("rendered-clips", "a/clip.mp4")).rejects.toThrow("Sign in");
});
it("cannot reuse another owner's cached URL when RLS denies signing", async () => {
  native.getSession.mockResolvedValue({
    data: { session: { user: { id: "owner-a" } } },
    error: null,
  });
  native.createSignedUrl.mockResolvedValue({ data: { signedUrl: "private-a" }, error: null });
  await signedMedia("rendered-clips", "a/clip.mp4");
  native.getSession.mockResolvedValue({
    data: { session: { user: { id: "owner-b" } } },
    error: null,
  });
  native.createSignedUrl.mockResolvedValue({ data: null, error: new Error("RLS denied") });
  await expect(signedMedia("rendered-clips", "a/clip.mp4")).rejects.toThrow("RLS denied");
});
