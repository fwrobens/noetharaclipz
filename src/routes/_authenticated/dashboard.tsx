import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { Brand } from "@/components/Brand";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { UploadComposer } from "@/components/dashboard/UploadComposer";
import {
  DashboardLoadError,
  DashboardLoading,
  ProjectCard,
  ProjectDialog,
} from "@/components/dashboard/projects";
import { useWorkspace } from "@/components/dashboard/useWorkspace";
import { creatorQuery } from "@/lib/creator-query";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () =>
    pageHead(
      "New clip — Creator studio",
      "Upload a recording, tell AI what moments you want, and get vertical clips with Noethara Clipz.",
    ),
  loader: ({ context }) => context.queryClient.ensureQueryData(creatorQuery()),
  pendingComponent: DashboardLoading,
  pendingMs: 300,
  errorComponent: DashboardLoadError,
  component: StudioPage,
});

function StudioPage() {
  const { projects, firstName, shellProps, refresh } = useWorkspace();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const recent = projects.slice(0, 3);
  const selected = projects.find((project) => project.id === selectedId) ?? null;

  return (
    <DashboardShell {...shellProps}>
      <section className="mx-auto max-w-3xl pt-4 sm:pt-12 lg:pt-16">
        <div className="animate-in-up mb-7 text-center sm:mb-9">
          <div className="mb-5 flex justify-center">
            <Brand />
          </div>
          <h1 className="text-[1.9rem] font-medium leading-tight tracking-[-0.035em] sm:text-5xl">
            What should we clip,{" "}
            <span className="font-display italic text-ember [overflow-wrap:anywhere]">
              {firstName}?
            </span>
          </h1>
          <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground sm:text-base">
            Attach a recording and describe the moments you want. AI does the rest.
          </p>
        </div>
        <div className="animate-in-up" style={{ animationDelay: "120ms" }}>
          <UploadComposer onUploaded={refresh} />
        </div>
      </section>

      <section className="animate-in-up mt-14 sm:mt-20" style={{ animationDelay: "220ms" }}>
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-medium tracking-tight">Recent projects</h2>
            <p className="mt-1 text-sm text-muted-foreground">Pick up where you left off.</p>
          </div>
          {projects.length > 0 && (
            <Link
              to="/dashboard/projects"
              className="inline-flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground transition hover:text-foreground"
            >
              View all <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>
        {recent.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((project, index) => (
              <ProjectCard
                key={project.id}
                project={project}
                index={index}
                onOpen={() => setSelectedId(project.id)}
              />
            ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-border bg-card/50 p-8 text-center text-sm text-muted-foreground shadow-soft">
            Your projects will appear here after your first upload.
          </p>
        )}
      </section>

      <ProjectDialog project={selected} onOpenChange={(open) => !open && setSelectedId(null)} />
    </DashboardShell>
  );
}
