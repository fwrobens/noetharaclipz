import { beforeEach, expect, it, vi } from "vitest";
const native = vi.hoisted(() => ({ getSession: vi.fn(), createSignedUrl: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({
  supabase: {
    auth: { getSession: native.getSession },
    storage: { from: () => ({ createSignedUrl: native.createSignedUrl }) },
  },
}));
import { clearMediaCache, downloadRenderedClip, signedMedia } from "@/lib/media";
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
const rendered =
  "21b61ad1-bda4-4abd-ac35-7a0bf477ed69/11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.mp4";
it("downloads a rendered clip through a session-signed private URL", async () => {
  native.getSession.mockResolvedValue({
    data: { session: { user: { id: "owner-a" } } },
    error: null,
  });
  native.createSignedUrl.mockResolvedValue({
    data: { signedUrl: "https://zxdnjnsghdnviflahvry.supabase.co/storage/v1/object/sign/rendered-clips/clip?token=short" },
    error: null,
  });
  const clicks: string[] = [];
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.href);
    });
  await downloadRenderedClip(rendered);
  click.mockRestore();
  expect(native.createSignedUrl).toHaveBeenCalledWith(rendered, 600, { download: "noetharaclipz.mp4" });
  expect(clicks[0]).toContain("/storage/v1/object/sign/");
  expect(clicks[0]).not.toContain("/object/public/");
});
it("refuses a download without a session or for a path outside rendered clips", async () => {
  native.getSession.mockResolvedValue({ data: { session: null }, error: null });
  await expect(downloadRenderedClip(rendered)).rejects.toThrow("Sign in");
  expect(native.createSignedUrl).not.toHaveBeenCalled();
  native.getSession.mockResolvedValue({
    data: { session: { user: { id: "owner-a" } } },
    error: null,
  });
  await expect(downloadRenderedClip("../source-videos/secret.mp4")).rejects.toThrow("Download failed");
  expect(native.createSignedUrl).not.toHaveBeenCalled();
});
