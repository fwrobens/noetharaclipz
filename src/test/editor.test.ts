import { describe, it, expect } from "vitest";
import { defaultEdit, editSchema } from "@/lib/editor";
const edit = defaultEdit({
  id: "h",
  title: "Event",
  category: "Other",
  start: 10,
  duration: 25,
  score: 80,
  explanation: "Observed",
});
describe("Persistent clip edits", () => {
  it("uses source timestamps", () => {
    expect(edit.start).toBe(10);
    expect(edit.end).toBe(35);
  });
  it.each([
    { end: 100 },
    { start: -1 },
    { crop_x: 2 },
    { volume: 8 },
    { caption_color: "javascript:bad" },
    { start: Number.NaN },
  ])("rejects unsafe edit %j", (change) => {
    expect(editSchema.safeParse({ ...edit, ...change }).success).toBe(false);
  });
  it("rejects arbitrary model operations", () => {
    expect(editSchema.safeParse({ ...edit, command: "shell" }).success).toBe(false);
  });
});
