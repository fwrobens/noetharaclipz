import { useBrand } from "@/lib/brand";
import { requireAuth } from "@/lib/auth";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { templates } from "@/lib/domain";
import { PageHeader } from "@/components/Page";

export const Route = createFileRoute("/templates")({
  beforeLoad: requireAuth,
  head: () => ({
    meta: [
      { title: "Templates — Clipwave" },
      { name: "description", content: "Ready-made caption and layout styles for every platform." },
      { property: "og:title", content: "Templates — Clipwave" },
      {
        property: "og:description",
        content: "Ready-made caption and layout styles for every platform.",
      },
    ],
  }),
  component: TemplatesPage,
});

function TemplatesPage() {
  const { save } = useBrand();
  return (
    <div className="animate-fade-up p-4 sm:p-8">
      <PageHeader title="Templates" sub="One click to style a clip for any platform." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {templates.map((t) => (
          <button
            key={t.name}
            onClick={() =>
              void save({
                ratio: t.ratio as "9:16" | "4:5" | "16:9",
                caption_style:
                  t.name === "IG Reels Clean"
                    ? "Minimal"
                    : t.name === "YouTube Shorts Recap"
                      ? "Karaoke"
                      : "Bold pop",
              })
                .then(() => toast.success(`${t.name} saved as default`))
                .catch((e) => toast.error(e.message))
            }
            className="group overflow-hidden rounded-2xl border bg-card text-left lift"
          >
            <div className="relative aspect-[4/3] overflow-hidden bg-muted">
              <img
                src={t.thumb}
                alt=""
                loading="lazy"
                className="h-full w-full object-cover opacity-90 transition group-hover:scale-105"
              />
              <span className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-lg bg-warning px-2 py-1 font-display text-sm font-bold text-foreground shadow-pop">
                CAPTION STYLE
              </span>
              <span className="absolute right-2 top-2 rounded-md bg-card/90 px-1.5 py-0.5 text-[11px] font-medium shadow-soft">
                {t.ratio}
              </span>
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
