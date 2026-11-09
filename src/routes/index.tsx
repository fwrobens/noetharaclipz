import { createFileRoute, Link } from "@tanstack/react-router";
import hero from "@/assets/creator-studio.jpg";
import { Badge, btnClass, Footer, Nav, PricingCard, plans } from "@/components/site";
import { BorderBeam } from "@/components/ui/border-beam";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "NoetharaClipZ — AI clips the best moments of your streams" },
      { name: "description", content: "Drop a YouTube or Twitch link. AI finds the funniest, hypest, most viral moments and turns them into ready-to-post clips." },
      { property: "og:title", content: "NoetharaClipZ — AI clips the best moments" },
      { property: "og:description", content: "Turn hours of VODs and livestreams into viral shorts automatically." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const features = [
  { t: "Moment detection", d: "Multimodal AI scores chat spikes, laughter, reactions and audio peaks to find what matters." },
  { t: "Funny & hype modes", d: "Tell it what you want — fails, clutches, rage, wholesome — and it hunts for exactly that." },
  { t: "Auto-reframe 9:16", d: "Face & action tracking keeps the subject centered for Shorts, TikTok and Reels." },
  { t: "Animated captions", d: "Word-by-word captions with emoji and styles that stop the scroll." },
  { t: "Live stream clipping", d: "Livestream clipping is planned; upload recorded streams today." },
  { t: "Virality score", d: "Every clip is ranked so you post the winners first." },
];

const logos = ["YouTube", "Twitch", "Kick", "TikTok", "Shorts", "Reels", "X", "Rumble"];

function Index() {
  return (
    <div className="clipspark-skin min-h-screen overflow-x-hidden">
      <Nav />

      {/* HERO */}
      <section className="relative pt-32 pb-16 md:pt-40">
        <div className="grid-bg absolute inset-0 -z-10" />
        <div className="ember-orb absolute left-1/2 top-24 -z-10 h-[420px] w-[620px] -translate-x-1/2" />
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 lg:grid-cols-[1.1fr_1fr]">
          <div className="text-center lg:text-left">
            <div className="animate-in-up"><Badge>Find your standout moments</Badge></div>
            <h1 className="animate-in-up mt-6 text-[2.6rem] font-medium leading-[1.05] tracking-tight sm:text-6xl" style={{ animationDelay: "80ms" }}>
              <span className="text-gradient">Your best moments,</span>
              <br />
              <span className="font-display italic text-ember">clipped by AI.</span>
            </h1>
            <p className="animate-in-up mx-auto mt-6 max-w-lg text-muted-foreground lg:mx-0" style={{ animationDelay: "160ms" }}>
              Upload a recording to your workspace. AI helps find standout moments and prepares clips for review. Link imports and livestream clipping are planned.
            </p>
            <div className="animate-in-up mx-auto mt-8 flex max-w-md flex-col gap-3 sm:flex-row lg:mx-0" style={{ animationDelay: "240ms" }}>
              <div className="glow-border glow-border-soft flex h-12 flex-1 items-center rounded-full bg-surface pl-5 pr-1.5">
                <input placeholder="Upload a video in your workspace" className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
                <Link to="/signup" className={btnClass("solid", "sm")}>Start</Link>
                <BorderBeam size={75} duration={7} radius={999} />
              </div>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">Video uploads available · Credits and link imports coming soon</p>
          </div>

          <div className="animate-in-up relative" style={{ animationDelay: "200ms" }}>
            <img src={hero} alt="Chrome film strip" width={1280} height={1024} className="w-full rounded-3xl" />
            <div className="glow-border absolute -bottom-6 left-2 w-60 rounded-2xl bg-card/90 p-3 backdrop-blur-xl sm:left-6">
              <BorderBeam size={70} duration={8} radius={16} />
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Analyzing VOD</span>
                <span className="text-ember">3:42:10</span>
              </div>
              <div className="relative mt-3 flex h-8 items-end gap-[3px] overflow-hidden">
                {Array.from({ length: 34 }).map((_, i) => (
                  <span key={i} className="flex-1 rounded-sm bg-muted-foreground/30" style={{ height: `${20 + Math.abs(Math.sin(i * 1.7)) * 80}%` }} />
                ))}
                <span className="animate-scan absolute top-0 h-full w-px bg-ember shadow-[0_0_12px_var(--ember)]" />
              </div>
            </div>
            <div className="glow-border glow-border-soft absolute -top-4 right-2 rounded-2xl bg-card/90 px-4 py-3 backdrop-blur-xl sm:right-6">
              <BorderBeam size={60} duration={9} radius={16} reverse />
              <p className="text-xs text-muted-foreground">Clips found</p>
              <p className="font-display text-3xl">24 <span className="text-sm text-ember">🔥 8 viral</span></p>
            </div>
          </div>
        </div>
      </section>

      {/* LOGOS */}
      <section className="border-y border-border py-8">
        <div className="relative overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_15%,#000_85%,transparent)]">
          <div className="animate-marquee flex w-max gap-16">
            {[...logos, ...logos].map((l, i) => (
              <span key={i} className="text-lg font-semibold tracking-tight text-muted-foreground/60">{l}</span>
            ))}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="mx-auto max-w-6xl px-5 py-24">
        <div className="grid gap-6 md:grid-cols-2 md:items-end">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-ember">Features</p>
            <h2 className="mt-3 text-4xl font-medium tracking-tight sm:text-5xl">
              Built to find <span className="font-display italic">the moment</span>
            </h2>
          </div>
          <p className="text-muted-foreground">Hours of footage in, a feed of post-ready shorts out. Every clip is scored, captioned and framed.</p>
        </div>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => (
            <div key={f.t} className="surface-card group rounded-2xl p-6 transition hover:-translate-y-1 hover:bg-accent/40">
              <span className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-surface font-display text-lg text-ember">0{i + 1}</span>
              <h3 className="mt-5 font-medium">{f.t}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="mx-auto max-w-6xl px-5 pb-24">
        <div className="glow-border glow-border-soft rounded-3xl bg-card p-8 md:p-14">
          <BorderBeam size={115} duration={12} radius={24} />
          <h2 className="text-center text-4xl font-medium tracking-tight">Three steps. <span className="text-shimmer">Less scrubbing.</span></h2>
          <div className="mt-12 grid gap-10 md:grid-cols-3">
            {[
              ["Upload a recording", "Bring an MP4, MOV or WebM video into your workspace."],
              ["AI watches", "It reads chat, audio and visuals to rank every second."],
              ["Post clips", "Export 9:16 shorts with captions, or publish directly."],
            ].map(([t, d], i) => (
              <div key={t} className="text-center md:text-left">
                <p className="font-display text-6xl text-muted-foreground/40">{i + 1}</p>
                <h3 className="mt-2 font-medium">{t}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section className="mx-auto max-w-6xl px-5 pb-24">
        <div className="text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-ember">Pricing</p>
          <h2 className="mt-3 text-4xl font-medium tracking-tight sm:text-5xl">Simple <span className="font-display italic">credits</span></h2>
          <p className="mt-4 text-muted-foreground">Credit-based plans are being planned; pricing is not active yet.</p>
        </div>
        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {plans.map((p) => <PricingCard key={p.name} p={p} />)}
        </div>
      </section>

      {/* CTA */}
      <section className="relative mx-auto max-w-6xl px-5 pb-28 text-center">
        <div className="ember-orb absolute left-1/2 top-0 -z-10 h-72 w-[500px] -translate-x-1/2" />
        <h2 className="text-4xl font-medium tracking-tight sm:text-6xl"><span className="text-gradient">Less scrubbing.</span><br /><span className="font-display italic text-ember">Start posting.</span></h2>
        <Link to="/signup" className={btnClass("glow", "lg") + " mt-10"}>Get started →<BorderBeam size={45} duration={6} radius={999} /></Link>
      </section>

      <Footer />
    </div>
  );
}