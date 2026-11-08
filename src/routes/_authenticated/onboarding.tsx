import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { ArrowRight, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Brand } from "@/components/Brand";
import { Button } from "@/components/ui/button";
import { saveOnboarding } from "@/lib/creator.functions";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/_authenticated/onboarding")({ head: () => pageHead("Your creator setup", "Personalize your platform and caption style."), component: Onboarding });
function Onboarding() {
  const navigate = useNavigate();
  const save = useServerFn(saveOnboarding);
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState<"TikTok" | "YouTube" | "IG Reels">("TikTok");
  const [style, setStyle] = useState<"Bold pop" | "Clean" | "Karaoke">("Bold pop");
  const [busy, setBusy] = useState(false);
  const next = async () => {
    if (!name.trim()) return;
    if (step < 2) { setStep(step + 1); return; }
    setBusy(true);
    try { await save({ data: { name, platform, style } }); await navigate({ to: "/dashboard" }); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Couldn't save your setup"); }
    finally { setBusy(false); }
  };
  return <div className="min-h-screen bg-background px-5 py-7"><Brand /><main className="mx-auto max-w-lg py-16 sm:py-24">
    <div className="mb-10 flex gap-2">{[0,1,2].map(n => <div key={n} className={`h-1 flex-1 rounded-full ${n <= step ? "bg-primary" : "bg-muted"}`} />)}</div>
    <p className="mb-3 text-xs text-primary">YOUR WORKSPACE · {step + 1} / 3</p>
    <h1 className="text-3xl font-medium">{["Make it yours.", "Where do you create?", "Find your signature style."][step]}</h1>
    <p className="mt-3 text-muted-foreground">{["First, what should we call you?", "Choose the destination for your next great clip.", "Pick a caption look. You can change it anytime."][step]}</p>
    <div className="my-9 space-y-3">{step === 0 ? <label className="block text-sm">Creator name<input autoFocus value={name} onChange={e => setName(e.target.value)} maxLength={80} className="form-input mt-2" placeholder="Your name" /></label> : step === 1 ? (["TikTok", "YouTube", "IG Reels"] as const).map(p => <Button key={p} variant="outline" onClick={() => setPlatform(p)} className={`h-16 w-full justify-between ${p === platform ? "border-primary bg-accent" : ""}`}>{p}{p === platform && <Check />}</Button>) : (["Bold pop", "Clean", "Karaoke"] as const).map(s => <Button key={s} variant="outline" onClick={() => setStyle(s)} className={`h-20 w-full justify-between ${s === style ? "border-primary bg-accent" : ""}`}><span className={s === "Bold pop" ? "font-bold text-xl" : "text-lg"}>{s}</span>{s === style && <Check />}</Button>)}</div>
    <div className="flex justify-between">{step > 0 ? <Button variant="ghost" onClick={() => setStep(step - 1)}>Back</Button> : <span />}<Button disabled={!name.trim() || busy} onClick={next}>{busy ? <Loader2 className="animate-spin" /> : <ArrowRight />}{step === 2 ? "Open my workspace" : "Continue"}</Button></div>
  </main></div>;
}