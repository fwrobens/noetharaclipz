import { createFileRoute } from "@tanstack/react-router";
import { Footer, Nav, PricingCard, plans } from "@/components/site";

export const Route = createFileRoute("/pricing")({
  head: () => ({
    meta: [
      { title: "Pricing — NoetharaClipZ credits" },
      {
        name: "description",
        content: "Credit-based pricing for AI clipping. Pay for the minutes you process.",
      },
      { property: "og:title", content: "Pricing — NoetharaClipZ credits" },
      {
        property: "og:description",
        content: "Credit-based pricing for AI clipping of YouTube and Twitch.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Pricing,
});

const packs = [
  ["100", "Top-up S"],
  ["500", "Top-up M"],
  ["1,500", "Top-up L"],
];

function Pricing() {
  return (
    <div className="clipspark-skin min-h-screen overflow-x-hidden">
      <Nav />
      <section className="relative mx-auto max-w-6xl px-5 pt-36 pb-24">
        <div className="grid-bg absolute inset-0 -z-10" />
        <div className="animate-in-up text-center">
          <h1 className="text-5xl font-medium tracking-tight sm:text-6xl">
            <span className="text-gradient">Pricing built on</span>{" "}
            <span className="font-display italic text-ember">credits</span>
          </h1>
          <p className="mx-auto mt-5 max-w-md text-muted-foreground">
            Credit plans and pricing are being finalized. No paid plans are active yet.
          </p>
        </div>
        <div className="mt-16 grid gap-6 md:grid-cols-3">
          {plans.map((p) => (
            <PricingCard key={p.name} p={p} />
          ))}
        </div>
        <h2 className="mt-24 text-center text-2xl font-medium">Need more? Grab a credit pack.</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {packs.map(([c, n]) => (
            <div
              key={n}
              className="glow-border glow-border-soft rounded-2xl bg-card p-6 text-center"
            >
              <p className="text-sm text-muted-foreground">{n}</p>
              <p className="mt-2 font-display text-4xl">{c}</p>
              <p className="text-xs text-ember">credits · planned pack</p>
            </div>
          ))}
        </div>
      </section>
      <Footer />
    </div>
  );
}
