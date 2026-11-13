import { VideoPlayer } from "@/components/VideoPlayer";
import { ExportDialog } from "@/components/ExportDialog";
import { activeJob, defaultEdit } from "@/lib/editor";
import { requireAuth } from "@/lib/auth";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp,
  Play,
  Pause,
  Paperclip,
  PanelLeftClose,
  PanelLeft,
  Sparkles,
  Check,
  Scissors,
  Download,
  Trash2,
  Loader2,
  MessageSquare,
  Clapperboard,
  Bookmark,
} from "lucide-react";
import { toast } from "sonner";
import { useStore, useArtifacts, type ChatMsg } from "@/lib/store";
import { fmt, type Category, type Highlight } from "@/lib/domain";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/project/$id")({
  beforeLoad: requireAuth,
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Project workspace — Noethara Clipz" },
      { name: "description", content: "Chat with the AI and review detected highlights." },
      { property: "og:title", content: "Project workspace — Noethara Clipz" },
      { property: "og:description", content: "Chat with the AI and review detected highlights." },
    ],
  }),
  component: Workspace,
});

const cats: ("All" | Category)[] = ["All", "Clutch", "Hype", "Funny", "Reaction", "Tutorial"];
const commands = [
  "Make them shorter",
  "Find more funny moments",
  "Add captions to all",
  "Export for TikTok",
];

