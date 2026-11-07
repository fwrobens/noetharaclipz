import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp, Play, Pause, Paperclip, PanelLeftClose, PanelLeft, Sparkles, Check, Scissors,
  Download, Trash2, Loader2, MessageSquare, Clapperboard, Bookmark,
} from "lucide-react";
import { toast } from "sonner";
import { useStore, streamText, type ChatMsg } from "@/lib/store";
import { fmt, type Category, type Highlight } from "@/lib/mock";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/project/$id")({
  head: () => ({
    meta: [
      { title: "Project workspace — Clipwave" },
      { name: "description", content: "Chat with the AI and review detected highlights." },
      { property: "og:title", content: "Project workspace — Clipwave" },
      { property: "og:description", content: "Chat with the AI and review detected highlights." },
    ],
  }),
  component: Workspace,
});

const cats: ("All" | Category)[] = ["All", "Clutch", "Hype", "Funny", "Reaction", "Tutorial"];
const commands = ["Make them shorter", "Find more funny moments", "Add captions to all", "Export for TikTok"];

const genHighlights = (pid: string, len: number, n: number, cat?: Category): Highlight[] => {
  const titles: [string, Category][] = [
    ["Insane comeback in overtime", "Clutch"], ["Chat spams POG", "Hype"], ["Accidental team wipe", "Funny"],
    ["Genuine shock reaction", "Reaction"], ["Pro tip: peek timing", "Tutorial"], ["Last-second save", "Clutch"],
  ];
  return Array.from({ length: n }, (_, i) => {
    const [title, c] = cat ? [titles.find((t) => t[1] === cat)![0] + ` #${i + 1}`, cat] : titles[i % titles.length]!;
    return { id: `${pid}-g${Date.now()}-${i}`, title, category: c, start: Math.floor(((i + 1) / (n + 1)) * len), duration: 15 + ((i * 7) % 35), score: 96 - i * 3 };
  });
};

