import { useServerFn } from "@tanstack/react-start";
import { useNavigate } from "@tanstack/react-router";
import {
  ArrowUp,
  Flame,
  Laugh,
  Timer,
  Clapperboard,
  FileVideo2,
  Link2,
  Loader2,
  Plus,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";
import { finalizeVideo, prepareVideo } from "@/lib/creator.functions";
import { uploadVideo } from "@/lib/upload";
import { cn } from "@/lib/utils";

const MAX_FILE_SIZE = 45_000_000;
const ACCEPTED_TYPES = ["video/mp4", "video/quicktime", "video/webm"] as const;
const prompts = [
  {
    label: "Funny moments",
    value: "Find the funniest moments and turn them into short, punchy clips.",
  },
  {
    label: "Hype & clutch",
    value: "Find the most hype and clutch moments, keeping the buildup and payoff.",
  },
  {
    label: "Under 30 seconds",
    value: "Create engaging vertical clips under 30 seconds with animated captions.",
  },
];

type UploadStage = "idle" | "preparing" | "uploading" | "finalizing";

type UploadComposerProps = {
  onUploaded: () => Promise<void>;
};

export function UploadComposer({ onUploaded }: UploadComposerProps) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [instructions, setInstructions] = useState("");
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>("idle");
  const [progress, setProgress] = useState(0);
  const uploadRef = useRef<AbortController | null>(null);
  useEffect(() => () => uploadRef.current?.abort(), []);
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
    if (!nextFile.size || nextFile.size > MAX_FILE_SIZE) {
      toast.error("This video is over 45 MB. Choose a smaller file to upload it here.");
      return;
    }
    if (
      !file ||
      file.name !== nextFile.name ||
      file.size !== nextFile.size ||
      file.lastModified !== nextFile.lastModified
    ) {
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
      const controller = new AbortController();
      uploadRef.current = controller;
      setProgress(0);
      const projectId = await uploadVideo(
        file,
        instructions.trim() ||
          "Find the most engaging moments and create vertical clips with captions.",
        requestId,
        setProgress,
        controller.signal,
        {
          prepare: async (data) => {
            const result = await prepare({ data });
            setStage("uploading");
            return result;
          },
          finalize: async (projectId) => {
            setStage("finalizing");
            return finalize({ data: { projectId } });
          },
        },
      );
      toast.success("Upload complete. AI analysis is now queued.");
      setFile(null);
      setInstructions("");
      requestIdRef.current = null;
      if (inputRef.current) inputRef.current.value = "";
      await onUploaded();
      await navigate({ to: "/project/$id", params: { id: projectId } });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "The upload didn't finish. Please try again.",
      );
    } finally {
      uploadRef.current = null;
      setStage("idle");
    }
  };

  const stageLabel =
    stage === "preparing"
      ? "Preparing your project…"
      : stage === "uploading"
        ? `Uploading your video… ${progress}%`
        : stage === "finalizing"
          ? "Queueing AI analysis…"
          : "";

  return (
    <section id="new-project" className="scroll-mt-28">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "prompt-shell rounded-[18px] p-1.5 transition-all duration-300",
          dragging && "prompt-shell-active",
        )}
      >
        <div className="rounded-[14px] border border-border bg-card shadow-float transition focus-within:border-ember/40">
          <input
            ref={inputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
            className="sr-only"
            aria-label="Choose a video file"
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
          <div className="px-4 pt-4 sm:px-5">
            {file && (
              <div className="mb-3 inline-flex max-w-full items-center gap-2 rounded-lg border border-border bg-surface py-1.5 pl-2 pr-1 text-xs shadow-soft">
                <FileVideo2 className="h-4 w-4 shrink-0 text-ember" />
                <span className="truncate font-medium">{file.name}</span>
                <span className="shrink-0 text-muted-foreground">
                  {(file.size / 1_000_000).toFixed(1)} MB
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setFile(null);
                    requestIdRef.current = null;
                    if (inputRef.current) inputRef.current.value = "";
                  }}
                  className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-foreground disabled:opacity-40"
                  aria-label="Remove selected video"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            {busy ? (
              <p className="shimmer-text min-h-[96px] text-sm sm:text-base" aria-live="polite">
                {stageLabel}
              </p>
            ) : (
              <textarea
                id="clip-instructions"
                value={instructions}
                onChange={(event) => setInstructions(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) void startUpload();
                }}
                maxLength={2000}
                rows={3}
                placeholder={
                  dragging
                    ? "Drop your recording to attach it…"
                    : "Describe the clips you want… e.g. find my funniest reactions, under 30 seconds"
                }
                className="min-h-[96px] w-full resize-none bg-transparent text-sm leading-relaxed outline-none placeholder:text-muted-foreground/70 sm:text-base"
              />
            )}
          </div>
          <div className="flex items-center gap-1 px-2.5 pb-2.5 pt-1 sm:px-3">
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              className="grid h-9 w-9 place-items-center rounded-lg text-muted-foreground transition hover:bg-accent hover:text-foreground disabled:opacity-40"
              aria-label="Attach a video"
              title="Attach a video (MP4, MOV, WebM · up to 45 MB)"
            >
              <Plus className="h-[18px] w-[18px]" />
            </button>
            <span className="mx-1 h-5 w-px bg-border" />
            <button
              type="button"
              disabled
              className="grid h-9 w-9 place-items-center rounded-lg text-muted-foreground/50"
              title="Paste a stream link — coming soon"
              aria-label="Paste a link (coming soon)"
            >
              <Link2 className="h-[17px] w-[17px]" />
            </button>
            <span className="ml-1 hidden items-center gap-1.5 text-[11px] text-muted-foreground sm:flex">
              <Clapperboard className="h-3.5 w-3.5" />
              {file ? "Vertical clips with captions" : "Attach a recording to begin"}
            </span>
            <span className="ml-auto mr-2 hidden text-[10px] text-muted-foreground/70 sm:block">
              {instructions.length}/2000
            </span>
            {file && (
              <span className="mr-2 rounded-md bg-ember/10 px-2 py-1 text-[10px] text-ember">
                ~{Math.max(1, Math.ceil(file.size / 5_000_000))} credits
              </span>
            )}
            <button
              type="button"
              onClick={() => void startUpload()}
              disabled={busy}
              className="ml-auto grid h-10 w-10 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground shadow-pop transition hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-70 sm:ml-0"
              aria-label={file ? "Start clipping" : "Choose a video"}
              title={file ? "Start clipping" : "Choose a video"}
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : file ? (
                <ArrowUp className="h-4 w-4" />
              ) : (
                <UploadCloud className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
        {busy && (
          <div className="flex items-center justify-between px-3 pb-1 pt-2 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-ember" /> Working on it…
            </span>
            <div className="h-1 w-24 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-ember transition-[width]"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="no-scrollbar mt-3 flex gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:justify-center">
        {prompts.map((prompt, index) => {
          const Icon = [Laugh, Flame, Timer][index] ?? Sparkles;
          return (
            <button
              type="button"
              key={prompt.label}
              disabled={busy}
              onClick={() => setInstructions(prompt.value)}
              className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-soft transition hover:-translate-y-0.5 hover:border-ember/30 hover:text-foreground"
            >
              <Icon className="h-3.5 w-3.5 text-ember" />
              {prompt.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
