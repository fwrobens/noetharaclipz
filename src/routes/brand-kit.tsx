import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Upload } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/Page";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/brand-kit")({
  head: () => ({
    meta: [
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { title: "Brand Kit — Noethara Clipz" },
      { name: "description", content: "Your logo, colors and fonts applied to every clip." },
      { property: "og:title", content: "Brand Kit — Noethara Clipz" },
      { property: "og:description", content: "Your logo, colors and fonts applied to every clip." },
    ],
  }),
  component: BrandKit,
});

const swatches = ["bg-primary", "bg-warning", "bg-success", "bg-destructive", "bg-foreground", "bg-glow-3"];
const fonts = ["Bricolage Grotesque", "Instrument Sans", "Mono"];

function BrandKit() {
  const [color, setColor] = useState(0);
  const [font, setFont] = useState(0);
  return (
    <div className="animate-fade-up p-4 sm:p-8">
      <PageHeader title="Brand Kit" sub="Applied automatically to new clips." />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border bg-card p-5 shadow-soft">
          <p className="text-sm font-medium">Logo / watermark</p>
          <button onClick={() => toast("Logo upload is simulated in this prototype")} className="mt-3 flex h-32 w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed text-sm text-muted-foreground transition hover:bg-muted">
            <Upload className="h-5 w-5" /> Upload PNG or SVG
          </button>
        </div>
        <div className="rounded-2xl border bg-card p-5 shadow-soft">
          <p className="text-sm font-medium">Caption highlight color</p>
          <div className="mt-3 flex flex-wrap gap-3">
            {swatches.map((s, i) => (
              <button key={s} onClick={() => setColor(i)} className={cn("h-10 w-10 rounded-full shadow-pop transition hover:scale-110", s, color === i && "ring-2 ring-ring ring-offset-2 ring-offset-card")} aria-label={`Color ${i + 1}`} />
            ))}
          </div>
        </div>
        <div className="rounded-2xl border bg-card p-5 shadow-soft">
          <p className="text-sm font-medium">Caption font</p>
          <div className="mt-3 space-y-2">
            {fonts.map((f, i) => (
              <button key={f} onClick={() => setFont(i)} className={cn("w-full rounded-xl border px-3 py-2 text-left text-sm transition", font === i ? "border-primary bg-accent shadow-soft" : "hover:bg-muted", i === 0 && "font-display", i === 2 && "font-mono")}>{f}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
