import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase/client";
import { publishableKey, supabaseUrl } from "@/lib/supabase/config";
import { betaEnabled } from "@/lib/beta";
export const Route = createFileRoute("/login")({
  component: Login,
  head: () => ({ meta: [{ title: "Sign in — Clipwave" }] }),
});
function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [google, setGoogle] = useState(false);
  useEffect(() => {
    fetch(supabaseUrl + "/auth/v1/settings", { headers: { apikey: publishableKey } })
      .then((r) => r.json())
      .then((s) => setGoogle(s.external?.google === true))
      .catch(() => {});
  }, []);
  async function submit() {
    setBusy(true);
    setNote("");
    try {
      const result = signup
        ? await supabase.auth.signUp({
            email,
            password,
            options: { emailRedirectTo: window.location.origin + "/auth/callback" },
          })
        : await supabase.auth.signInWithPassword({ email, password });
      if (result.error) throw result.error;
      if (!result.data.session) setNote("Check your email to confirm your account, then sign in.");
      else await nav({ to: "/library" });
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="mx-auto max-w-md p-6 pt-16 animate-fade-up">
      <h1 className="text-3xl font-bold">{signup ? "Create your account" : "Welcome back"}</h1>
      <p className="mt-2 text-sm text-muted-foreground">Your videos and clips stay private.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        className="mt-6 space-y-4 rounded-3xl border bg-card p-6 shadow-float"
      >
        <label className="block text-sm">
          Email
          <input
            required
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-xl border bg-background p-3"
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            required
            type="password"
            minLength={8}
            autoComplete={signup ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-xl border bg-background p-3"
          />
        </label>
        {note && (
          <p role="status" className="text-sm">
            {note}
          </p>
        )}
        <button
          disabled={busy}
          className="w-full rounded-xl bg-primary p-3 text-primary-foreground shadow-pop disabled:opacity-50"
        >
          {busy ? "Please wait…" : signup ? "Create account" : "Sign in"}
        </button>
        {google && !betaEnabled() && (
          <button
            type="button"
            onClick={() =>
              void supabase.auth.signInWithOAuth({
                provider: "google",
                options: { redirectTo: window.location.origin + "/auth/callback" },
              })
            }
            className="w-full rounded-xl border p-3"
          >
            Continue with Google
          </button>
        )}
        {!betaEnabled() && (
          <button
            type="button"
            onClick={() => setSignup(!signup)}
            className="w-full text-sm text-primary"
          >
            {signup ? "Already have an account? Sign in" : "Create an account"}
          </button>
        )}
        {betaEnabled() && (
          <p className="text-sm text-muted-foreground">
            Beta access is by invitation. Sign in with your approved account.
          </p>
        )}
        <Link to="/" className="block text-center text-sm text-muted-foreground">
          Back home
        </Link>
      </form>
    </div>
  );
}
