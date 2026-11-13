import type { Tables } from "@/integrations/supabase/types";
import t1 from "@/assets/thumb-1.jpg";
import t2 from "@/assets/thumb-2.jpg";
import t3 from "@/assets/thumb-3.jpg";
import t4 from "@/assets/thumb-4.jpg";
export type Category = "Clutch" | "Funny" | "Hype" | "Reaction" | "Tutorial" | "Other";
export interface Highlight {
  id: string;
  title: string;
  start: number;
  duration: number;
  score: number;
  category: Category;
  explanation: string;
}
export interface Project {
  id: string;
  title: string;
  thumb: string;
  platform: string;
  length: number;
  status: string;
  edited: string;
  folder: string;
  highlights: Highlight[];
  deleted: boolean;
  video: Tables<"videos"> | undefined;
}
export const fmt = (s: number) => {
  const n = Math.max(0, Math.floor(s));
  const sec = String(n % 60).padStart(2, "0"),
    m = String(Math.floor(n / 60) % 60).padStart(2, "0");
  return n >= 3600 ? `${Math.floor(n / 3600)}:${m}:${sec}` : `${m}:${sec}`;
};
export const suggestions = [
  "Find the 5 funniest moments for TikTok",
  "Clip every clutch play under 40 seconds",
  "Make a 60s recap with captions",
  "Find the biggest reactions",
];
// Static style references, never presented as imported videos or detected moments.
export const templates = [
  { name: "TikTok Hype", ratio: "9:16", desc: "Bold captions, vertical crop", thumb: t1 },
  { name: "YouTube Shorts Recap", ratio: "9:16", desc: "Karaoke captions", thumb: t2 },
  { name: "IG Reels Clean", ratio: "4:5", desc: "Minimal captions", thumb: t3 },
  { name: "Highlight Montage", ratio: "16:9", desc: "Landscape framing", thumb: t4 },
];
export type ChatMsg = {
  id: string;
  role: "user" | "ai" | "system";
  text: string;
  clipIds?: string[] | undefined;
};
