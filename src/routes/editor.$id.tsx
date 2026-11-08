import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowLeft, ArrowUp, Play, Pause, Scissors, Sparkles, Download, Loader2, User, Type, Crop, RectangleVertical } from "lucide-react";
import { toast } from "sonner";
import { useStore } from "@/lib/store";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/editor/$id")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Clip editor — Noethara Clipz" },
      { name: "description", content: "Trim, caption and reframe clips with AI commands." },
      { property: "og:title", content: "Clip editor — Noethara Clipz" },
      { property: "og:description", content: "Trim, caption and reframe clips with AI commands." },
    ],
  }),
  component: Editor,
});

const ratios = { "9:16": "aspect-[9/16] max-h-[60vh]", "1:1": "aspect-square max-h-[55vh]", "4:5": "aspect-[4/5] max-h-[58vh]", "16:9": "aspect-video w-full" } as const;
type Ratio = keyof typeof ratios;
const captionStyles = ["Bold pop", "Karaoke", "Minimal", "Neon"] as const;
const facecams = ["Top", "Bottom", "Corner", "Off"] as const;
const tabs = [
  { id: "captions", label: "Captions", icon: Type },
  { id: "frame", label: "Frame", icon: Crop },
  { id: "facecam", label: "Facecam", icon: User },
] as const;

