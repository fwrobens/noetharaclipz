import { requireAuth } from "@/lib/auth";
import { createFileRoute } from "@tanstack/react-router";
import { Folder } from "lucide-react";
import { useStore } from "@/lib/store";
import { VideoCard } from "@/components/VideoCard";
import { PageHeader } from "@/components/Page";

export const Route = createFileRoute("/projects")({
  beforeLoad: requireAuth,
  head: () => ({
    meta: [
      { title: "Projects — Clipwave" },
      { name: "description", content: "Your clipping projects organized by destination." },
      { property: "og:title", content: "Projects — Clipwave" },
      { property: "og:description", content: "Your clipping projects organized by destination." },
    ],
  }),
  component: ProjectsPage,
});

function ProjectsPage() {
  const { projects } = useStore();
  const folders = ["TikTok", "YouTube", "IG Reels"] as const;
  return (
    <div className="animate-fade-up p-4 sm:p-8">
      <PageHeader title="Projects" sub="Grouped by where your clips are headed." />
      <div className="space-y-10">
        {folders.map((f) => {
          const list = projects.filter((p) => !p.deleted && p.folder === f);
          return (
            <section key={f}>
              <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
                <Folder className="h-4 w-4 text-primary" /> {f}{" "}
                <span className="text-sm font-normal text-muted-foreground">· {list.length}</span>
              </h2>
              {list.length ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {list.map((p) => (
                    <VideoCard key={p.id} p={p} />
                  ))}
                </div>
              ) : (
                <p className="rounded-2xl border border-dashed p-6 text-sm text-muted-foreground">
                  No projects in this folder yet.
                </p>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
