import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { ArrowUp, Upload, Sparkles, Video, FilePlus2, Wand2, Captions, Crop, Mic } from "lucide-react";
import { toast } from "sonner";
import { useStore } from "@/lib/store";
import { suggestions } from "@/lib/mock";
import { VideoCard } from "@/components/VideoCard";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Clipwave — Turn streams into viral clips with AI" },
      { name: "description", content: "Paste a link or upload a video, tell the AI what you want, and get ready-to-post highlights." },
      { property: "og:title", content: "Clipwave — Turn streams into viral clips with AI" },
      { property: "og:description", content: "Paste a link or upload a video, tell the AI what you want, and get ready-to-post highlights." },
    ],
  }),
  component: Home,
});

const modes = [
  { id: "ai", label: "AI Clips", icon: Sparkles },
  { id: "rec", label: "Record Video", icon: Video },
  { id: "blank", label: "Blank Project", icon: FilePlus2 },
] as const;

const tools = [
  { icon: Wand2, label: "Long video to shorts" },
  { icon: Captions, label: "Auto captions" },
  { icon: Crop, label: "Smart reframe" },
  { icon: Mic, label: "Enhance speech" },
];

function Home() {
  const { projects, createProject } = useStore();
  const nav = useNavigate();
  const [mode, setMode] = useState<(typeof modes)[number]["id"]>("ai");
  const [text, setText] = useState("");
  const [file, setFile] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = (value = text) => {
    const v = value.trim() || (file ? `Find the best moments in ${file}` : "");
    if (!v) return toast("Paste a link or describe what you want first");
    const id = createProject(v);
    nav({ to: "/project/$id", params: { id } });
  };

  const recent = projects.filter((p) => !p.deleted);

  return (
    <div className="animate-fade-up">
      <section className="relative px-4 pb-14 pt-12 sm:px-8 sm:pt-20">
        <div className="pointer-events-none absolute inset-x-0 top-10 mx-auto h-80 max-w-3xl glow-halo opacity-80" />
        <div className="relative mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-bold sm:text-5xl">What are we clipping today?</h1>
          <p className="mt-3 text-sm text-muted-foreground sm:text-base">Drop a stream link or upload a video. Tell the AI what you want.</p>
        </div>

        <div className="relative mx-auto mt-8 max-w-2xl">
          <div className="no-scrollbar mb-2 flex gap-1 overflow-x-auto">
            {modes.map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                className={cn(
                  "flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm transition",
                  mode === m.id ? "bg-card font-medium shadow-pop ring-1 ring-border" : "text-muted-foreground hover:bg-card/60",
                )}
              >
                <m.icon className={cn("h-4 w-4", mode === m.id && "text-primary")} /> {m.label}
              </button>
            ))}
          </div>
          <div className="glow-ring rounded-3xl bg-card shadow-float">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
              rows={3}
              placeholder={mode === "rec" ? "Describe what you'll record…" : mode === "blank" ? "Name your project…" : "Paste a YouTube/Twitch link, or say “clip the funniest moments”…"}
              className="w-full resize-none rounded-t-3xl bg-transparent px-5 pt-5 text-base outline-none placeholder:text-muted-foreground"
            />
            <div className="flex items-center justify-between gap-2 px-3 pb-3">
              <input ref={fileRef} type="file" accept="video/*" hidden onChange={(e) => setFile(e.target.files?.[0]?.name ?? null)} />
              <button onClick={() => fileRef.current?.click()} className="flex min-w-0 items-center gap-2 rounded-xl border bg-background px-3 py-2 text-sm shadow-soft transition hover:shadow-pop">
                <Upload className="h-4 w-4 shrink-0" /> <span className="truncate">{file ?? "Upload video"}</span>
              </button>
              <button onClick={() => submit()} aria-label="Generate" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-foreground text-background shadow-pop transition hover:scale-105 active:scale-95">
                <ArrowUp className="h-5 w-5" />
              </button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {suggestions.map((s) => (
              <button key={s} onClick={() => submit(s)} className="rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-soft transition hover:-translate-y-0.5 hover:text-foreground hover:shadow-pop sm:text-sm">
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="relative mx-auto mt-10 grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
          {tools.map((t) => (
            <button key={t.label} onClick={() => setText(t.label + ": ")} className="flex items-center gap-2 rounded-2xl border bg-card p-3 text-left text-sm lift">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent text-accent-foreground"><t.icon className="h-4 w-4" /></span>
              <span className="min-w-0 leading-tight">{t.label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="border-t bg-surface px-4 py-8 sm:px-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent videos</h2>
          <button onClick={() => nav({ to: "/library" })} className="text-sm text-primary hover:underline">See all</button>
        </div>
        <div className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-4 sm:-mx-8 sm:px-8">
          {recent.map((p) => (
            <VideoCard key={p.id} p={p} className="w-64 shrink-0 snap-start sm:w-72" />
          ))}
        </div>
      </section>
    </div>
  );
}