function Editor() {
  const { id } = Route.useParams();
  const [pid, hid] = id.split("~");
  const { projects } = useStore();
  const project = projects.find((p) => p.id === pid);
  const clip = project?.highlights.find((h) => h.id === hid) ?? project?.highlights[0];

  const [ratio, setRatio] = useState<Ratio>("9:16");
  const [trim, setTrim] = useState<[number, number]>([0, clip?.duration ?? 30]);
  const [captions, setCaptions] = useState(true);
  const [capStyle, setCapStyle] = useState<(typeof captionStyles)[number]>("Bold pop");
  const [capSize, setCapSize] = useState([28]);
  const [focus, setFocus] = useState<"Face" | "Gameplay" | "Auto">("Auto");
  const [facecam, setFacecam] = useState<(typeof facecams)[number]>("Top");
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("captions");
  const [playing, setPlaying] = useState(false);
  const [cmd, setCmd] = useState("");
  const [thinking, setThinking] = useState(false);
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [splits, setSplits] = useState<number[]>([]);
  const [captionText, setCaptionText] = useState("NO WAY HE HIT THAT");

  if (!project || !clip) return <div className="p-10 text-center text-muted-foreground">Clip not found. <Link to="/" className="text-primary">Go home</Link></div>;
  const max = Math.max(clip.duration, 60);

  const runAi = (raw = cmd) => {
    const t = raw.toLowerCase().trim();
    if (!t) return;
    setCmd("");
    setThinking(true);
    setAiNote(null);
    setTimeout(() => {
      const notes: string[] = [];
      const num = t.match(/(\d+)\s*(s|sec|second)/);
      if (num) { const n = Math.min(+(num[1] ?? 0), max); setTrim([0, n]); notes.push(`trimmed to ${n}s`); }
      if (t.includes("subtitle") || t.includes("caption")) { setCaptions(true); setCapStyle(t.includes("animated") ? "Karaoke" : "Bold pop"); notes.push("added animated captions"); setTab("captions"); }
      if (t.includes("gameplay")) { setFocus("Gameplay"); notes.push("crop focused on gameplay"); setTab("frame"); }
      if (t.includes("face")) { setFocus("Face"); notes.push("crop follows your face"); }
      if (t.includes("tiktok") || t.includes("short") || t.includes("reel") || t.includes("vertical")) { setRatio("9:16"); setCaptions(true); setFacecam("Top"); notes.push("made a 9:16 version with facecam on top"); }
      if (t.includes("square")) { setRatio("1:1"); notes.push("switched to 1:1"); }
      if (t.includes("landscape") || t.includes("youtube")) { setRatio("16:9"); notes.push("switched to 16:9"); }
      setAiNote(notes.length ? `Done — ${notes.join(", ")}.` : "I couldn't map that to an edit yet. Try “make this 45 seconds” or “focus on the gameplay”.");
      setThinking(false);
    }, 1100);
  };

  const len = trim[1] - trim[0];

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-3 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <Link to="/project/$id" params={{ id: project.id }} className="shrink-0 rounded-lg p-2 hover:bg-muted" aria-label="Back"><ArrowLeft className="h-4 w-4" /></Link>
          <p className="truncate text-sm font-semibold">{clip.title}</p>
        </div>
        <button onClick={() => toast.success(`Exported ${len}s clip in ${ratio}`)} className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-pop transition hover:-translate-y-0.5"><Download className="h-4 w-4" /> Export</button>
      </div>

      <div className="flex flex-1 flex-col lg:flex-row">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="relative flex flex-1 items-center justify-center bg-surface p-4 sm:p-8">
            <div className={cn("relative overflow-hidden rounded-2xl bg-foreground shadow-float transition-all duration-500", ratios[ratio], ratio === "16:9" ? "max-w-3xl" : "")}>
              <img src={project.thumb} alt="" className={cn("h-full w-full object-cover transition-all duration-500", focus === "Gameplay" ? "object-right" : focus === "Face" ? "object-left" : "object-center")} />
              {facecam !== "Off" && ratio !== "16:9" && (
                <div className={cn("absolute overflow-hidden rounded-xl border-2 border-background/70 shadow-float transition-all",
                  facecam === "Top" && "inset-x-3 top-3 h-1/4", facecam === "Bottom" && "inset-x-3 bottom-3 h-1/4", facecam === "Corner" && "right-3 top-3 h-1/5 w-2/5")}>
                  <img src={project.thumb} alt="" className="h-full w-full scale-150 object-cover object-left" />
                </div>
              )}
              {captions && (
                <p style={{ fontSize: (capSize[0] ?? 28) * (ratio === "16:9" ? 0.8 : 0.6) }}
                  className={cn("absolute inset-x-4 bottom-[18%] text-center font-display font-bold uppercase leading-tight drop-shadow-lg",
                    capStyle === "Bold pop" && "text-background [-webkit-text-stroke:1px_var(--foreground)]",
                    capStyle === "Karaoke" && "text-warning", capStyle === "Minimal" && "font-sans font-medium normal-case text-background",
                    capStyle === "Neon" && "text-glow-2")}>
                  {captionText}
                </p>
              )}
              <button onClick={() => setPlaying(!playing)} className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-card/90 text-foreground shadow-float transition hover:scale-110" aria-label="Play">
                {playing ? <Pause className="h-5 w-5" /> : <Play className="ml-0.5 h-5 w-5" />}
              </button>
            </div>

            <div className="absolute inset-x-3 bottom-3 mx-auto max-w-xl sm:bottom-5">
              {aiNote && <div className="mb-2 flex items-start gap-2 rounded-xl border bg-popover px-3 py-2 text-sm shadow-pop animate-fade-up"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> {aiNote}</div>}
              <div className="glow-ring flex items-center gap-2 rounded-2xl bg-card p-1.5 pl-3 shadow-float">
                {thinking ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" /> : <Sparkles className="h-4 w-4 shrink-0 text-primary" />}
                <input value={cmd} onChange={(e) => setCmd(e.target.value)} onKeyDown={(e) => e.key === "Enter" && runAi()} placeholder="“Make this clip 45 seconds”" className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
                <button onClick={() => runAi()} className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-foreground text-background shadow-pop" aria-label="Run"><ArrowUp className="h-4 w-4" /></button>
              </div>
              <div className="no-scrollbar mt-2 flex gap-1.5 overflow-x-auto">
                {["Make this clip 45 seconds", "Add animated subtitles", "Focus the crop on the gameplay", "Create a TikTok version"].map((s) => (
                  <button key={s} onClick={() => runAi(s)} className="shrink-0 rounded-full border bg-card/90 px-2.5 py-1 text-xs shadow-soft backdrop-blur hover:shadow-pop">{s}</button>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-3 border-t bg-card p-3 sm:p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span className="font-mono">Length {len}s · {trim[0]}s → {trim[1]}s</span>
              <button onClick={() => { setSplits((s) => [...s, Math.round((trim[0] + trim[1]) / 2)]); toast("Split added"); }} className="flex items-center gap-1 rounded-lg border px-2 py-1 text-foreground shadow-soft hover:shadow-pop"><Scissors className="h-3.5 w-3.5" /> Split</button>
            </div>
            <div className="relative">
              <div className="flex h-12 gap-0.5 overflow-hidden rounded-xl">
                {Array.from({ length: 12 }).map((_, i) => <img key={i} src={project.thumb} alt="" className="h-full flex-1 object-cover opacity-80" style={{ objectPosition: `${(i / 11) * 100}% 50%` }} />)}
              </div>
              {splits.map((s, i) => <span key={i} className="absolute inset-y-0 w-0.5 bg-warning shadow-pop" style={{ left: `${(s / max) * 100}%` }} />)}
            </div>
            <div className="flex h-8 items-center gap-px rounded-lg bg-muted px-1">
              {Array.from({ length: 120 }).map((_, i) => <span key={i} className="flex-1 rounded-full bg-primary/60" style={{ height: `${15 + Math.abs(Math.sin(i * 0.9) * Math.cos(i * 0.3)) * 80}%` }} />)}
            </div>
            <Slider value={trim} min={0} max={max} step={1} onValueChange={(v) => setTrim([v[0] ?? 0, v[1] ?? max])} aria-label="Trim" />
          </div>
        </div>

        <aside className="w-full shrink-0 border-t bg-sidebar lg:w-80 lg:border-l lg:border-t-0">
          <div className="flex gap-1 border-b p-2">
            {tabs.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} className={cn("flex flex-1 items-center justify-center gap-1.5 rounded-xl py-2 text-sm", tab === t.id ? "bg-card font-medium shadow-pop ring-1 ring-border" : "text-muted-foreground hover:text-foreground")}>
                <t.icon className="h-4 w-4" /> {t.label}
              </button>
            ))}
          </div>
          <div className="space-y-5 p-4">
            {tab === "captions" && (
              <>
                <label className="flex items-center justify-between text-sm">Show captions <Switch checked={captions} onCheckedChange={setCaptions} /></label>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Caption text</p>
                  <input value={captionText} onChange={(e) => setCaptionText(e.target.value)} className="w-full rounded-xl border bg-card px-3 py-2 text-sm shadow-soft outline-none focus:ring-2 focus:ring-ring/40" />
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Template</p>
                  <div className="grid grid-cols-2 gap-2">
                    {captionStyles.map((s) => <button key={s} onClick={() => setCapStyle(s)} className={cn("rounded-xl border px-3 py-2 text-sm transition", capStyle === s ? "border-primary bg-accent shadow-pop" : "bg-card hover:shadow-soft")}>{s}</button>)}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Size · {capSize[0]}px</p>
                  <Slider value={capSize} min={16} max={48} step={1} onValueChange={setCapSize} />
                </div>
              </>
            )}
            {tab === "frame" && (
              <>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Aspect ratio</p>
                  <div className="grid grid-cols-4 gap-2">
                    {(Object.keys(ratios) as Ratio[]).map((r) => (
                      <button key={r} onClick={() => setRatio(r)} className={cn("flex flex-col items-center gap-1 rounded-xl border py-2 text-xs transition", ratio === r ? "border-primary bg-accent shadow-pop" : "bg-card hover:shadow-soft")}><RectangleVertical className="h-4 w-4" />{r}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Smart crop focus</p>
                  <div className="grid grid-cols-3 gap-2">
                    {(["Auto", "Face", "Gameplay"] as const).map((f) => <button key={f} onClick={() => setFocus(f)} className={cn("rounded-xl border py-2 text-sm transition", focus === f ? "border-primary bg-accent shadow-pop" : "bg-card hover:shadow-soft")}>{f}</button>)}
                  </div>
                </div>
              </>
            )}
            {tab === "facecam" && (
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">Facecam position</p>
                <div className="grid grid-cols-2 gap-2">
                  {facecams.map((f) => <button key={f} onClick={() => setFacecam(f)} className={cn("rounded-xl border py-2 text-sm transition", facecam === f ? "border-primary bg-accent shadow-pop" : "bg-card hover:shadow-soft")}>{f}</button>)}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">Facecam shows on vertical and square formats.</p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
