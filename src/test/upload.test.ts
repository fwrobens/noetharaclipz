import { describe, it, expect } from "vitest";
import { validateVideo } from "@/lib/upload";
describe("Upload validation", () => {
  it("rejects non-media", () =>
    expect(() => validateVideo(new File(["text"], "script.txt", { type: "text/plain" }))).toThrow(
      "MP4",
    ));
  it("rejects empty uploads", () =>
    expect(() => validateVideo(new File([], "empty.mp4", { type: "video/mp4" }))).toThrow("45 MB"));
  it("accepts allowed containers for worker inspection", () =>
    expect(() =>
      validateVideo(
        new File(["container inspected by worker"], "video.mp4", { type: "video/mp4" }),
      ),
    ).not.toThrow());
});
