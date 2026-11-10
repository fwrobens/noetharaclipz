import type { ErrorComponentProps } from "@tanstack/react-router";
import { ArrowUpRight, Clapperboard, Clock3, Loader2, Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { loadCreator } from "@/lib/creator.functions";
import { fmt } from "@/lib/mock";
import { cn } from "@/lib/utils";

export type CreatorData = Awaited<ReturnType<typeof loadCreator>>;
export type CreatorProject = CreatorData["projects"][number];

export function ProjectCard({
  project,
  index,
  onOpen,
}: {
  project: CreatorProject;
  index: number;
  onOpen: () => void;
}) {
  const status = getProjectStatus(project);
  const video = project.videos;
  const progress = getProjectProgress(project);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="animate-in-up group overflow-hidden rounded-[20px] border border-border bg-card text-left shadow-soft transition-all duration-300 hover:-translate-y-1.5 hover:border-ember/25 hover:shadow-float"
      style={{ animationDelay: `${Math.min(index, 5) * 60}ms` }}
    >
      <div className="project-visual relative aspect-[16/8.5] overflow-hidden border-b border-border">
        <div className="absolute left-3 top-3 z-10 flex items-center gap-2">
          <span className="rounded-full border border-border bg-cover-background/70 px-2.5 py-1 text-[10px] text-cover-muted backdrop-blur-md">
            {project.source_platform}
          </span>
          <span
            className={cn(
              "rounded-full border px-2.5 py-1 text-[10px] backdrop-blur-md",
              status.className,
            )}
          >
            <span className="mr-1.5 inline-block h-1 w-1 rounded-full bg-current" />
            {status.label}
          </span>
        </div>
        <span className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cover-muted/20 bg-cover-background/45 text-cover-foreground shadow-pop backdrop-blur-md transition duration-300 group-hover:scale-110 group-hover:border-ember/40">
          {status.active ? (
            <Loader2 className="h-5 w-5 animate-spin text-ember" />
          ) : (
            <Play className="ml-0.5 h-4 w-4 fill-current" />
          )}
        </span>
        <div className="absolute inset-x-4 bottom-3 flex items-end justify-between gap-3">
          <div className="flex h-6 flex-1 items-end gap-[3px] opacity-50 transition group-hover:opacity-90">
            {Array.from({ length: 28 }).map((_, bar) => (
              <span
                key={bar}
                className="flex-1 rounded-full bg-cover-muted"
                style={{ height: `${20 + Math.abs(Math.sin(bar * 1.35 + index)) * 75}%` }}
              />
            ))}
          </div>
          {video?.duration != null && (
            <span className="rounded-md bg-cover-background/70 px-2 py-1 font-mono text-[10px] text-cover-muted backdrop-blur-md">
              {fmt(video.duration)}
            </span>
          )}
        </div>
        {progress !== null && (
          <div className="absolute inset-x-0 bottom-0 h-0.5 bg-muted">
            <div
              className="h-full bg-ember transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="line-clamp-1 text-sm font-medium tracking-tight">{project.title}</h3>
          <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-ember" />
        </div>
        <div className="mt-3 flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clapperboard className="h-3.5 w-3.5" /> {(project.highlights?.length ?? 0)}{" "}
            {(project.highlights?.length ?? 0) === 1 ? "clip" : "clips"}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock3 className="h-3.5 w-3.5" />{" "}
            {formatProjectAge(project.updated_at)}
          </span>
        </div>
      </div>
    </button>
  );
}

export function ProjectDialog({
  project,
  onOpenChange,
}: {
  project: CreatorProject | null;
  onOpenChange: (open: boolean) => void;
}) {
  const status = project ? getProjectStatus(project) : null;
  const progress = project ? getProjectProgress(project) : null;
  return (
    <Dialog open={Boolean(project)} onOpenChange={onOpenChange}>
      <DialogContent className="clipspark-skin dashboard-skin max-h-[88vh] overflow-y-auto border-border bg-card text-foreground shadow-float sm:max-w-2xl sm:rounded-3xl">
        {project && (
          <>
            <DialogHeader className="pr-8">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-border bg-surface px-2.5 py-1 text-[10px] text-muted-foreground">
                  {project.source_platform}
                </span>
                {status && (
                  <span
                    className={cn("rounded-full border px-2.5 py-1 text-[10px]", status.className)}
                  >
                    {status.label}
                  </span>
                )}
              </div>
              <DialogTitle className="text-xl font-medium">{project.title}</DialogTitle>
              <DialogDescription>
                Updated {formatProjectAge(project.updated_at)}
              </DialogDescription>
            </DialogHeader>
            {progress !== null && (
              <div className="rounded-2xl border border-border bg-surface p-4">
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-ember" /> Processing your
                    video
                  </span>
                  <span>{progress}%</span>
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-ember" style={{ width: `${progress}%` }} />
                </div>
              </div>
            )}
            <div className="rounded-2xl border border-border bg-surface/60 p-4">
              <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-ember">
                Your instructions
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                {project.instructions || "Find the most engaging moments in this recording."}
              </p>
            </div>
            <div>
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium">Detected moments</h3>
                <span className="text-xs text-muted-foreground">
                  {(project.highlights?.length ?? 0)} total
                </span>
              </div>
              {(project.highlights?.length ?? 0) ? (
                <div className="mt-3 space-y-2">
                  {[...(project.highlights ?? [])]
                    .sort((a, b) => Number(b.score ?? 0) - Number(a.score ?? 0))
                    .map((highlight, index) => (
                      <div
                        key={highlight.id}
                        className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-2xl border border-border bg-surface/50 p-3.5 transition hover:border-ember/20"
                      >
                        <span className="grid h-9 w-9 place-items-center rounded-xl border border-ember/20 bg-ember/10 font-display text-sm text-ember">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{highlight.title}</p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {highlight.category} · {fmt(highlight.start_time)}–
                            {fmt(highlight.end_time)}
                          </p>
                        </div>
                        <span className="rounded-full border border-border bg-card px-2.5 py-1 text-[10px] text-ember">
                          {Math.round(Number(highlight.score ?? 0))} score
                        </span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="mt-3 rounded-2xl border border-dashed border-border p-7 text-center">
                  <Clapperboard className="mx-auto h-5 w-5 text-muted-foreground" />
                  <p className="mt-3 text-sm">No clips to review yet</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Detected moments will appear here when processing finishes.
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function isProjectActive(project: CreatorProject) {
  return (
    ["queued", "processing", "uploading", "analyzing"].includes(project.status) ||
    (project.processing_jobs ?? []).some((job) => ["queued", "running", "processing"].includes(job.status))
  );
}

export function getProjectProgress(project: CreatorProject) {
  const job = (project.processing_jobs ?? []).find((item) =>
    ["queued", "running", "processing"].includes(item.status),
  );
  return job ? Math.max(0, Math.min(100, Math.round(Number(job.progress ?? 0)))) : null;
}

export function getProjectStatus(project: CreatorProject) {
  if (project.status === "ready")
    return {
      label: "Ready",
      active: false,
      className: "border-success/20 bg-success/10 text-success",
    };
  if (project.status === "failed" || (project.processing_jobs ?? []).some((job) => job.status === "failed"))
    return {
      label: "Needs attention",
      active: false,
      className: "border-destructive/20 bg-destructive/10 text-destructive",
    };
  if (isProjectActive(project))
    return {
      label: "Processing",
      active: true,
      className: "border-ember/20 bg-ember/10 text-ember",
    };
  if (project.status === "draft")
    return {
      label: "Needs upload",
      active: false,
      className: "border-border bg-card/70 text-cover-muted",
    };
  return {
    label: project.status.replaceAll("_", " "),
    active: false,
    className: "border-border bg-card/70 text-cover-muted",
  };
}

export function buildWeeklyActivity(projects: CreatorProject[]) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    const next = new Date(date);
    next.setDate(date.getDate() + 1);
    const count = projects.filter((project) => {
      const created = new Date(project.created_at);
      return created >= date && created < next;
    }).length;
    return {
      key: date.toISOString(),
      label: date.toLocaleDateString("en", { weekday: "narrow" }),
      count,
    };
  });
  return {
    days,
    total: days.reduce((sum, day) => sum + day.count, 0),
    max: Math.max(1, ...days.map((day) => day.count)),
  };
}


// Route-scoped fallbacks keep the actual authenticated workspace from going blank
// when its initial query or a newly optimized module fails to load.
export function DashboardLoading() {
  return <div className="clipspark-skin flex min-h-screen items-center justify-center bg-background px-6 text-foreground" role="status">
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-6 py-5 text-sm text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin text-ember" /> Loading your workspace…
    </div>
  </div>;
}

export function DashboardLoadError({ reset }: ErrorComponentProps) {
  return <div className="clipspark-skin flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
    <div className="max-w-md rounded-3xl border border-border bg-card p-7 text-center shadow-pop">
      <h1 className="text-xl font-medium">Your workspace didn't load.</h1>
      <p className="mt-3 text-sm leading-6 text-muted-foreground">This can happen during a preview reload or a temporary connection issue. Your saved projects haven't been changed.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button type="button" className="rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground" onClick={() => { reset(); window.location.reload(); }}>Try again</button>
        <a href="/dashboard-visual-check" className="rounded-full border border-border bg-surface px-5 py-2.5 text-sm">View design demo</a>
      </div>
    </div>
  </div>;
}

export function formatProjectAge(value: string | null | undefined): string {
  if (!value) return "Recently";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "Recently";
  const minutes = Math.round((timestamp - Date.now()) / 60_000);
  if (Math.abs(minutes) < 1) return "Just now";
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return formatter.format(days, "day");
  const months = Math.round(days / 30);
  if (Math.abs(months) < 12) return formatter.format(months, "month");
  return formatter.format(Math.round(months / 12), "year");
}
