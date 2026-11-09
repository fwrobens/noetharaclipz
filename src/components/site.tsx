import { Link } from "@tanstack/react-router";
import { useState, type ReactNode, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import { BorderBeam } from "@/components/ui/border-beam";
import brandImage from "@/assets/noethara-logo.png.asset.json";

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2.5", className)}>
      {/* Logo placeholder — swap the square for your mark */}
      <img src={brandImage.url} alt="" className="h-8 w-8 shrink-0 object-contain" />
      <span className="text-[15px] font-semibold tracking-tight">NoetharaClipZ</span>
    </Link>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "glow" | "ghost" | "solid"; size?: "sm" | "md" | "lg" };

export function btnClass(variant: BtnProps["variant"] = "glow", size: BtnProps["size"] = "md") {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all duration-300 active:scale-[0.98] disabled:opacity-50",
    size === "sm" && "h-9 px-4 text-sm",
    size === "md" && "h-11 px-5 text-sm",
    size === "lg" && "h-12 px-7 text-[15px]",
    variant === "glow" && "glow-border bg-primary text-primary-foreground hover:bg-primary/90",
    variant === "solid" && "bg-primary text-primary-foreground hover:bg-primary/90",
    variant === "ghost" && "glow-border glow-border-soft bg-surface text-foreground hover:bg-accent",
  );
}

export function Button({ variant, size, className, ...p }: BtnProps) {
  return <button className={cn(btnClass(variant, size), className)} {...p}>{p.children}{variant !== "solid" && <BorderBeam size={38} duration={6} radius={999} />}</button>;
}

export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="glow-border glow-border-soft inline-flex items-center gap-2 rounded-full bg-surface px-3.5 py-1.5 text-xs text-muted-foreground">
      <span className="h-1.5 w-1.5 rounded-full bg-ember animate-pulse-dot" />
      {children}
      <BorderBeam size={50} duration={9} radius={999} />
    </span>
  );
}

export function Nav() {
  const [open, setOpen] = useState(false);
  const links = [
    { to: "/" as const, label: "Product", hash: "features" },
    { to: "/pricing" as const, label: "Pricing" },
  ];
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-border bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm text-muted-foreground md:flex">
          <a href="/#features" className="hover:text-foreground">Features</a>
          <a href="/#how" className="hover:text-foreground">How it works</a>
          <Link to="/dashboard" className="hover:text-foreground">Workspace</Link>
          {links.slice(1).map((l) => (
            <Link key={l.label} to={l.to} className="hover:text-foreground">{l.label}</Link>
          ))}
        </nav>
        <div className="hidden items-center gap-3 md:flex">
          <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground">Log in</Link>
          <Link to="/signup" className={btnClass("glow", "sm")}>Get started<BorderBeam size={35} duration={6} radius={999} /></Link>
        </div>
        <button aria-label="Menu" onClick={() => setOpen(!open)} className="grid h-9 w-9 place-items-center rounded-lg border border-border md:hidden">
          <span className="flex flex-col gap-1">
            <span className={cn("h-px w-4 bg-foreground transition", open && "translate-y-[2.5px] rotate-45")} />
            <span className={cn("h-px w-4 bg-foreground transition", open && "-translate-y-[2.5px] -rotate-45")} />
          </span>
        </button>
      </div>
      {open && (
        <div className="animate-in-up border-t border-border px-5 py-5 md:hidden">
          <div className="flex flex-col gap-4 text-sm">
            <a href="/#features" onClick={() => setOpen(false)}>Features</a>
            <a href="/#how" onClick={() => setOpen(false)}>How it works</a>
            <Link to="/pricing" onClick={() => setOpen(false)}>Pricing</Link>
            <Link to="/login" onClick={() => setOpen(false)}>Log in</Link>
            <Link to="/dashboard" onClick={() => setOpen(false)}>Workspace</Link>
            <Link to="/signup" className={btnClass("glow", "md")}>Get started<BorderBeam size={38} duration={6} radius={999} /></Link>
          </div>
        </div>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:grid-cols-2 md:grid-cols-4">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-xs text-sm text-muted-foreground">AI that watches the whole stream so you don't have to.</p>
        </div>
        {[
          ["Product", ["Features", "Pricing", "Changelog"]],
          ["Company", ["About", "Careers", "Contact"]],
          ["Legal", ["Privacy", "Terms"]],
        ].map(([t, items]) => (
          <div key={t as string} className="space-y-3 text-sm">
            <p className="font-medium">{t}</p>
            {(items as string[]).map((i) => (
              <p key={i} className="text-muted-foreground">{i}</p>
            ))}
          </div>
        ))}
      </div>
      <p className="pb-8 text-center text-xs text-muted-foreground">© {new Date().getFullYear()} NoetharaClipZ. All rights reserved.</p>
    </footer>
  );
}

export const plans = [
  { name: "Starter", price: "0", credits: "—", desc: "Preview tier · not available yet.", features: ["Credit plans coming soon", "720p exports", "Watermark", "Basic captions"], cta: "Join waitlist" },
  { name: "Creator", price: "—", credits: "—", desc: "Planned tier · not available yet.", features: ["Credit plans coming soon", "1080p, no watermark", "Funny & hype detection", "Animated captions", "Auto-reframe 9:16"], cta: "Join waitlist", featured: true },
  { name: "Studio", price: "—", credits: "—", desc: "Planned tier · not available yet.", features: ["Credit plans coming soon", "4K exports", "Brand kits", "Team seats", "Priority processing"], cta: "Join waitlist" },
];

export function PricingCard({ p }: { p: (typeof plans)[number] }) {
  return (
    <div className={cn("glow-border flex flex-col rounded-3xl bg-card p-7", !p.featured && "glow-border-soft")}>
      <BorderBeam duration={p.featured ? 7 : 10} size={100} radius={24} borderWidth={p.featured ? 2 : 1.5} />
      <div className="flex items-center justify-between">
        <p className="font-medium">{p.name}</p>
        {p.featured && <span className="rounded-full bg-ember/15 px-2.5 py-1 text-[11px] text-ember">Most popular</span>}
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{p.desc}</p>
      <div className="mt-6 flex items-end gap-1">
        <span className="font-display text-5xl">{p.price === "—" ? "TBA" : `$${p.price}`}</span>
        {p.price !== "—" && <span className="pb-2 text-sm text-muted-foreground">/mo</span>}
      </div>
      <p className="mt-1 text-sm"><span className="text-ember">{p.credits}</span> <span className="text-muted-foreground">credits · plan details pending</span></p>
      <Link to="/signup" className={cn(btnClass(p.featured ? "glow" : "ghost", "md"), "mt-6 w-full")}>{p.cta}<BorderBeam size={45} duration={7} radius={999} /></Link>
      <ul className="mt-7 space-y-3 text-sm text-muted-foreground">
        {p.features.map((f) => (
          <li key={f} className="flex items-center gap-2.5">
            <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 stroke-ember" fill="none" strokeWidth="2.5"><path d="M5 12l5 5L20 7" /></svg>
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}