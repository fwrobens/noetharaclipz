import { createFileRoute } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowRight,
  ArrowUpRight,
  Clapperboard,
  Clock3,
  Film,
  FolderOpen,
  Layers3,
  Loader2,
  Play,
  SearchX,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { focusComposer } from "@/components/dashboard/focusComposer";
import { UploadComposer } from "@/components/dashboard/UploadComposer";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { creatorQuery } from "@/lib/creator-query";
import type { loadCreator } from "@/lib/creator.functions";
import { fmt } from "@/lib/mock";
import { pageHead } from "@/lib/seo";
import { useSessionUser } from "@/lib/session";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () =>
    pageHead(
      "Creator dashboard",
      "Upload recordings, find standout moments, and review your Noethara Clipz projects.",
    ),
  loader: ({ context }) => context.queryClient.ensureQueryData(creatorQuery()),
  component: DashboardPage,
});

type CreatorData = Awaited<ReturnType<typeof loadCreator>>;
type CreatorProject = CreatorData["projects"][number];
type ProjectFilter = "all" | "ready" | "active";

function DashboardPage() {
  const { data } = useSuspenseQuery(creatorQuery());
  const user = useSessionUser();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<ProjectFilter>("all");
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const queryClient = Route.useRouteContext().queryClient;

  const projects = useMemo(
    () => data.projects.filter((project) => !project.deleted_at),
    [data.projects],
  );
  const totalHighlights = projects.reduce((total, project) => total + project.highlights.length, 0);
  const activeProjects = projects.filter((project) => isProjectActive(project));
  const displayName =
    data.profile?.display_name?.trim() ||
    user?.user_metadata?.["full_name"] ||
    user?.email?.split("@")[0] ||
    "Creator";
  const firstName = displayName.split(" ")[0] || "Creator";
  const latestProjectId = projects[0]?.id;

  const visibleProjects = useMemo(() => {
    const query = search.trim().toLowerCase();
    return projects.filter((project) => {
      const matchesSearch =
        !query ||
        `${project.title} ${project.source_platform} ${project.instructions}`
          .toLowerCase()
          .includes(query);
      const matchesFilter =
        filter === "all" ||
        (filter === "ready" ? project.status === "ready" : isProjectActive(project));
      return matchesSearch && matchesFilter;
    });
  }, [filter, projects, search]);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const weekly = useMemo(() => buildWeeklyActivity(projects), [projects]);

  const refreshProjects = async () => {
    await queryClient.invalidateQueries({ queryKey: ["creator"] });
  };

  return (
    <DashboardShell
      displayName={displayName}
      email={user?.email}
      avatarUrl={data.profile?.avatar_url}
      projectCount={projects.length}
      search={search}
      onSearchChange={setSearch}
    >
      <section id="overview" className="scroll-mt-28">
        <div className="animate-in-up grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4">
          <div className="min-w-0">
            <p className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-ember">
              <span className="h-1.5 w-1.5 rounded-full bg-ember animate-pulse-dot" /> Your creative
              space
            </p>
            <h1 className="text-[1.75rem] font-medium leading-tight tracking-[-0.035em] sm:text-4xl">
              Welcome back, <span className="font-display italic text-ember">{firstName}.</span>
            </h1>
            <p className="mt-2 text-sm text-muted-foreground sm:text-base">
              Your next standout moment is already in the footage.
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              latestProjectId ? setSelectedProjectId(latestProjectId) : focusComposer()
            }
            className="hidden h-10 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm text-muted-foreground shadow-soft transition hover:-translate-y-0.5 hover:text-foreground sm:flex"
          >
            {latestProjectId ? "Latest project" : "Quick start"}
            <ArrowUpRight className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-7 grid grid-cols-3 gap-2.5 sm:gap-4">
          <StatCard
            icon={FolderOpen}
            label="Projects"
            value={projects.length}
            detail="In your workspace"
            delay="60ms"
          />
          <StatCard
            icon={Clapperboard}
            label="Clips found"
            value={totalHighlights}
            detail="Moments to review"
            delay="120ms"
          />
          <StatCard
            icon={WandSparkles}
            label="Processing"
            value={activeProjects.length}
            detail={activeProjects.length ? "AI is on it" : "Queue is clear"}
            delay="180ms"
          />
        </div>
      </section>

      <div className="mt-6 grid items-start gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,.7fr)]">
        <div className="animate-in-up" style={{ animationDelay: "220ms" }}>
          <UploadComposer onUploaded={refreshProjects} />
        </div>
        <aside
          id="activity"
          className="animate-in-up scroll-mt-28 rounded-[24px] border border-border bg-card/80 p-5 shadow-pop sm:p-6"
          style={{ animationDelay: "280ms" }}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Weekly activity</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Projects created in the last 7 days
              </p>
            </div>
            <span className="grid h-9 w-9 place-items-center rounded-xl border border-border bg-surface text-ember">
              <Layers3 className="h-4 w-4" />
            </span>
          </div>
          <div
            className="mt-6 flex items-end justify-between gap-2"
            aria-label={`${weekly.total} projects created this week`}
          >
            {weekly.days.map((day) => (
              <div
                key={day.key}
                className="flex h-[104px] flex-1 flex-col items-center justify-end gap-2"
              >
                <span className="text-[10px] text-muted-foreground">{day.count || ""}</span>
                <div className="flex h-[72px] w-full max-w-7 items-end overflow-hidden rounded-full bg-muted/70">
                  <div
                    className={cn(
                      "w-full rounded-full transition-[height] duration-700",
                      day.count
                        ? "bg-ember shadow-[0_0_16px_color-mix(in_oklab,var(--ember)_35%,transparent)]"
                        : "bg-muted-foreground/20",
                    )}
                    style={{
                      height: `${day.count ? Math.max(18, (day.count / weekly.max) * 100) : 5}%`,
                    }}
                    title={`${day.label}: ${day.count} ${day.count === 1 ? "project" : "projects"}`}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">{day.label}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-xs">
            <span className="text-muted-foreground">Total this week</span>
            <span className="font-medium text-foreground">
              {weekly.total} {weekly.total === 1 ? "project" : "projects"}
            </span>
          </div>
          <div className="mt-5 rounded-2xl border border-border bg-surface/70 p-4">
            <div className="flex items-center gap-2 text-xs font-medium">
              <Sparkles className="h-3.5 w-3.5 text-ember" /> A simpler workflow
            </div>
            <ol className="mt-3 space-y-2.5 text-xs text-muted-foreground">
              <li className="flex items-center gap-2.5">
                <StepNumber number={1} /> Upload your recording
              </li>
              <li className="flex items-center gap-2.5">
                <StepNumber number={2} /> Describe the best moments
              </li>
              <li className="flex items-center gap-2.5">
                <StepNumber number={3} /> Review your clips
              </li>
            </ol>
          </div>
        </aside>
      </div>

      <section id="projects" className="mt-10 scroll-mt-28 sm:mt-12">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ember">
              Your library
            </p>
            <h2 className="mt-2 text-2xl font-medium tracking-tight">Recent projects</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Pick up where you left off, or review your newest clips.
            </p>
          </div>
          <div className="no-scrollbar flex gap-2 overflow-x-auto">
            {(["all", "ready", "active"] as ProjectFilter[]).map((value) => (
              <button
                type="button"
                key={value}
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={cn(
                  "shrink-0 rounded-full border px-3.5 py-2 text-xs transition",
                  filter === value
                    ? "border-ember/30 bg-ember/10 text-foreground shadow-soft"
                    : "border-border bg-card text-muted-foreground hover:text-foreground",
                )}
              >
                {value === "all"
                  ? `All · ${projects.length}`
                  : value === "ready"
                    ? "Ready"
                    : "In progress"}
              </button>
            ))}
          </div>
        </div>

        {visibleProjects.length ? (
          <div className="mt-6 grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
            {visibleProjects.map((project, index) => (
              <ProjectCard
                key={project.id}
                project={project}
                index={index}
                onOpen={() => setSelectedProjectId(project.id)}
              />
            ))}
          </div>
        ) : (
          <div className="mt-6 flex flex-col items-center rounded-[24px] border border-dashed border-border bg-card/50 px-6 py-14 text-center shadow-soft">
            <span className="grid h-14 w-14 place-items-center rounded-2xl border border-ember/20 bg-ember/10 text-ember shadow-pop">
              {search || filter !== "all" ? (
                <SearchX className="h-6 w-6" />
              ) : (
                <Film className="h-6 w-6" />
              )}
            </span>
            <h3 className="mt-5 text-lg font-medium">
              {search || filter !== "all"
                ? "No matching projects"
                : "Your next great clip starts here"}
            </h3>
            <p className="mt-2 max-w-sm text-sm text-muted-foreground">
              {search || filter !== "all"
                ? "Try another search or filter to find what you're looking for."
                : "Upload a recording above and let AI find the moments your audience will remember."}
            </p>
            <button
              type="button"
              onClick={() => {
                if (search || filter !== "all") {
                  setSearch("");
                  setFilter("all");
                } else focusComposer();
              }}
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-full border border-border bg-surface px-4 text-sm shadow-soft transition hover:-translate-y-0.5 hover:border-ember/30"
            >
              {search || filter !== "all" ? "Clear filters" : "Create your first project"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </section>

      <ProjectDialog
        project={selectedProject}
        onOpenChange={(open) => {
          if (!open) setSelectedProjectId(null);
        }}
      />
    </DashboardShell>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
  delay,
}: {
  icon: typeof FolderOpen;
  label: string;
  value: number;
  detail: string;
  delay: string;
}) {
  return (
    <div
      className="animate-in-up group rounded-2xl border border-border bg-card/80 p-3 shadow-soft transition duration-300 hover:-translate-y-1 hover:border-ember/20 hover:shadow-pop sm:rounded-[20px] sm:p-5"
      style={{ animationDelay: delay }}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-[11px] text-muted-foreground sm:text-xs">{label}</p>
        <span className="hidden h-8 w-8 place-items-center rounded-lg border border-border bg-surface text-muted-foreground transition group-hover:text-ember sm:grid">
          <Icon className="h-3.5 w-3.5" />
        </span>
      </div>
      <p className="mt-2 font-display text-3xl leading-none sm:mt-3 sm:text-4xl">{value}</p>
      <p className="mt-2 hidden truncate text-[11px] text-muted-foreground sm:block">{detail}</p>
    </div>
  );
}

function StepNumber({ number }: { number: number }) {
  return (
    <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full border border-border bg-card text-[10px] text-ember">
      {number}
    </span>
  );
}

function ProjectCard({
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
            <Clapperboard className="h-3.5 w-3.5" /> {project.highlights.length}{" "}
            {project.highlights.length === 1 ? "clip" : "clips"}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock3 className="h-3.5 w-3.5" />{" "}
            {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
          </span>
        </div>
      </div>
    </button>
  );
}

function ProjectDialog({
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
                Updated {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
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
                  {project.highlights.length} total
                </span>
              </div>
              {project.highlights.length ? (
                <div className="mt-3 space-y-2">
                  {[...project.highlights]
                    .sort((a, b) => b.score - a.score)
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
                          {Math.round(highlight.score)} score
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

function isProjectActive(project: CreatorProject) {
  return (
    ["queued", "processing", "uploading", "analyzing"].includes(project.status) ||
    project.processing_jobs.some((job) => ["queued", "running", "processing"].includes(job.status))
  );
}

function getProjectProgress(project: CreatorProject) {
  const job = project.processing_jobs.find((item) =>
    ["queued", "running", "processing"].includes(item.status),
  );
  return job ? Math.max(0, Math.min(100, Math.round(job.progress))) : null;
}

function getProjectStatus(project: CreatorProject) {
  if (project.status === "ready")
    return {
      label: "Ready",
      active: false,
      className: "border-success/20 bg-success/10 text-success",
    };
  if (project.status === "failed" || project.processing_jobs.some((job) => job.status === "failed"))
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

function buildWeeklyActivity(projects: CreatorProject[]) {
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