function Workspace() {
  const { id } = Route.useParams();
  const { projects, chats, pushMsg, updateMsg, addHighlights, setDeleted } = useStore();
  const nav = useNavigate();
  const project = projects.find((p) => p.id === id);
  const msgs = chats[id] ?? [];
  const [chatOpen, setChatOpen] = useState(true);
  const [mobileTab, setMobileTab] = useState<"chat" | "clips">("clips");
  const [cat, setCat] = useState<(typeof cats)[number]>("All");
  const [selected, setSelected] = useState<string[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const started = useRef(false);
  const endRef = useRef<HTMLDivElement>(null);

  const reply = (text: string, newClips?: Highlight[]) => {
    const mid = `a${Date.now()}`;
    setBusy(true);
    pushMsg(id, { id: mid, role: "ai", text: "" });
    setTimeout(() => {
      streamText(text, (t) => updateMsg(id, mid, t), () => {
        if (newClips?.length) {
          addHighlights(id, newClips);
          updateMsg(id, mid, text, newClips.map((c) => c.id));
          setActiveId(newClips[0]!.id);
        }
        setBusy(false);
      });
    }, 900);
  };

  useEffect(() => {
    if (!project || started.current) return;
    started.current = true;
    if (project.status === "processing" && msgs.length === 1) {
      setMobileTab("chat");
      reply("I scanned the full video, transcribed the audio and checked chat activity spikes. Here are the strongest moments I found — tap any clip to preview it.", genHighlights(id, project.length, 5));
    } else if (!msgs.length) {
      pushMsg(id, { id: "intro", role: "ai", text: `I found ${project.highlights.length} highlights in this video. Ask me to find more, change lengths, or prep them for a platform.` });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const clips = useMemo(() => (project?.highlights ?? []).filter((h) => cat === "All" || h.category === cat), [project, cat]);
  const active = project?.highlights.find((h) => h.id === activeId) ?? project?.highlights[0];

  if (!project) {
    return <div className="p-10 text-center text-muted-foreground">Project not found. <Link to="/" className="text-primary">Go home</Link></div>;
  }

  const send = (v = input) => {
    const t = v.trim();
    if (!t || busy) return;
    setInput("");
    pushMsg(id, { id: `u${Date.now()}`, role: "user", text: t });
    const low = t.toLowerCase();
    if (low.includes("export") || low.includes("tiktok")) {
      reply("Done — I'll prep the selected clips in 9:16 with animated captions. Opening export options.");
      setTimeout(() => setExportOpen(true), 2200);
    } else if (low.includes("funny")) reply("Found 2 more funny moments based on laughter in the audio:", genHighlights(id, project.length, 2, "Funny"));
    else if (low.includes("clutch")) reply("Here are more clutch plays:", genHighlights(id, project.length, 2, "Clutch"));
    else if (low.includes("short")) reply("Trimmed versions under 20 seconds, keeping the payoff moment:", genHighlights(id, project.length, 3).map((h) => ({ ...h, duration: 12 + (h.score % 7), title: h.title + " (short)" })));
    else if (low.includes("caption")) reply("Animated captions are now applied to every clip in this project. You can tweak the style in the editor.");
    else reply("Got it. Here's what I found for that request:", genHighlights(id, project.length, 2));
  };

  const toggleSel = (hid: string) => setSelected((s) => (s.includes(hid) ? s.filter((x) => x !== hid) : [...s, hid]));

  const chatPanel = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-primary-foreground shadow-pop"><Scissors className="h-3.5 w-3.5" /></span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Clipwave AI</p>
          <p className="truncate text-xs text-muted-foreground">{project.title}</p>
        </div>
        <button onClick={() => setChatOpen(false)} className="hidden rounded-lg p-1.5 text-muted-foreground hover:bg-muted lg:block" aria-label="Collapse chat"><PanelLeftClose className="h-4 w-4" /></button>
      </div>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        {msgs.map((m) => <Message key={m.id} m={m} project={project} onPick={(cid) => { setActiveId(cid); setMobileTab("clips"); }} />)}
        {busy && msgs.at(-1)?.text === "" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin text-primary" /> Analyzing video…</div>
        )}
        <div ref={endRef} />
      </div>
      <div className="border-t p-3">
        <div className="no-scrollbar mb-2 flex gap-1.5 overflow-x-auto">
          {commands.map((c) => (
            <button key={c} onClick={() => send(c)} className="shrink-0 rounded-full border bg-card px-2.5 py-1 text-xs text-muted-foreground shadow-soft hover:text-foreground hover:shadow-pop">{c}</button>
          ))}
        </div>
        <div className="glow-ring flex items-end gap-2 rounded-2xl bg-card p-2 shadow-pop">
          <button onClick={() => toast("Attach a video to add it to this project")} className="rounded-lg p-2 text-muted-foreground hover:bg-muted" aria-label="Attach"><Paperclip className="h-4 w-4" /></button>
          <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} rows={1} placeholder="Ask for changes…" className="min-h-9 flex-1 resize-none bg-transparent py-2 text-sm outline-none" />
          <button onClick={() => send()} disabled={busy} className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-foreground text-background shadow-pop transition hover:scale-105 disabled:opacity-40" aria-label="Send"><ArrowUp className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col lg:flex-row">
      <div className="flex border-b p-2 lg:hidden">
        {(["chat", "clips"] as const).map((t) => (
          <button key={t} onClick={() => setMobileTab(t)} className={cn("flex flex-1 items-center justify-center gap-1.5 rounded-xl py-2 text-sm", mobileTab === t ? "bg-card font-medium shadow-pop ring-1 ring-border" : "text-muted-foreground")}>
            {t === "chat" ? <MessageSquare className="h-4 w-4" /> : <Clapperboard className="h-4 w-4" />} {t === "chat" ? "AI chat" : `Clips (${project.highlights.length})`}
          </button>
        ))}
      </div>

      <aside className={cn("min-h-0 border-r bg-sidebar transition-all duration-300 lg:block lg:h-full", chatOpen ? "lg:w-96" : "lg:w-0 lg:overflow-hidden lg:border-0", mobileTab === "chat" ? "flex-1" : "hidden")}>
        {chatPanel}
      </aside>

      <section className={cn("min-h-0 flex-1 overflow-y-auto", mobileTab === "clips" ? "block" : "hidden lg:block")}>
        <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
          <div className="flex items-center gap-2">
            {!chatOpen && (
              <button onClick={() => setChatOpen(true)} className="hidden items-center gap-1.5 rounded-xl border bg-card px-3 py-1.5 text-sm shadow-soft hover:shadow-pop lg:flex"><PanelLeft className="h-4 w-4" /> AI chat</button>
            )}
            <h1 className="min-w-0 flex-1 truncate text-lg font-semibold sm:text-xl">{project.title}</h1>
            <button onClick={() => { setDeleted(project.id, true); toast("Moved to Recently Deleted"); nav({ to: "/library" }); }} className="rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-destructive" aria-label="Delete project"><Trash2 className="h-4 w-4" /></button>
          </div>

          <div className="overflow-hidden rounded-3xl border bg-card shadow-float">
            <div className="relative aspect-video bg-foreground">
              <img src={project.thumb} alt="" className={cn("h-full w-full object-cover transition", playing && "scale-[1.02]")} />
              <div className="absolute inset-0 bg-gradient-to-t from-foreground/60 via-transparent to-transparent" />
              <button onClick={() => setPlaying((p) => !p)} className="absolute left-1/2 top-1/2 grid h-14 w-14 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-card/90 text-foreground shadow-float backdrop-blur transition hover:scale-110 sm:h-16 sm:w-16" aria-label="Play">
                {playing ? <Pause className="h-6 w-6" /> : <Play className="ml-1 h-6 w-6" />}
              </button>
              {active && (
                <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center gap-2 text-background">
                  <span className="rounded-lg bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground shadow-pop">{active.category}</span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{active.title}</span>
                  <span className="font-mono text-xs">{fmt(active.start)} · {active.duration}s</span>
                </div>
              )}
            </div>
            <Timeline length={project.length} clips={project.highlights} activeId={active?.id} onPick={setActiveId} />
          </div>

          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
            <div className="no-scrollbar flex gap-1.5 overflow-x-auto">
              {cats.map((c) => (
                <button key={c} onClick={() => setCat(c)} className={cn("shrink-0 rounded-full border px-3 py-1 text-sm transition", cat === c ? "bg-foreground text-background shadow-pop" : "bg-card shadow-soft hover:shadow-pop")}>{c}</button>
              ))}
            </div>
            <button onClick={() => setSelected(selected.length ? [] : clips.map((c) => c.id))} className="text-sm text-primary">{selected.length ? "Clear" : "Select all"}</button>
          </div>

          {project.highlights.length === 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="rounded-2xl border bg-card p-3 shadow-soft"><Skeleton className="aspect-video w-full rounded-xl" /><Skeleton className="mt-3 h-4 w-3/4" /><Skeleton className="mt-2 h-3 w-1/2" /></div>
              ))}
            </div>
          ) : (
            <div className="grid gap-4 pb-24 sm:grid-cols-2 xl:grid-cols-3">
              {clips.map((h) => (
                <HighlightCard key={h.id} h={h} thumb={project.thumb} active={active?.id === h.id} selected={selected.includes(h.id)} onPick={() => setActiveId(h.id)} onSelect={() => toggleSel(h.id)} />
              ))}
            </div>
          )}
        </div>

        {selected.length > 0 && (
          <div className="fixed inset-x-3 bottom-4 z-40 mx-auto flex max-w-lg items-center gap-2 rounded-2xl border bg-popover p-2 pl-4 shadow-float animate-fade-up">
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{selected.length} selected</span>
            <button onClick={() => toast.success(`${selected.length} clips saved`)} className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm shadow-soft"><Bookmark className="h-4 w-4" /><span className="hidden sm:inline">Save</span></button>
            <Link to="/editor/$id" params={{ id: `${project.id}~${selected[0]}` }} className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm shadow-soft"><Scissors className="h-4 w-4" /><span className="hidden sm:inline">Edit</span></Link>
            <button onClick={() => setExportOpen(true)} className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-pop"><Download className="h-4 w-4" /> Export</button>
          </div>
        )}
      </section>

      <ExportDialog open={exportOpen} onOpenChange={setExportOpen} count={Math.max(selected.length, 1)} />
    </div>
  );
}