function Workspace() {
  const { id } = Route.useParams();
  const {
    projects,
    chats,
    jobs,
    loading,
    error,
    setDeleted,
    retryJob,
    cancelJob,
    saveClip,
    clips: savedClips,
  } = useStore();
  const artifacts = useArtifacts(id);
  const job = jobs.find((j) => j.project_id === id && j.kind === "analysis");
  const [playhead, setPlayhead] = useState(0);
  const [seek, setSeek] = useState<number | undefined>();
  const nav = useNavigate();
  const project = projects.find((p) => p.id === id);
  const msgs = useMemo(() => chats[id] ?? [], [chats, id]);
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

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const clips = useMemo(
    () => (project?.highlights ?? []).filter((h) => cat === "All" || h.category === cat),
    [project, cat],
  );
  const active = project?.highlights.find((h) => h.id === activeId) ?? project?.highlights[0];

  if (loading) return <div className="p-10">Loading your project…</div>;
  if (error)
    return (
      <div role="alert" className="p-10">
        {error.message}
      </div>
    );
  if (!project) {
    return (
      <div className="p-10 text-center text-muted-foreground">
        Project not found.{" "}
        <Link to="/" className="text-primary">
          Go home
        </Link>
      </div>
    );
  }

  const send = () =>
    toast(
      "Conversational editing is not enabled yet. Your analysis instructions and results are saved; use the clip editor for changes.",
    );
  const pick = (hid: string) => {
    setActiveId(hid);
    const h = project.highlights.find((h) => h.id === hid);
    if (h) setSeek(h.start);
  };
  const saveSelected = async () => {
    try {
      for (const hid of selected) {
        const h = project.highlights.find((h) => h.id === hid);
        if (h && !savedClips.some((c) => c.highlight_id === hid))
          await saveClip(hid, defaultEdit(h));
      }
      toast.success("Clip drafts saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  };
  const toggleSel = (hid: string) =>
    setSelected((s) => (s.includes(hid) ? s.filter((x) => x !== hid) : [...s, hid]));

  const chatPanel = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-primary-foreground shadow-pop">
          <Scissors className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Noethara Clipz AI</p>
          <p className="truncate text-xs text-muted-foreground">{project.title}</p>
        </div>
        <button
          onClick={() => setChatOpen(false)}
          className="hidden rounded-lg p-1.5 text-muted-foreground hover:bg-muted lg:block"
          aria-label="Collapse chat"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        {msgs.map((m) => (
          <Message
            key={m.id}
            m={m}
            project={project}
            onPick={(cid) => {
              pick(cid);
              setMobileTab("clips");
            }}
          />
        ))}
        {busy && msgs.at(-1)?.text === "" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-primary" /> Analyzing video…
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="border-t p-3">
        <div className="no-scrollbar mb-2 flex gap-1.5 overflow-x-auto">
          {commands.map((c) => (
            <button
              key={c}
              onClick={() => send()}
              disabled
              title="Available after the core video workflow"
              className="shrink-0 rounded-full border bg-card px-2.5 py-1 text-xs text-muted-foreground shadow-soft hover:text-foreground hover:shadow-pop"
            >
              {c}
            </button>
          ))}
        </div>
        <div className="glow-ring flex items-end gap-2 rounded-2xl bg-card p-2 shadow-pop">
          <button
            onClick={() => toast("Attach a video to add it to this project")}
            className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
            aria-label="Attach"
          >
            <Paperclip className="h-4 w-4" />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            disabled
            placeholder="Use the editor to adjust your clips"
            className="min-h-9 flex-1 resize-none bg-transparent py-2 text-sm outline-none"
          />
          <button
            onClick={() => send()}
            disabled
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-foreground text-background shadow-pop transition hover:scale-105 disabled:opacity-40"
            aria-label="Send"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col lg:flex-row">
      <div className="flex border-b p-2 lg:hidden">
        {(["chat", "clips"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setMobileTab(t)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-xl py-2 text-sm",
              mobileTab === t
                ? "bg-card font-medium shadow-pop ring-1 ring-border"
                : "text-muted-foreground",
            )}
          >
            {t === "chat" ? (
              <MessageSquare className="h-4 w-4" />
            ) : (
              <Clapperboard className="h-4 w-4" />
            )}{" "}
            {t === "chat" ? "AI chat" : `Clips (${project.highlights.length})`}
          </button>
        ))}
      </div>

      <aside
        className={cn(
          "min-h-0 border-r bg-sidebar transition-all duration-300 lg:block lg:h-full",
          chatOpen ? "lg:w-96" : "lg:w-0 lg:overflow-hidden lg:border-0",
          mobileTab === "chat" ? "flex-1" : "hidden",
        )}
      >
        {chatPanel}
      </aside>

      <section
        className={cn(
          "min-h-0 flex-1 overflow-y-auto",
          mobileTab === "clips" ? "block" : "hidden lg:block",
        )}
      >
        <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
          <div className="flex items-center gap-2">
            {!chatOpen && (
              <button
                onClick={() => setChatOpen(true)}
                className="hidden items-center gap-1.5 rounded-xl border bg-card px-3 py-1.5 text-sm shadow-soft hover:shadow-pop lg:flex"
              >
                <PanelLeft className="h-4 w-4" /> AI chat
              </button>
            )}
            <h1 className="min-w-0 flex-1 truncate text-lg font-semibold sm:text-xl">
              {project.title}
            </h1>
            <button
              onClick={() =>
                void setDeleted(project.id, true)
                  .then(() => nav({ to: "/library" }))
                  .catch((e) => toast.error(e.message))
              }
              className="rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-destructive"
              aria-label="Delete project"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>

          <div className="overflow-hidden rounded-3xl border bg-card shadow-float">
            <div className="relative aspect-video bg-foreground">
              <VideoPlayer
                path={project.video?.playback_path ?? project.video?.source_path}
                poster={project.thumb}
                seekTo={seek}
                onTime={setPlayhead}
              />
              {active && (
                <div className="pointer-events-none absolute bottom-12 left-3 right-3 flex flex-wrap items-center gap-2 text-background">
                  <span className="rounded-lg bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground shadow-pop">
                    {active.category}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">
                    {active.title}
                  </span>
                  <span className="font-mono text-xs">
                    {fmt(active.start)} · {active.duration}s
                  </span>
                </div>
              )}
            </div>
            <Timeline
              length={project.length}
              clips={project.highlights}
              activeId={active?.id}
              onPick={pick}
              waveform={artifacts.data?.waveform as number[] | undefined}
              playhead={playhead}
              onSeek={setSeek}
            />
          </div>

          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
            <div className="no-scrollbar flex gap-1.5 overflow-x-auto">
              {cats.map((c) => (
                <button
                  key={c}
                  onClick={() => setCat(c)}
                  className={cn(
                    "shrink-0 rounded-full border px-3 py-1 text-sm transition",
                    cat === c
                      ? "bg-foreground text-background shadow-pop"
                      : "bg-card shadow-soft hover:shadow-pop",
                  )}
                >
                  {c}
                </button>
              ))}
            </div>
            <button
              onClick={() => setSelected(selected.length ? [] : clips.map((c) => c.id))}
              className="text-sm text-primary"
            >
              {selected.length ? "Clear" : "Select all"}
            </button>
          </div>

          {job && (
            <div className="space-y-2 rounded-2xl border bg-card p-4 shadow-soft">
              <p role="status" className="text-sm">
                {job.stage} · {job.progress}%
              </p>
              <progress max={100} value={job.progress} className="w-full" />
              {job.error && (
                <p role="alert" className="break-words text-sm text-destructive">
                  {job.error}
                </p>
              )}
              {activeJob(job.status) ? (
                <button
                  onClick={() => void cancelJob(job.id).catch((e) => toast.error(e.message))}
                  className="text-sm text-muted-foreground"
                >
                  Cancel processing
                </button>
              ) : (
                job.status !== "completed" && (
                  <button
                    onClick={() => void retryJob(job.id).catch((e) => toast.error(e.message))}
                    className="text-sm text-primary"
                  >
                    Retry processing
                  </button>
                )
              )}
              {job.status === "queued" && (
                <p className="text-xs text-muted-foreground">
                  Waiting for the video worker. You can return later.
                </p>
              )}
            </div>
          )}
          {project.highlights.length === 0 && !["queued", "processing"].includes(project.status) ? (
            <p className="rounded-2xl border p-6 text-sm text-muted-foreground">
              {project.status === "ready"
                ? "Analysis completed without suitable highlights. No moments were fabricated."
                : "Highlights will appear after real analysis completes."}
            </p>
          ) : project.highlights.length === 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="rounded-2xl border bg-card p-3 shadow-soft">
                  <Skeleton className="aspect-video w-full rounded-xl" />
                  <Skeleton className="mt-3 h-4 w-3/4" />
                  <Skeleton className="mt-2 h-3 w-1/2" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid gap-4 pb-24 sm:grid-cols-2 xl:grid-cols-3">
              {clips.map((h) => (
                <HighlightCard
                  key={h.id}
                  h={h}
                  thumb={project.thumb}
                  active={active?.id === h.id}
                  selected={selected.includes(h.id)}
                  onPick={() => pick(h.id)}
                  onSelect={() => toggleSel(h.id)}
                />
              ))}
            </div>
          )}
        </div>

        {selected.length > 0 && (
          <div className="fixed inset-x-3 bottom-4 z-40 mx-auto flex max-w-lg items-center gap-2 rounded-2xl border bg-popover p-2 pl-4 shadow-float animate-fade-up">
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {selected.length} selected
            </span>
            <button
              onClick={() => void saveSelected()}
              className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm shadow-soft"
            >
              <Bookmark className="h-4 w-4" />
              <span className="hidden sm:inline">Save</span>
            </button>
            <Link
              to="/editor/$id"
              params={{ id: `${project.id}~${selected[0]}` }}
              className="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm shadow-soft"
            >
              <Scissors className="h-4 w-4" />
              <span className="hidden sm:inline">Edit</span>
            </Link>
            <button
              onClick={() => setExportOpen(true)}
              className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-pop"
            >
              <Download className="h-4 w-4" /> Export
            </button>
          </div>
        )}
      </section>

      <ExportDialog
        open={exportOpen}
        onOpenChange={setExportOpen}
        projectId={id}
        highlightIds={selected.length ? selected : active ? [active.id] : []}
      />
    </div>
  );
}

