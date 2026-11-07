import { requireAuth } from "@/lib/auth";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { VideoCard } from "@/components/VideoCard";
import { PageHeader, EmptyState } from "@/components/Page";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/library")({
  beforeLoad: requireAuth,
  head: () => ({
    meta: [
      { title: "Library — Clipwave" },
      { name: "description", content: "All your imported streams and videos in one place." },
      { property: "og:title", content: "Library — Clipwave" },
      { property: "og:description", content: "All your imported streams and videos in one place." },
    ],
  }),
  component: LibraryPage,
});

const filters = ["All", "Ready", "Processing", "YouTube", "Twitch", "Kick"] as const;

function LibraryPage() {
  const { projects } = useStore();
  const [f, setF] = useState<(typeof filters)[number]>("All");
  const search =
    typeof window !== "undefined"
      ? (new URLSearchParams(window.location.search).get("q") ?? "")
      : "";
  const list = projects
    .filter((p) => p.title.toLowerCase().includes(search.toLowerCase()))
    .filter((p) => !p.deleted)
    .filter((p) =>
      f === "All"
        ? true
        : f === "Ready"
          ? p.status === "ready"
          : f === "Processing"
            ? p.status !== "ready"
            : p.platform === f,
    );
  return (
    <div className="animate-fade-up p-4 sm:p-8">
      <PageHeader title="Library" sub="Every video you've brought into Clipwave." />
      <div className="no-scrollbar mb-6 flex gap-2 overflow-x-auto">
        {filters.map((x) => (
          <button
            key={x}
            onClick={() => setF(x)}
            className={cn(
              "shrink-0 rounded-full border px-3 py-1.5 text-sm transition",
              f === x
                ? "bg-foreground text-background shadow-pop"
                : "bg-card shadow-soft hover:shadow-pop",
            )}
          >
            {x}
          </button>
        ))}
      </div>
      {list.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {list.map((p) => (
            <VideoCard key={p.id} p={p} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="Nothing here yet"
          sub="Try another filter or import a video from Home."
        />
      )}
    </div>
  );
}
