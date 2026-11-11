import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Film, SearchX } from "lucide-react";
import { useMemo, useState } from "react";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import {
  DashboardLoadError,
  DashboardLoading,
  isProjectActive,
  ProjectCard,
  ProjectDialog,
} from "@/components/dashboard/projects";
import { useWorkspace } from "@/components/dashboard/useWorkspace";
import { creatorQuery } from "@/lib/creator-query";
import { pageHead } from "@/lib/seo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/dashboard_/projects")({
  head: () =>
    pageHead(
      "Projects — Creator studio",
      "Browse, search and review all your Noethara Clipz projects.",
    ),
  loader: ({ context }) => context.queryClient.ensureQueryData(creatorQuery()),
  pendingComponent: DashboardLoading,
  pendingMs: 300,
  errorComponent: DashboardLoadError,
  component: ProjectsPage,
});

type Filter = "all" | "ready" | "active";

function ProjectsPage() {
  const { projects, shellProps } = useWorkspace();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = projects.find((project) => project.id === selectedId) ?? null;

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return projects.filter((project) => {
      const text =
        `${project.title} ${project.source_platform} ${project.instructions}`.toLowerCase();
      const matchesFilter =
        filter === "all" ||
        (filter === "ready" ? project.status === "ready" : isProjectActive(project));
      return (!query || text.includes(query)) && matchesFilter;
    });
  }, [filter, projects, search]);

  const filtered = Boolean(search) || filter !== "all";

  return (
    <DashboardShell {...shellProps} search={search} onSearchChange={setSearch}>
      <div className="animate-in-up flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-medium tracking-tight sm:text-3xl">Projects</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">Every recording you've brought in.</p>
        </div>
        <div className="no-scrollbar flex gap-2 overflow-x-auto">
          {(["all", "ready", "active"] as Filter[]).map((value) => (
            <button
              type="button"
              key={value}
              onClick={() => setFilter(value)}
              aria-pressed={filter === value}
              className={cn(
                "shrink-0 rounded-lg border px-3.5 py-2 text-xs transition",
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

      {visible.length ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((project, index) => (
            <ProjectCard
              key={project.id}
              project={project}
              index={index}
              onOpen={() => setSelectedId(project.id)}
            />
          ))}
        </div>
      ) : (
        <div className="mt-6 flex flex-col items-center rounded-[20px] border border-dashed border-border bg-card/50 px-6 py-14 text-center shadow-soft">
          <span className="grid h-14 w-14 place-items-center rounded-2xl border border-ember/20 bg-ember/10 text-ember shadow-pop">
            {filtered ? <SearchX className="h-6 w-6" /> : <Film className="h-6 w-6" />}
          </span>
          <h3 className="mt-5 text-lg font-medium">
            {filtered ? "No matching projects" : "No projects yet"}
          </h3>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            {filtered
              ? "Try another search or filter."
              : "Upload a recording and let AI find your best moments."}
          </p>
          {filtered ? (
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setFilter("all");
              }}
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-surface px-4 text-sm shadow-soft"
            >
              Clear filters
            </button>
          ) : (
            <Link
              to="/dashboard"
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-surface px-4 text-sm shadow-soft"
            >
              Create your first clip <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>
      )}

      <ProjectDialog project={selected} onOpenChange={(open) => !open && setSelectedId(null)} />
    </DashboardShell>
  );
}