function Message({ m, project, onPick }: { m: ChatMsg; project: { highlights: Highlight[]; thumb: string }; onPick: (id: string) => void }) {
  if (m.role === "user") {
    return <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-foreground px-3.5 py-2 text-sm text-background shadow-pop">{m.text}</div>;
  }
  const clips = (m.clipIds ?? []).map((cid) => project.highlights.find((h) => h.id === cid)).filter(Boolean) as Highlight[];
  return (
    <div className="flex gap-2.5 animate-fade-up">
      <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <div className="min-w-0 flex-1 space-y-2">
        {m.text && <p className="text-sm leading-relaxed">{m.text}</p>}
        {clips.length > 0 && (
          <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
            {clips.map((c) => (
              <button key={c.id} onClick={() => onPick(c.id)} className="w-36 shrink-0 overflow-hidden rounded-xl border bg-card text-left lift">
                <div className="relative aspect-video"><img src={project.thumb} alt="" className="h-full w-full object-cover" /><span className="absolute right-1 top-1 rounded bg-success px-1 text-[10px] font-bold text-background">{c.score}</span><Play className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-background drop-shadow" /></div>
                <p className="line-clamp-1 p-1.5 text-xs font-medium">{c.title}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Timeline({ length, clips, activeId, onPick }: { length: number; clips: Highlight[]; activeId?: string | undefined; onPick: (id: string) => void }) {
  return (
    <div className="p-4">
      <div className="relative h-10 rounded-xl bg-muted">
        <div className="absolute inset-0 flex items-end gap-px overflow-hidden rounded-xl px-1 py-2 opacity-40">
          {Array.from({ length: 90 }).map((_, i) => <span key={i} className="flex-1 rounded-sm bg-muted-foreground" style={{ height: `${20 + Math.abs(Math.sin(i * 1.7)) * 75}%` }} />)}
        </div>
        {clips.map((c) => (
          <button key={c.id} onClick={() => onPick(c.id)} title={c.title} style={{ left: `${(c.start / length) * 100}%`, width: `max(6px, ${(c.duration / length) * 100}%)` }}
            className={cn("absolute inset-y-0 rounded-md transition hover:scale-y-110", activeId === c.id ? "bg-primary shadow-pop" : "bg-primary/45 hover:bg-primary/70")} />
        ))}
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[10px] text-muted-foreground"><span>00:00</span><span>{fmt(length / 2)}</span><span>{fmt(length)}</span></div>
    </div>
  );
}

function HighlightCard({ h, thumb, active, selected, onPick, onSelect }: { h: Highlight; thumb: string; active: boolean; selected: boolean; onPick: () => void; onSelect: () => void }) {
  const scoreColor = h.score >= 90 ? "bg-success" : h.score >= 80 ? "bg-warning" : "bg-muted-foreground";
  return (
    <div onClick={onPick} className={cn("group cursor-pointer overflow-hidden rounded-2xl border bg-card lift", active && "ring-2 ring-primary")}>
      <div className="relative aspect-video overflow-hidden">
        <img src={thumb} alt="" loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
        <button onClick={(e) => { e.stopPropagation(); onSelect(); }} className={cn("absolute left-2 top-2 grid h-6 w-6 place-items-center rounded-md border-2 shadow-pop transition", selected ? "border-primary bg-primary text-primary-foreground" : "border-background/80 bg-foreground/30")} aria-label="Select clip">
          {selected && <Check className="h-3.5 w-3.5" />}
        </button>
        <span className={cn("absolute right-2 top-2 rounded-lg px-1.5 py-0.5 text-xs font-bold text-background shadow-pop", scoreColor)}>{h.score}</span>
        <span className="absolute bottom-2 right-2 rounded-md bg-foreground/80 px-1.5 py-0.5 font-mono text-[11px] text-background">{h.duration}s</span>
      </div>
      <div className="p-3">
        <p className="line-clamp-1 text-sm font-medium">{h.title}</p>
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <span className="rounded-md bg-accent px-1.5 py-0.5 text-accent-foreground">{h.category}</span>
          <span className="font-mono">@ {fmt(h.start)}</span>
        </div>
      </div>
    </div>
  );
}

function ExportDialog({ open, onOpenChange, count }: { open: boolean; onOpenChange: (o: boolean) => void; count: number }) {
  const [fmtSel, setFmt] = useState("TikTok 9:16");
  const [progress, setProgress] = useState<number | null>(null);
  const run = () => {
    setProgress(0);
    const iv = setInterval(() => setProgress((p) => {
      const n = (p ?? 0) + 8;
      if (n >= 100) { clearInterval(iv); setTimeout(() => { setProgress(null); onOpenChange(false); toast.success(`${count} clip${count > 1 ? "s" : ""} exported`); }, 400); return 100; }
      return n;
    }), 120);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl shadow-float sm:max-w-md">
        <DialogHeader><DialogTitle className="font-display">Export {count} clip{count > 1 ? "s" : ""}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-2">
          {["TikTok 9:16", "YouTube Shorts", "IG Reels 4:5", "Landscape 16:9"].map((f) => (
            <button key={f} onClick={() => setFmt(f)} className={cn("rounded-xl border p-3 text-left text-sm transition", fmtSel === f ? "border-primary bg-accent shadow-pop" : "hover:bg-muted")}>{f}</button>
          ))}
        </div>
        {progress !== null && <div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} /></div>}
        <button onClick={run} disabled={progress !== null} className="w-full rounded-xl bg-primary py-2.5 text-sm font-medium text-primary-foreground shadow-pop disabled:opacity-60">
          {progress !== null ? `Rendering… ${progress}%` : "Export"}
        </button>
      </DialogContent>
    </Dialog>
  );
}
