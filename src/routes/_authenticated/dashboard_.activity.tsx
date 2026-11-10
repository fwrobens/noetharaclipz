import { createFileRoute } from "@tanstack/react-router";
import { Clapperboard, FolderOpen, Loader2, WandSparkles } from "lucide-react";
import { useMemo } from "react";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import {
  buildWeeklyActivity,
  DashboardLoadError,
  DashboardLoading,
  formatProjectAge,
  getProjectProgress,
  getProjectStatus,
  isProjectActive,
} from "@/components/dashboard/projects";
import { useWorkspace } from "@/components/dashboard/useWorkspace";
import { creatorQuery } from "@/lib/creator-query";
import { pageHead } from "@/lib/seo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/dashboard_/activity")({
  head: () =>
    pageHead("Activity — Creator studio", "Follow processing progress and weekly activity in Noethara Clipz."),
  loader: ({ context }) => context.queryClient.ensureQueryData(creatorQuery()),
  pendingComponent: DashboardLoading,
  pendingMs: 300,
  errorComponent: DashboardLoadError,
  component: ActivityPage,
});

function ActivityPage() {
  const { projects, shellProps } = useWorkspace();
  const weekly = useMemo(() => buildWeeklyActivity(projects), [projects]);
  const active = projects.filter(isProjectActive);
  const clips = projects.reduce((sum, project) => sum + (project.highlights?.length ?? 0), 0);
  const stats = [
    { icon: FolderOpen, label: "Projects", value: projects.length },
    { icon: Clapperboard, label: "Clips found", value: clips },
    { icon: WandSparkles, label: "Processing", value: active.length },
  ];

  return (
    <DashboardShell {...shellProps}>
      <div className="animate-in-up">
        <h1 className="text-2xl font-medium tracking-tight sm:text-3xl">Activity</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">What's happening across your workspace.</p>
      </div>

      <div className="mt-6 grid grid-cols-3 gap-2.5 sm:gap-4">
        {stats.map((stat, index) => (
          <div
            key={stat.label}
            className="animate-in-up rounded-2xl border border-border bg-card/80 p-3 shadow-soft transition hover:-translate-y-1 hover:shadow-pop sm:p-5"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-[11px] text-muted-foreground sm:text-xs">{stat.label}</p>
              <stat.icon className="hidden h-4 w-4 text-ember sm:block" />
            </div>
            <p className="mt-2 font-display text-3xl leading-none sm:text-4xl">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,1fr)]">
        <section className="animate-in-up rounded-[20px] border border-border bg-card/80 p-5 shadow-pop sm:p-6">
          <h2 className="text-sm font-medium">Processing queue</h2>
          <p className="mt-1 text-xs text-muted-foreground">Videos AI is working on right now.</p>
          {active.length ? (
            <ul className="mt-5 space-y-3">
              {active.map((project) => {
                const progress = getProjectProgress(project) ?? 0;
                const status = getProjectStatus(project);
                return (
                  <li key={project.id} className="rounded-xl border border-border bg-surface/60 p-3.5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="flex min-w-0 items-center gap-2 text-sm font-medium">
                        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-ember" />
                        <span className="truncate">{project.title}</span>
                      </p>
                      <span className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[10px]", status.className)}>
                        {progress}%
                      </span>
                    </div>
                    <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-ember" style={{ width: `${progress}%` }} />
                    </div>
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      Started {formatProjectAge(project.created_at)}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-5 rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              The queue is clear.
            </p>
          )}
        </section>

        <section className="animate-in-up rounded-[20px] border border-border bg-card/80 p-5 shadow-pop sm:p-6">
          <h2 className="text-sm font-medium">This week</h2>
          <p className="mt-1 text-xs text-muted-foreground">Projects created in the last 7 days</p>
          <div className="mt-6 flex items-end justify-between gap-2">
            {weekly.days.map((day) => (
              <div key={day.key} className="flex h-[110px] flex-1 flex-col items-center justify-end gap-2">
                <span className="text-[10px] text-muted-foreground">{day.count || ""}</span>
                <div className="flex h-[72px] w-full max-w-7 items-end overflow-hidden rounded-md bg-muted/70">
                  <div
                    className={cn(
                      "w-full rounded-md transition-[height] duration-700",
                      day.count ? "bg-ember" : "bg-muted-foreground/20",
                    )}
                    style={{ height: `${day.count ? Math.max(18, (day.count / weekly.max) * 100) : 5}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">{day.label}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-xs">
            <span className="text-muted-foreground">Total this week</span>
            <span className="font-medium">{weekly.total}</span>
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}
