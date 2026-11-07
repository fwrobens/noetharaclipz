import t1 from "@/assets/thumb-1.jpg";
import t2 from "@/assets/thumb-2.jpg";
import t3 from "@/assets/thumb-3.jpg";
import t4 from "@/assets/thumb-4.jpg";

export type Platform = "YouTube" | "Twitch" | "Kick" | "Upload";
export type Status = "ready" | "processing" | "queued";
export type Category = "Clutch" | "Funny" | "Hype" | "Reaction" | "Tutorial";

export interface Highlight {
  id: string;
  title: string;
  start: number; // seconds
  duration: number;
  score: number;
  category: Category;
}

export interface Project {
  id: string;
  title: string;
  thumb: string;
  platform: Platform;
  length: number; // seconds
  status: Status;
  edited: string;
  folder: "YouTube" | "TikTok" | "IG Reels";
  highlights: Highlight[];
  deleted?: boolean;
}

export const thumbs = [t1, t2, t3, t4];

const hl = (p: string, list: [string, number, number, number, Category][]): Highlight[] =>
  list.map(([title, start, duration, score, category], i) => ({ id: `${p}-h${i}`, title, start, duration, score, category }));

export const seedProjects: Project[] = [
  {
    id: "p1", title: "Ranked grind to Champion — 6h stream", thumb: t1, platform: "Twitch", length: 21540, status: "ready",
    edited: "2 hours ago", folder: "TikTok",
    highlights: hl("p1", [
      ["1v4 clutch with 2 HP left", 1820, 38, 97, "Clutch"],
      ["Chat goes wild after the snipe", 5410, 24, 92, "Hype"],
      ["Fell off the map mid-sentence", 8930, 19, 89, "Funny"],
      ["How I rotate late game", 12040, 52, 84, "Tutorial"],
      ["Reacting to the final circle", 17220, 31, 81, "Reaction"],
      ["Back-to-back victory royales", 20110, 44, 78, "Hype"],
    ]),
  },
  {
    id: "p2", title: "Worlds Quarterfinal watch party", thumb: t2, platform: "YouTube", length: 9240, status: "ready",
    edited: "Yesterday", folder: "YouTube",
    highlights: hl("p2", [
      ["Baron steal changes everything", 2210, 29, 95, "Hype"],
      ["Pentakill reaction", 4380, 22, 93, "Reaction"],
      ["Caster can't believe it", 6620, 18, 86, "Funny"],
      ["Draft breakdown explained", 7810, 58, 80, "Tutorial"],
    ]),
  },
  {
    id: "p3", title: "Building a sky castle — survival ep. 42", thumb: t3, platform: "YouTube", length: 5400, status: "processing",
    edited: "3 days ago", folder: "IG Reels",
    highlights: hl("p3", [
      ["Creeper ruins the bridge", 1220, 16, 90, "Funny"],
      ["Sunset timelapse reveal", 3910, 27, 88, "Hype"],
    ]),
  },
  {
    id: "p4", title: "Midnight drift league finals", thumb: t4, platform: "Kick", length: 7320, status: "ready",
    edited: "Last week", folder: "TikTok",
    highlights: hl("p4", [
      ["Photo-finish overtake", 3340, 21, 96, "Clutch"],
      ["Perfect 900° drift chain", 4720, 33, 91, "Hype"],
      ["Wall tap, still wins", 6010, 17, 85, "Funny"],
    ]),
  },
];

export const fmt = (s: number) => {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
};

export const suggestions = [
  "Find the 5 funniest moments for TikTok",
  "Clip every clutch play under 40 seconds",
  "Make a 60s recap with animated captions",
  "Pull chat's biggest hype reactions",
];

export const templates = [
  { name: "TikTok Hype", ratio: "9:16", desc: "Bold animated captions, facecam top", thumb: t1 },
  { name: "YouTube Shorts Recap", ratio: "9:16", desc: "Zoom cuts with progress bar", thumb: t2 },
  { name: "IG Reels Clean", ratio: "4:5", desc: "Minimal captions, soft fades", thumb: t3 },
  { name: "Highlight Montage", ratio: "16:9", desc: "Beat-synced cuts and flashes", thumb: t4 },
];
