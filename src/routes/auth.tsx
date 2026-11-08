import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { ArrowRight, Eye, EyeOff, Loader2, ArrowLeft } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { Brand } from "@/components/Brand";
import { Button } from "@/components/ui/button";
import { pageHead } from "@/lib/seo";
import studio from "@/assets/creator-studio.jpg";

export const Route = createFileRoute("/auth")({ head: () => pageHead("Sign in", "Sign in or create your Noethara Clipz creator account."), component: Auth });
function Auth() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup" | "forgot">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      if (mode === "forgot") {
        const result = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/reset-password` });
        if (result.error) throw result.error;
        setNotice("If an account exists, a reset link is on its way. Check your email.");
      } else if (mode === "signup") {
        const result = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/auth` } });
        if (result.error) throw result.error;
        if (result.data.session) await navigate({ to: "/onboarding" });
        else setNotice("Check your email to confirm your account, then sign in here.");
      } else {
        const result = await supabase.auth.signInWithPassword({ email, password });
        if (result.error) throw result.error;
        await navigate({ to: "/dashboard" });
      }
    } catch(e) { setError(e instanceof Error ? e.message : "Something went wrong. Try again."); }
    finally { setBusy(false); }
  };
  return <div className="grid min-h-screen lg:grid-cols-2"><div className="flex flex-col px-6 py-7 sm:px-12"><Brand /><main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-16">
    <p className="mb-4 text-xs font-medium text-primary">YOUR NEXT GREAT CLIP STARTS HERE</p>
    <h1 className="text-3xl font-medium">{mode === "signin" ? "Welcome back." : mode === "signup" ? "Create something great." : "A fresh start."}</h1>
    <p className="mt-3 text-sm text-muted-foreground">{mode === "signin" ? "Sign in to your creator workspace." : mode === "signup" ? "Your content. A whole new possibility." : "We'll email you a password reset link."}</p>
    <form onSubmit={submit} className="mt-8 space-y-5"><label className="block text-sm">Email address<input className="form-input mt-2" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required /></label>
    {mode !== "forgot" && <label className="block text-sm">Password<div className="relative mt-2"><input className="form-input pr-12" type={show ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)} minLength={8} autoComplete={mode === "signin" ? "current-password" : "new-password"} placeholder="At least 8 characters" required /><Button type="button" variant="ghost" size="icon" className="absolute right-1 top-1" aria-label={show ? "Hide password" : "Show password"} onClick={() => setShow(!show)}>{show ? <EyeOff /> : <Eye />}</Button></div></label>}
    {mode === "signin" && <Button type="button" variant="link" className="h-auto p-0 text-xs" onClick={() => {setMode("forgot");setError("");}}>Forgot password?</Button>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}{notice && <p role="status" className="text-sm text-success">{notice}</p>}
    <Button disabled={busy} className="h-11 w-full" type="submit">{busy ? <Loader2 className="animate-spin" /> : <ArrowRight />}{mode === "signin" ? "Sign in" : mode === "signup" ? "Create account" : "Send reset link"}</Button></form>
    <div className="mt-6 text-center text-sm text-muted-foreground">{mode === "signin" ? "New to Noethara? " : "Already have an account? "}<Button variant="link" className="h-auto p-0" onClick={() => {setMode(mode === "signin" ? "signup" : "signin");setError("");setNotice("");}}>{mode === "signin" ? "Create an account" : "Sign in"}</Button></div>
    <Link to="/" className="mt-10 flex items-center justify-center gap-2 text-xs text-muted-foreground"><ArrowLeft className="h-3 w-3" /> Back to Noethara Clipz</Link>
  </main><p className="text-xs text-muted-foreground">© {new Date().getFullYear()} Noethara Clipz</p></div>
  <aside className="relative hidden overflow-hidden border-l lg:block"><img src={studio} width={1920} height={1024} alt="Creator recording in a studio" className="absolute inset-0 h-full w-full object-cover object-right" /><div className="auth-shade absolute inset-0" /><div className="absolute bottom-16 left-12 right-12"><p className="mb-4 text-xs text-primary">LESS EDITING. MORE CREATING.</p><h2 className="max-w-sm text-4xl font-medium leading-tight text-cover-foreground">Your best moments<br />deserve an audience.</h2><p className="mt-4 max-w-sm text-sm text-cover-muted">From the full story to the moment that matters.</p></div></aside></div>;
}