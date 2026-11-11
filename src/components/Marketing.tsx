import { Link } from "@tanstack/react-router";
import { ArrowUpRight, Scissors, Captions, Focus, Sparkles, Play } from "lucide-react";
import { Brand } from "./Brand";
import { Button } from "./ui/button";
import studio from "@/assets/creator-studio.jpg";
export function ProductPreview() {
  return (
    <div className="product-preview mx-auto overflow-hidden rounded-lg border border-border bg-card shadow-float">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-xs">
          <Scissors className="h-4 w-4 text-primary" /> Noethara workspace{" "}
          <span className="ml-2 hidden text-muted-foreground sm:inline">/ Creator session</span>
        </div>
        <span className="rounded bg-accent px-2 py-1 text-[10px] text-primary">
          PRODUCT PREVIEW
        </span>
      </div>
      <div className="grid sm:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
        <div className="min-w-0 border-border p-4 sm:border-r sm:p-6">
          <div className="relative aspect-video overflow-hidden rounded-md">
            <img
              src={studio}
              width={1920}
              height={1024}
              alt="Podcast recording preview"
              loading="lazy"
              className="h-full w-full object-cover"
            />
            <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded bg-cover-background/80 px-2 py-1 text-xs text-cover-foreground">
              <Play className="h-3 w-3" /> 00:24 / 12:48
            </div>
          </div>
          <div className="mt-4 flex h-10 items-center gap-1 overflow-hidden">
            {Array.from({ length: 48 }, (_, i) => (
              <div
                key={i}
                className={`wave-bar shrink-0 rounded-sm bg-primary/40 ${["h-3", "h-5", "h-8", "h-4", "h-6"][i % 5]}`}
              />
            ))}
          </div>
          <div className="mt-3 flex justify-between text-[10px] text-muted-foreground">
            <span>00:00</span>
            <span>04:00</span>
            <span>08:00</span>
            <span>12:48</span>
          </div>
        </div>
        <div className="min-w-0 p-4 sm:p-6">
          <p className="flex items-center gap-2 text-xs font-medium">
            <Sparkles className="h-4 w-4 text-primary" /> Moments worth sharing
          </p>
          <div className="mt-4 space-y-3">
            {[
              "The moment it all clicked",
              "A take nobody expected",
              "One tip that changes everything",
            ].map((t, i) => (
              <div key={t} className="flex items-center gap-3 border-b border-border pb-3">
                <img
                  src={studio}
                  alt=""
                  loading="lazy"
                  className="h-14 w-20 shrink-0 rounded object-cover"
                />
                <div className="min-w-0">
                  <p className="text-xs leading-relaxed">{t}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {["00:24 – 00:58", "03:12 – 03:46", "08:04 – 08:38"][i]}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <Button asChild variant="outline" className="mt-5 w-full">
            <Link to="/auth">
              Make your first clip <ArrowUpRight />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
export function FeatureContent() {
  const items = [
    {
      icon: Scissors,
      n: "01",
      title: "Find the moment.",
      desc: "Bring your long-form video into one workspace and turn standout moments into short-form stories.",
    },
    {
      icon: Captions,
      n: "02",
      title: "Give it your voice.",
      desc: "Keep your caption style and preferred platform together in your creator profile.",
    },
    {
      icon: Focus,
      n: "03",
      title: "Keep the focus.",
      desc: "Review highlights, refine your framing, and prepare your next clip for its audience.",
    },
  ];
  return (
    <section className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-24">
      <div className="mb-12 max-w-2xl">
        <p className="section-label">BUILT AROUND YOUR CONTENT</p>
        <h2 className="mt-4 text-3xl font-medium sm:text-4xl">
          The full story.
          <br />
          <span className="text-muted-foreground">Just the best parts.</span>
        </h2>
      </div>
      <div className="grid gap-8 md:grid-cols-3">
        {items.map((x) => (
          <article key={x.n} className="border-t border-border pt-6">
            <div className="flex items-center justify-between">
              <x.icon className="h-6 w-6 text-primary" />
              <span className="font-mono text-xs text-muted-foreground">{x.n}</span>
            </div>
            <h3 className="mt-8 text-xl font-medium">{x.title}</h3>
            <p className="mt-3 max-w-sm text-sm leading-7 text-muted-foreground">{x.desc}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col justify-between gap-5 px-5 py-8 sm:flex-row sm:items-center sm:px-8">
        <Brand />
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} Noethara Clipz. Made for the moments.
        </p>
        <Link to="/auth" className="text-xs text-muted-foreground">
          Your account <ArrowUpRight className="ml-1 inline h-3 w-3" />
        </Link>
      </div>
    </footer>
  );
}
