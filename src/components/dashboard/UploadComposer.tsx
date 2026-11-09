import { useServerFn } from "@tanstack/react-start";
import { ArrowUpRight, Clapperboard, FileVideo2, Link2, Loader2, Plus, Sparkles, UploadCloud, X } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";
import { finalizeVideo, prepareVideo } from "@/lib/creator.functions";
import { supabase } from "@/integrations/supabase/client";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE = 45_000_000;
const ACCEPTED_TYPES = ["video/mp4", "video/quicktime", "video/webm"] as const;
const prompts = [
  { label: "Funny moments", value: "Find the funniest moments and turn them into short, punchy clips." },
  { label: "Hype & clutch", value: "Find the most hype and clutch moments, keeping the buildup and payoff." },
  { label: "Under 30 seconds", value: "Create engaging vertical clips under 30 seconds with animated captions." },
];

type UploadStage = "idle" | "preparing" | "uploading" | "finalizing";

type UploadComposerProps = {
  onUploaded: () => Promise<void>;
};

export function UploadComposer({ onUploaded }: UploadComposerProps) {
  const [file, setFile] = useState<File | null>(null);
  const [instructions, setInstructions] = useState("");
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>("idle");
  const inputRef = useRef<HTMLInputElement>(null);
  const requestIdRef = useRef<string | null>(null);
  const prepare = useServerFn(prepareVideo);
  const finalize = useServerFn(finalizeVideo);
  const busy = stage !== "idle";

  const chooseFile = (nextFile: File | undefined) => {
    if (!nextFile || busy) return;
    if (!ACCEPTED_TYPES.includes(nextFile.type as (typeof ACCEPTED_TYPES)[number])) {
      toast.error("Choose an MP4, MOV or WebM video.");
      return;
    }
    if (nextFile.size > MAX_FILE_SIZE) {
      toast.error("This video is over 45 MB. Choose a smaller file to upload it here.");
      return;
    }
    if (!file || file.name !== nextFile.name || file.size !== nextFile.size || file.lastModified !== nextFile.lastModified) {
      requestIdRef.current = null;
    }
    setFile(nextFile);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  };

  const startUpload = async () => {
    if (busy) return;
    if (!file) {
      inputRef.current?.click();
      return;
    }

    try {
      setStage("preparing");
      const requestId = requestIdRef.current ?? crypto.randomUUID();
      requestIdRef.current = requestId;
      const result = await prepare({
        data: {
          requestId,
          filename: file.name,
          mime: file.type,
          bytes: file.size,
          instructions: instructions.trim() || "Find the most engaging moments and create vertical clips with captions.",
        },
      });
      const prepared = result as { project_id?: string; path?: string };
      if (!prepared.project_id || !prepared.path) throw new Error("The upload could not be prepared. Please try again.");

      setStage("uploading");
      const upload = await supabase.storage.from("source-videos").upload(prepared.path, file, {
        contentType: file.type,
        upsert: true,
      });
      if (upload.error) throw new Error(upload.error.message);

      setStage("finalizing");
      await finalize({ data: { projectId: prepared.project_id } });
      toast.success("Upload complete. AI analysis is now queued.");
      setFile(null);
      setInstructions("");
      requestIdRef.current = null;
      if (inputRef.current) inputRef.current.value = "";
      await onUploaded();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "The upload didn't finish. Please try again.");
    } finally {
      setStage("idle");
    }
  };

  const stageLabel = stage === "preparing"
    ? "Preparing your project…"
    : stage === "uploading"
      ? "Uploading your video…"
      : stage === "finalizing"
        ? "Queueing AI analysis…"
        : "";

  return (
    <section id="new-project" className="glow-border glow-border-soft scroll-mt-28 rounded-[24px] bg-card shadow-float">
      <div className="p-4 sm:p-6 lg:p-7">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-ember/20 bg-ember/10 text-ember shadow-soft">
              <Sparkles className="h-[18px] w-[18px]" />
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-base font-medium tracking-tight sm:text-lg">Create something worth watching</h2>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">Upload a recording. Describe the moments you want.</p>
            </div>
          </div>
          <span className="hidden rounded-full border border-border bg-surface px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-muted-foreground sm:block">AI clipping</span>
        </div>

        <div className="mt-6 flex items-center gap-5 border-b border-border text-sm">
          <span className="flex items-center gap-2 border-b border-ember pb-3 font-medium text-foreground"><UploadCloud className="h-4 w-4 text-ember" /> Upload video</span>
          <span className="flex items-center gap-2 pb-3 text-muted-foreground/60" title="Link imports are coming soon"><Link2 className="h-4 w-4" /> Paste link <span className="rounded-full bg-muted px-1.5 py-0.5 text-[9px]">SOON</span></span>
        </div>

        <div
          onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={cn(
            "mt-5 rounded-2xl border border-dashed transition-all duration-300",
            dragging ? "border-ember bg-ember/10 shadow-pop" : "border-border bg-surface/60",
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
            className="sr-only"
            aria-label="Choose a video file"
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
          {file ? (
            <div className="flex items-center gap-3 p-3 sm:p-4">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-ember/20 bg-ember/10 text-ember"><FileVideo2 className="h-5 w-5" /></span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{file.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{(file.size / 1_000_000).toFixed(1)} MB · Ready to upload</p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => { setFile(null); requestIdRef.current = null; if (inputRef.current) inputRef.current.value = ""; }}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-muted-foreground transition hover:bg-accent hover:text-foreground disabled:opacity-40"
                aria-label="Remove selected video"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => inputRef.current?.click()} disabled={busy} className="flex w-full flex-col items-center px-4 py-7 text-center sm:py-8">
              <span className="grid h-11 w-11 place-items-center rounded-full border border-border bg-card text-muted-foreground shadow-soft transition group-hover:text-ember"><Plus className="h-5 w-5" /></span>
              <span className="mt-3 text-sm font-medium">Drop your recording here, or <span className="text-ember">browse</span></span>
              <span className="mt-1.5 text-xs text-muted-foreground">MP4, MOV or WebM · up to 45 MB</span>
            </button>
          )}
        </div>

        <div className="relative mt-3 rounded-2xl border border-border bg-surface/80 p-4 shadow-soft transition focus-within:border-ember/40 focus-within:shadow-pop">
          <textarea
            id="clip-instructions"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            maxLength={2000}
            rows={3}
            disabled={busy}
            placeholder="Tell AI what to look for… e.g. Find my funniest reactions and keep each clip under 30 seconds."
            className="min-h-[76px] w-full resize-none bg-transparent text-sm leading-relaxed outline-none placeholder:text-muted-foreground/70"
          />
          <div className="flex items-end justify-between gap-3">
            <span className="hidden items-center gap-1.5 text-[11px] text-muted-foreground sm:flex"><Clapperboard className="h-3.5 w-3.5" /> Vertical clips with captions</span>
            <span className="ml-auto text-[10px] text-muted-foreground/70">{instructions.length}/2000</span>
          </div>
        </div>

        <div className="no-scrollbar mt-3 flex gap-2 overflow-x-auto pb-1">
          {prompts.map((prompt) => (
            <button
              type="button"
              key={prompt.label}
              disabled={busy}
              onClick={() => setInstructions(prompt.value)}
              className="shrink-0 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-soft transition hover:-translate-y-0.5 hover:border-ember/30 hover:text-foreground"
            >
              {prompt.label}
            </button>
          ))}
        </div>

        {busy && (
          <div className="mt-4" aria-live="polite">
            <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin text-ember" /> {stageLabel}</div>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted"><div className="upload-progress h-full w-1/3 rounded-full bg-ember" /></div>
          </div>
        )}

        <div className="mt-5 flex items-center justify-between gap-4">
          <p className="hidden text-xs text-muted-foreground md:block">Your video stays private to your workspace.</p>
          <button
            type="button"
            onClick={() => void startUpload()}
            disabled={busy}
            className="glow-border inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground shadow-pop transition hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-60 sm:w-auto md:ml-auto"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : file ? <Sparkles className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {busy ? "Creating project…" : file ? "Start clipping" : "Choose a video"}
            {!busy && <ArrowUpRight className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </section>
  );
}
