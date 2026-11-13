import { requireAuth } from "@/lib/auth";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { useStore } from "@/lib/store";
import { PageHeader, EmptyState } from "@/components/Page";

export const Route = createFileRoute("/trash")({
  beforeLoad: requireAuth,
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Recently Deleted — Noethara Clipz" },
      { name: "description", content: "Restore projects deleted in the last 30 days." },
      { property: "og:title", content: "Recently Deleted — Noethara Clipz" },
      { property: "og:description", content: "Restore projects deleted in the last 30 days." },
    ],
  }),
  component: Trash,
});

function Trash() {
  const { projects, setDeleted } = useStore();
  const list = projects.filter((p) => p.deleted);
  return (
    <div className="animate-fade-up p-4 sm:p-8">
      <PageHeader title="Recently Deleted" sub="Projects stay here for 30 days." />
      {list.length ? (
        <div className="space-y-3">
          {list.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-3 rounded-2xl border bg-card p-3 shadow-soft"
            >
              <img src={p.thumb} alt="" className="h-14 w-24 shrink-0 rounded-lg object-cover" />
              <p className="min-w-0 flex-1 truncate text-sm font-medium">{p.title}</p>
              <button
                onClick={() =>
                  void setDeleted(p.id, false)
                    .then(() => toast.success("Restored"))
                    .catch((e) => toast.error(e.message))
                }
                className="flex shrink-0 items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm shadow-soft hover:shadow-pop"
              >
                <RotateCcw className="h-4 w-4" /> Restore
              </button>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Trash is empty" sub="Deleted projects will show up here." />
      )}
    </div>
  );
}
