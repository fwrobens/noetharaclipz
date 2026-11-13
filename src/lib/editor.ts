import { z } from "zod";
import type { Highlight } from "./domain";
export const editSchema = z
  .object({
    version: z.literal(1),
    start: z.number().finite().min(0),
    end: z.number().finite().positive(),
    ratio: z.enum(["9:16", "16:9", "1:1", "4:5"]),
    crop_x: z.number().min(0).max(1),
    crop_y: z.number().min(0).max(1),
    volume: z.number().min(0).max(2),
    captions: z.boolean(),
    caption_style: z.enum(["Bold pop", "Karaoke", "Minimal", "Neon"]),
    caption_size: z.number().int().min(16).max(72),
    caption_color: z.string().regex(/^#[0-9a-fA-F]{6}$/),
    caption_overrides: z.record(z.string().max(500)),
    font: z.enum(["Bricolage Grotesque", "Instrument Sans", "Mono"]),
  })
  .strict()
  .refine((e) => e.end > e.start && e.end - e.start <= 60, "Clip must be at most 60 seconds");
export type ClipEdit = z.infer<typeof editSchema>;
export const defaultEdit = (h: Highlight): ClipEdit => ({
  version: 1,
  start: h.start,
  end: h.start + Math.min(h.duration, 60),
  ratio: "9:16",
  crop_x: 0.5,
  crop_y: 0.5,
  volume: 1,
  captions: true,
  caption_style: "Bold pop",
  caption_size: 28,
  caption_color: "#FFFFFF",
  caption_overrides: {},
  font: "Instrument Sans",
});
export const activeJob = (status: string) => !["completed", "failed", "cancelled"].includes(status);
export type TranscriptSegment = {
  id: string;
  start: number;
  end: number;
  text: string;
  words?: { start: number; end: number; text: string }[];
};
