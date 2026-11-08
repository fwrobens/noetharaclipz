import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { templates } from "@/lib/mock";
import { PageHeader } from "@/components/Page";

export const Route = createFileRoute("/templates")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Templates — Noethara Clipz" },
      { name: "description", content: "Ready-made caption and layout styles for every platform." },
      { property: "og:title", content: "Templates — Noethara Clipz" },
      { property: "og:description", content: "Ready-made caption and layout styles for every platform." },
    ],
  }),
  component: TemplatesPage,
});

function TemplatesPage() {
  return (
    <div className="animate-fade-up p-4 sm:p-8">
      <PageHeader title="Templates" sub="One click to style a clip for any platform." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {templates.map((t) => (
          <button key={t.name} onClick={() => toast.success(`${t.name} set as default`)} className="group overflow-hidden rounded-2xl border bg-card text-left lift">
            <div className="relative aspect-[4/3] overflow-hidden bg-muted">
              <img src={t.thumb} alt="" loading="lazy" className="h-full w-full object-cover opacity-90 transition group-hover:scale-105" />
              <span className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-lg bg-warning px-2 py-1 font-display text-sm font-bold text-foreground shadow-pop">CAPTION STYLE</span>
              <span className="absolute right-2 top-2 rounded-md bg-card/90 px-1.5 py-0.5 text-[11px] font-medium shadow-soft">{t.ratio}</span>
            </div>
            <div className="p-3">
              <p className="text-sm font-medium">{t.name}</p>
              <p className="text-xs text-muted-foreground">{t.desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
