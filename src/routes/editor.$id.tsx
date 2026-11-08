import { useBrand } from "@/lib/brand";
import { VideoPlayer } from "@/components/VideoPlayer";
import { ExportDialog } from "@/components/ExportDialog";
import { defaultEdit, editSchema, type ClipEdit, type TranscriptSegment } from "@/lib/editor";
import { useArtifacts } from "@/lib/store";
import { useMediaUrl } from "@/lib/media";
import { requireAuth } from "@/lib/auth";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowUp,
  Play,
  Pause,
  Scissors,
  Sparkles,
  Download,
  Loader2,
  User,
  Type,
  Crop,
  RectangleVertical,
} from "lucide-react";
import { toast } from "sonner";
import { useStore } from "@/lib/store";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/editor/$id")({
  beforeLoad: requireAuth,
  head: () => ({
    meta: [
      { title: "Clip editor — Clipwave" },
      { name: "description", content: "Trim, caption and reframe clips with AI commands." },
      { property: "og:title", content: "Clip editor — Clipwave" },
      { property: "og:description", content: "Trim, caption and reframe clips with AI commands." },
    ],
  }),
  component: Editor,
});

const ratios = {
  "9:16": "aspect-[9/16] max-h-[60vh]",
  "1:1": "aspect-square max-h-[55vh]",
  "4:5": "aspect-[4/5] max-h-[58vh]",
  "16:9": "aspect-video w-full",
} as const;
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
  const { brand, isPending: brandLoading } = useBrand();
  const [pid, hid] = id.split("~");
  const { projects, clips: savedClips, loading, saveClip } = useStore();
  const artifacts = useArtifacts(pid ?? "");
  const saved = savedClips.find((c) => c.highlight_id === hid);
  const [revision, setRevision] = useState<number | undefined>();
  const loaded = useRef("");
  const [exportOpen, setExportOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState([1]);
  const [cropX, setCropX] = useState([0.5]);
  const [cropY, setCropY] = useState([0.5]);
  const [captionColor, setCaptionColor] = useState("#FFFFFF");
  const [captionFont, setCaptionFont] = useState<ClipEdit["font"]>("Instrument Sans");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const project = projects.find((p) => p.id === pid);
  const clip = project?.highlights.find((h) => h.id === hid);

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
  const [captionText, setCaptionText] = useState("");

  const transcript = (artifacts.data?.transcript ?? []) as unknown as TranscriptSegment[];
  const segment = transcript.find((s) => s.start <= currentTime && s.end > currentTime);
  useEffect(() => {
    if (!clip || loading || brandLoading || loaded.current === clip.id) return;
    const parsed = saved ? editSchema.safeParse(saved.edit) : null;
    const e = parsed?.success ? parsed.data : { ...defaultEdit(clip), ...brand };
    setRatio(e.ratio);
    setTrim([e.start, e.end]);
    setCaptions(e.captions);
    setCapStyle(e.caption_style);
    setCapSize([e.caption_size]);
    setCropX([e.crop_x]);
    setCropY([e.crop_y]);
    setVolume([e.volume]);
    setCaptionColor(e.caption_color);
    setCaptionFont(e.font);
    setOverrides(e.caption_overrides);
    setRevision(saved?.revision);
    setCurrentTime(e.start);
    loaded.current = clip.id;
  }, [clip, loading, saved, brand, brandLoading]);
  useEffect(() => {
    setCaptionText(segment ? (overrides[segment.id] ?? segment.text) : "");
  }, [segment, overrides]);
  // Mount the player only after the real trim/brand settings are initialized.
  // Otherwise a click can race the temporary 0–duration segment and pause the seek.
  if (loading || brandLoading || (clip && loaded.current !== clip.id))
    return <div className="p-10">Loading your clip…</div>;
  if (!project || !clip)
    return (
      <div className="p-10 text-center text-muted-foreground">
        Clip not found.{" "}
        <Link to="/" className="text-primary">
          Go home
        </Link>
      </div>
    );
  const max = project.length;
  const runAi = () =>
    setAiNote(
      "Conversational editing is not enabled yet. Use the controls to save real editing decisions.",
    );
  const edit: ClipEdit = {
    version: 1,
    start: trim[0],
    end: trim[1],
    ratio,
    crop_x: cropX[0] ?? 0.5,
    crop_y: cropY[0] ?? 0.5,
    volume: volume[0] ?? 1,
    captions,
    caption_style: capStyle,
    caption_size: capSize[0] ?? 28,
    caption_color: captionColor,
    font: captionFont,
    caption_overrides: overrides,
  };
  const persist = async () => {
    try {
      await saveClip(clip.id, edit, revision);
      setRevision((r) => (r ?? 0) + 1);
      toast.success("Edit saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  };
  const len = trim[1] - trim[0];

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b px-3 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-2">
          <Link
            to="/project/$id"
            params={{ id: project.id }}
            className="shrink-0 rounded-lg p-2 hover:bg-muted"
            aria-label="Back"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <p className="truncate text-sm font-semibold">{clip.title}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void persist()}
            className="rounded-xl border px-3 py-2 text-sm shadow-soft"
          >
            Save
          </button>
          <button
            onClick={() => setExportOpen(true)}
            className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-pop transition hover:-translate-y-0.5"
          >
            <Download className="h-4 w-4" /> Export
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col lg:flex-row">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="relative flex flex-1 items-center justify-center bg-surface p-4 sm:p-8">
            <div
              className={cn(
                "relative overflow-hidden rounded-2xl bg-foreground shadow-float transition-all duration-500",
                ratios[ratio],
                ratio === "16:9" ? "max-w-3xl" : "",
              )}
            >
              <VideoPlayer
                path={project.video?.playback_path ?? project.video?.source_path}
                poster={project.thumb}
                seekTo={trim[0]}
                onTime={setCurrentTime}
                segmentEnd={trim[1]}
                cropX={cropX[0] ?? 0.5}
                cropY={cropY[0] ?? 0.5}
                volume={volume[0] ?? 1}
              />
              {captions && segment && (
                <p
                  style={{ fontSize: (capSize[0] ?? 28) * (ratio === "16:9" ? 0.8 : 0.6) }}
                  className={cn(
                    "absolute inset-x-4 bottom-[18%] text-center font-display font-bold uppercase leading-tight drop-shadow-lg",
                    capStyle === "Bold pop" &&
                      "text-background [-webkit-text-stroke:1px_var(--foreground)]",
                    capStyle === "Karaoke" && "text-warning",
                    capStyle === "Minimal" && "font-sans font-medium normal-case text-background",
                    capStyle === "Neon" && "text-glow-2",
                  )}
                >
                  {overrides[segment.id] ?? segment.text}
                </p>
              )}
            </div>

            <div className="absolute inset-x-3 bottom-3 mx-auto max-w-xl sm:bottom-5">
              {aiNote && (
                <div className="mb-2 flex items-start gap-2 rounded-xl border bg-popover px-3 py-2 text-sm shadow-pop animate-fade-up">
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> {aiNote}
                </div>
              )}
              <div className="glow-ring flex items-center gap-2 rounded-2xl bg-card p-1.5 pl-3 shadow-float">
                {thinking ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                ) : (
                  <Sparkles className="h-4 w-4 shrink-0 text-primary" />
                )}
                <input
                  value={cmd}
                  onChange={(e) => setCmd(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && runAi()}
                  disabled
                  placeholder="Edit using the controls below"
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none"
                />
                <button
                  disabled
                  onClick={() => runAi()}
                  className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-foreground text-background shadow-pop"
                  aria-label="Run"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              </div>
              <div className="no-scrollbar mt-2 flex gap-1.5 overflow-x-auto">
                {[
                  "Make this clip 45 seconds",
                  "Add animated subtitles",
                  "Focus the crop on the gameplay",
                  "Create a TikTok version",
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => runAi()}
                    disabled
                    className="shrink-0 rounded-full border bg-card/90 px-2.5 py-1 text-xs shadow-soft backdrop-blur hover:shadow-pop"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-3 border-t bg-card p-3 sm:p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span className="font-mono">
                Length {len}s · {trim[0]}s → {trim[1]}s
              </span>
              <button
                disabled
                title="Split editing is not enabled in the single-clip workflow"
                className="flex items-center gap-1 rounded-lg border px-2 py-1 text-foreground shadow-soft hover:shadow-pop"
              >
                <Scissors className="h-3.5 w-3.5" /> Split
              </button>
            </div>
            <div className="relative">
              <div className="flex h-12 gap-0.5 overflow-hidden rounded-xl">
                {((artifacts.data?.frame_paths ?? []) as { time: number; path: string }[]).map(
                  (f) => (
                    <TimelineFrame key={f.path} path={f.path} />
                  ),
                )}
              </div>
              {splits.map((s, i) => (
                <span
                  key={i}
                  className="absolute inset-y-0 w-0.5 bg-warning shadow-pop"
                  style={{ left: `${(s / max) * 100}%` }}
                />
              ))}
            </div>
            <div className="flex h-8 items-center gap-px rounded-lg bg-muted px-1">
              {((artifacts.data?.waveform ?? []) as number[]).map((n, i) => (
                <span
                  key={i}
                  className="flex-1 rounded-full bg-primary/60"
                  style={{ height: `${Math.round(n * 100)}%` }}
                />
              ))}
            </div>
            <Slider
              value={trim}
              min={0}
              max={max}
              step={0.1}
              onValueChange={(v) => {
                const a = v[0] ?? 0,
                  b = v[1] ?? max;
                if (b > a && b - a <= 60) setTrim([a, b]);
              }}
              aria-label="Trim"
            />
          </div>
        </div>

        <aside className="w-full shrink-0 border-t bg-sidebar lg:w-80 lg:border-l lg:border-t-0">
          <div className="flex gap-1 border-b p-2">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1.5 rounded-xl py-2 text-sm",
                  tab === t.id
                    ? "bg-card font-medium shadow-pop ring-1 ring-border"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <t.icon className="h-4 w-4" /> {t.label}
              </button>
            ))}
          </div>
          <div className="space-y-5 p-4">
            {tab === "captions" && (
              <>
                <label className="flex items-center justify-between text-sm">
                  Show captions <Switch checked={captions} onCheckedChange={setCaptions} />
                </label>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    Caption text at playhead
                  </p>
                  <input
                    value={captionText}
                    disabled={!segment}
                    onChange={(e) => {
                      setCaptionText(e.target.value);
                      if (segment) setOverrides((o) => ({ ...o, [segment.id]: e.target.value }));
                    }}
                    className="w-full rounded-xl border bg-card px-3 py-2 text-sm shadow-soft outline-none focus:ring-2 focus:ring-ring/40"
                  />
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Template</p>
                  <div className="grid grid-cols-2 gap-2">
                    {captionStyles.map((s) => (
                      <button
                        key={s}
                        onClick={() => setCapStyle(s)}
                        className={cn(
                          "rounded-xl border px-3 py-2 text-sm transition",
                          capStyle === s
                            ? "border-primary bg-accent shadow-pop"
                            : "bg-card hover:shadow-soft",
                        )}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    Size · {capSize[0]}px
                  </p>
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
                      <button
                        key={r}
                        onClick={() => setRatio(r)}
                        className={cn(
                          "flex flex-col items-center gap-1 rounded-xl border py-2 text-xs transition",
                          ratio === r
                            ? "border-primary bg-accent shadow-pop"
                            : "bg-card hover:shadow-soft",
                        )}
                      >
                        <RectangleVertical className="h-4 w-4" />
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Crop focus</p>
                  <div className="grid grid-cols-3 gap-2">
                    {(["Auto", "Face", "Gameplay"] as const).map((f) => (
                      <button
                        key={f}
                        disabled={f !== "Auto"}
                        title={
                          f === "Auto" ? "Center crop" : "Automatic detection is not available"
                        }
                        onClick={() => {
                          setFocus(f);
                          setCropX([0.5]);
                          setCropY([0.5]);
                        }}
                        className={cn(
                          "rounded-xl border py-2 text-sm transition",
                          focus === f
                            ? "border-primary bg-accent shadow-pop"
                            : "bg-card hover:shadow-soft",
                        )}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    Manual crop position; subject tracking is not enabled.
                  </p>
                  <label className="block text-sm">
                    Horizontal
                    <Slider
                      aria-label="Horizontal crop"
                      value={cropX}
                      min={0}
                      max={1}
                      step={0.01}
                      onValueChange={setCropX}
                    />
                  </label>
                  <label className="block text-sm">
                    Vertical
                    <Slider
                      aria-label="Vertical crop"
                      value={cropY}
                      min={0}
                      max={1}
                      step={0.01}
                      onValueChange={setCropY}
                    />
                  </label>
                  <label className="block text-sm">
                    Volume
                    <Slider
                      aria-label="Volume"
                      value={volume}
                      min={0}
                      max={2}
                      step={0.05}
                      onValueChange={setVolume}
                    />
                  </label>
                </div>
              </>
            )}
            {tab === "facecam" && (
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">Facecam position</p>
                <div className="grid grid-cols-2 gap-2">
                  {facecams.map((f) => (
                    <button
                      key={f}
                      disabled
                      title="Facecam region detection is not enabled yet"
                      onClick={() => setFacecam(f)}
                      className={cn(
                        "rounded-xl border py-2 text-sm transition",
                        facecam === f
                          ? "border-primary bg-accent shadow-pop"
                          : "bg-card hover:shadow-soft",
                      )}
                    >
                      {f}
                    </button>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  Facecam extraction is not enabled yet. Manual crop controls apply to the source
                  footage.
                </p>
              </div>
            )}
          </div>
        </aside>
      </div>
      <ExportDialog
        open={exportOpen}
        onOpenChange={setExportOpen}
        projectId={project.id}
        highlightIds={[clip.id]}
        edit={edit}
        onSaved={() => {
          loaded.current = "";
        }}
      />
    </div>
  );
}

function TimelineFrame({ path }: { path: string }) {
  const { data } = useMediaUrl("thumbnails", path);
  return <img src={data} alt="" className="h-full min-w-0 flex-1 object-cover opacity-80" />;
}
