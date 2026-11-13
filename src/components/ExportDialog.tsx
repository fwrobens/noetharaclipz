import { useBrand } from "@/lib/brand";
import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useStore, must } from "@/lib/store";
import { supabase } from "@/lib/supabase/client";
import { defaultEdit, editSchema, type ClipEdit, activeJob } from "@/lib/editor";
import { downloadRenderedClip } from "@/lib/media";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
export function ExportDialog({
  open,
  onOpenChange,
  projectId,
  highlightIds,
  edit,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  projectId: string;
  highlightIds: string[];
  edit?: ClipEdit;
  onSaved?: () => void;
}) {
  const { projects, clips, jobs, saveClip, exportClip, retryJob, cancelJob } = useStore();
  const { brand } = useBrand();
  const [ratio, setRatio] = useState<ClipEdit["ratio"]>(edit?.ratio ?? "9:16");
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedClipIds = clips
    .filter((c) => highlightIds.includes(c.highlight_id))
    .map((c) => c.id);
  const renders = jobs
    .filter((j) =>
      jobIds.length
        ? jobIds.includes(j.id)
        : j.kind === "render" && selectedClipIds.includes(j.clip_id ?? ""),
    )
    .slice(0, 3);
  useEffect(() => {
    if (open) setRatio(edit?.ratio ?? brand.ratio);
  }, [open, edit?.ratio, brand.ratio]);
  const pending = renders.some((j) => activeJob(j.status));
  async function run() {
    setBusy(true);
    setError("");
    const ids: string[] = [];
    try {
      for (const hid of highlightIds) {
        const h = projects.find((p) => p.id === projectId)?.highlights.find((h) => h.id === hid);
        if (!h) throw new Error("Highlight no longer exists");
        const existing = clips.find((c) => c.highlight_id === hid);
        const settings = edit
          ? { ...edit }
          : existing
            ? { ...(existing.edit as unknown as ClipEdit), ratio }
            : { ...defaultEdit(h), ...brand, ratio };
        let cid = existing?.id;
        if (
          !existing ||
          JSON.stringify(editSchema.parse(settings)) !==
            JSON.stringify(editSchema.parse(existing.edit))
        )
          cid = await saveClip(hid, settings, existing?.revision);
        const row = must(await supabase.from("clips").select("*").eq("id", cid!).single());
        ids.push(await exportClip(row));
        setJobIds([...ids]);
      }
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }
  async function download(path: string) {
    try {
      await downloadRenderedClip(path);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed");
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto rounded-3xl shadow-float sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display">
            Export {highlightIds.length} clip{highlightIds.length === 1 ? "" : "s"}
          </DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-2">
          {(["9:16", "16:9", "1:1", "4:5"] as const).map((r) => (
            <button
              key={r}
              disabled={!!edit || pending}
              onClick={() => setRatio(r)}
              className={cn(
                "rounded-xl border p-3 text-left text-sm transition",
                (edit?.ratio ?? ratio) === r
                  ? "border-primary bg-accent shadow-pop"
                  : "hover:bg-muted",
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          MP4 · H.264 / AAC · up to 720p · maximum 60 seconds per clip
        </p>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {renders.map((j) => (
          <div key={j.id} className="space-y-2 rounded-xl border p-3">
            <p role="status" className="text-sm">
              {j.stage} · {j.progress}%
            </p>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${j.progress}%` }}
              />
            </div>
            {j.error && <p className="break-words text-xs text-destructive">{j.error}</p>}
            {activeJob(j.status) && (
              <button
                onClick={() => void cancelJob(j.id).catch((e) => toast.error(e.message))}
                className="text-sm text-muted-foreground"
              >
                Cancel
              </button>
            )}
            {["failed", "cancelled"].includes(j.status) && (
              <button
                onClick={() => void retryJob(j.id).catch((e) => toast.error(e.message))}
                className="text-sm text-primary"
              >
                Retry
              </button>
            )}
            {j.status === "completed" &&
              typeof (j.payload as Record<string, unknown>)["output_path"] === "string" && (
                <button
                  onClick={() =>
                    void download((j.payload as Record<string, string>)["output_path"]!)
                  }
                  className="rounded-xl bg-primary px-4 py-2 text-sm text-primary-foreground"
                >
                  Download MP4
                </button>
              )}
          </div>
        ))}
        <button
          onClick={() => void run()}
          disabled={busy || pending || !highlightIds.length}
          className="w-full rounded-xl bg-primary py-2.5 text-sm font-medium text-primary-foreground shadow-pop disabled:opacity-60"
        >
          {busy
            ? "Submitting…"
            : pending
              ? renders.every((j) => j.status === "queued")
                ? "Queued…"
                : "Rendering…"
              : "Export"}
        </button>
      </DialogContent>
    </Dialog>
  );
}