function Message({
  m,
  project,
  onPick,
}: {
  m: ChatMsg;
  project: { highlights: Highlight[]; thumb: string };
  onPick: (id: string) => void;
}) {
  if (m.role === "user") {
    return (
      <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-foreground px-3.5 py-2 text-sm text-background shadow-pop">
        {m.text}
      </div>
    );
  }
  const clips = (m.clipIds ?? [])
    .map((cid) => project.highlights.find((h) => h.id === cid))
    .filter(Boolean) as Highlight[];
  return (
    <div className="flex gap-2.5 animate-fade-up">
      <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <div className="min-w-0 flex-1 space-y-2">
        {m.text && <p className="text-sm leading-relaxed">{m.text}</p>}
        {clips.length > 0 && (
          <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
            {clips.map((c) => (
              <button
                key={c.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onPick(c.id);
                }}
                className="w-36 shrink-0 overflow-hidden rounded-xl border bg-card text-left lift"
              >
                <div className="relative aspect-video">
                  <img src={project.thumb} alt="" className="h-full w-full object-cover" />
                  <span className="absolute right-1 top-1 rounded bg-success px-1 text-[10px] font-bold text-background">
                    {c.score}
                  </span>
                  <Play className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-background drop-shadow" />
                </div>
                <p className="line-clamp-1 p-1.5 text-xs font-medium">{c.title}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Timeline({
  length,
  clips,
  activeId,
  onPick,
  waveform,
  playhead,
  onSeek,
}: {
  length: number;
  clips: Highlight[];
  activeId?: string | undefined;
  onPick: (id: string) => void;
  waveform: number[] | undefined;
  playhead: number;
  onSeek: (t: number) => void;
}) {
  return (
    <div className="p-4">
      <div
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          onSeek(Math.max(0, Math.min(length, ((e.clientX - r.left) / r.width) * length)));
        }}
        className="relative h-10 cursor-pointer rounded-xl bg-muted"
      >
        <div className="absolute inset-0 flex items-end gap-px overflow-hidden rounded-xl px-1 py-2 opacity-40">
          {(waveform ?? []).map((n, i) => (
            <span
              key={i}
              className="flex-1 rounded-sm bg-muted-foreground"
              style={{ height: `${Math.round(n * 100)}%` }}
            />
          ))}
        </div>
        <span
          className="pointer-events-none absolute inset-y-0 w-0.5 bg-foreground"
          style={{ left: `${(playhead / (length || 1)) * 100}%` }}
        />
        {clips.map((c) => (
          <button
            key={c.id}
            onClick={(e) => {
              e.stopPropagation();
              onPick(c.id);
            }}
            title={c.title}
            style={{
              left: `${(c.start / (length || 1)) * 100}%`,
              width: `max(6px, ${(c.duration / (length || 1)) * 100}%)`,
            }}
            className={cn(
              "absolute inset-y-0 rounded-md transition hover:scale-y-110",
              activeId === c.id ? "bg-primary shadow-pop" : "bg-primary/45 hover:bg-primary/70",
            )}
          />
        ))}
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[10px] text-muted-foreground">
        <span>00:00</span>
        <span>{fmt(length / 2)}</span>
        <span>{fmt(length)}</span>
      </div>
    </div>
  );
}

function HighlightCard({
  h,
  thumb,
  active,
  selected,
  onPick,
  onSelect,
}: {
  h: Highlight;
  thumb: string;
  active: boolean;
  selected: boolean;
  onPick: () => void;
  onSelect: () => void;
}) {
  const scoreColor =
    h.score >= 90 ? "bg-success" : h.score >= 80 ? "bg-warning" : "bg-muted-foreground";
  return (
    <div
      onClick={onPick}
      className={cn(
        "group cursor-pointer overflow-hidden rounded-2xl border bg-card lift",
        active && "ring-2 ring-primary",
      )}
    >
      <div className="relative aspect-video overflow-hidden">
        <img
          src={thumb}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
        />
        <button
          onClick={(e) => {
            e.stopPropagation();
            onSelect();
          }}
          className={cn(
            "absolute left-2 top-2 grid h-6 w-6 place-items-center rounded-md border-2 shadow-pop transition",
            selected
              ? "border-primary bg-primary text-primary-foreground"
              : "border-background/80 bg-foreground/30",
          )}
          aria-label="Select clip"
        >
          {selected && <Check className="h-3.5 w-3.5" />}
        </button>
        <span
          className={cn(
            "absolute right-2 top-2 rounded-lg px-1.5 py-0.5 text-xs font-bold text-background shadow-pop",
            scoreColor,
          )}
        >
          {h.score}
        </span>
        <span className="absolute bottom-2 right-2 rounded-md bg-foreground/80 px-1.5 py-0.5 font-mono text-[11px] text-background">
          {h.duration}s
        </span>
      </div>
      <div className="p-3">
        <p className="line-clamp-1 text-sm font-medium">{h.title}</p>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{h.explanation}</p>
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <span className="rounded-md bg-accent px-1.5 py-0.5 text-accent-foreground">
            {h.category}
          </span>
          <span className="font-mono">@ {fmt(h.start)}</span>
        </div>
      </div>
    </div>
  );
}
