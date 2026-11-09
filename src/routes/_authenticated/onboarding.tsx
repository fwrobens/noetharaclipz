import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Logo, Button } from "@/components/site";
import { cn } from "@/lib/utils";
import { saveOnboarding } from "@/lib/creator.functions";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/_authenticated/onboarding")({
  head: () => pageHead("Get started", "Set up your NoetharaClipZ creator workspace."),
  component: Onboarding,
});

const steps = [
  { t: "What do you create?", s: "Tell us what kind of content you make.", opts: ["Gaming streams", "Podcasts", "Just chatting", "IRL", "Esports", "Education"] },
  { t: "Where's your content?", s: "Pick every source you use.", opts: ["YouTube", "Twitch", "Kick", "Local uploads"] },
  { t: "Which moments matter?", s: "Choose the highlights that interest you most.", opts: ["Funny", "Hype / clutch", "Rage", "Wholesome", "Hot takes", "Fails"] },
];
type Platform = "TikTok" | "YouTube" | "IG Reels";
type Style = "Bold pop" | "Clean" | "Karaoke";

function Onboarding() {
  const navigate = useNavigate();
  const save = useServerFn(saveOnboarding);
  const [step, setStep] = useState(0);
  const [picked, setPicked] = useState<Record<number, string[]>>({});
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState<Platform>("TikTok");
  const [style, setStyle] = useState<Style>("Bold pop");
  const [busy, setBusy] = useState(false);
  const toggle = (option: string) => setPicked(previous => {
    const selected = previous[step] ?? [];
    return {...previous, [step]: selected.includes(option) ? selected.filter(x => x !== option) : [...selected, option]};
  });
  async function next() {
    if (!picked[step]?.length || (step === 0 && !name.trim())) return;
    if (step < steps.length - 1) { setStep(step + 1); return; }
    setBusy(true);
    try {
      await save({ data: { name: name.trim(), platform, style } });
      await navigate({ to: "/dashboard" });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Couldn't save your setup");
    } finally { setBusy(false); }
  }
  const cur = steps[step]!;
  return <div className="clipspark-skin relative min-h-screen overflow-hidden px-5 py-8">
    <div className="grid-bg pointer-events-none absolute inset-0" />
    <div className="ember-orb pointer-events-none absolute left-1/2 top-1/3 h-80 w-[520px] -translate-x-1/2" />
    <div className="relative mx-auto flex max-w-xl items-center justify-between">
      <Logo />
      <span className="text-xs text-muted-foreground">Step {step + 1} of {steps.length}</span>
    </div>
    <div className="relative mx-auto mt-6 flex max-w-xl gap-2">
      {steps.map((_, i) => <span key={i} className={cn("h-1 flex-1 rounded-full transition-all duration-500", i <= step ? "bg-ember" : "bg-muted")} />)}
    </div>
    <main className="relative mx-auto mt-16 max-w-xl">
      <div key={step} className="animate-in-up">
        <h1 className="text-3xl font-medium tracking-tight sm:text-4xl">{cur.t}</h1>
        <p className="mt-2 text-muted-foreground">{cur.s}</p>
        {step === 0 && (
          <label className="mt-8 block text-sm">Creator name
            <input className="mt-2 h-11 w-full rounded-xl border border-input bg-surface px-4 text-sm outline-none focus:border-ember/60" required placeholder="Your name" maxLength={80} value={name} onChange={e => setName(e.target.value)} />
          </label>
        )}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {cur.opts.map(option => {
            const selected = picked[step]?.includes(option);
            return <button type="button" key={option} aria-pressed={Boolean(selected)} onClick={() => toggle(option)} className={cn("rounded-2xl bg-card px-4 py-5 text-left text-sm transition", selected ? "glow-border" : "border border-border hover:bg-accent")}>{option}</button>;
          })}
        </div>
        {step === 1 && <>
          <p className="mt-8 text-sm font-medium">Preferred clip destination</p>
          <div className="mt-3 grid grid-cols-3 gap-2">{(["TikTok","YouTube","IG Reels"] as Platform[]).map(p => (
            <button key={p} aria-pressed={platform === p} onClick={() => setPlatform(p)} className={cn("rounded-xl border px-2 py-3 text-xs",platform === p ? "border-ember bg-accent" : "border-border bg-card")}>{p}</button>
          ))}</div>
        </>}
        {step === 2 && <>
          <p className="mt-8 text-sm font-medium">Your caption style</p>
          <div className="mt-3 grid grid-cols-3 gap-2">{(["Bold pop","Clean","Karaoke"] as Style[]).map(s => (
            <button key={s} aria-pressed={style === s} onClick={() => setStyle(s)} className={cn("rounded-xl border px-2 py-3 text-xs",style === s ? "border-ember bg-accent" : "border-border bg-card")}>{s}</button>
          ))}</div>
        </>}
        <div className="mt-10 flex justify-between gap-3">
          <Button type="button" variant="ghost" onClick={() => setStep(s => Math.max(0,s - 1))} disabled={step === 0 || busy}>Back</Button>
          <Button type="button" disabled={busy || !picked[step]?.length || (step === 0 && !name.trim())} onClick={() => void next()}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {step === steps.length - 1 ? "Open my workspace" : "Continue"} →
          </Button>
        </div>
        <p className="mt-7 text-xs text-muted-foreground">Creator name, clip destination, and caption style are saved to your account. Content preferences are for this setup screen only.</p>
      </div>
    </main>
  </div>;
}
