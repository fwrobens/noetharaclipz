import { useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { supabase } from "@/lib/supabase/client";
import { AuthShell, Field } from "@/components/auth-shell";
import { Button } from "@/components/site";
import { Loader2 } from "lucide-react";
import { authCallbackUrl } from "@/lib/auth-callback";
import { betaEnabled } from "@/lib/beta";
import { fetchIdentity } from "@/lib/auth.functions";

type Mode = "signin" | "signup" | "forgot";

export function ClipSparkAuth({ initialMode = "signin" }: { initialMode?: "signin" | "signup" }) {
  const navigate = useNavigate();
  const beta = betaEnabled();
  const [mode, setMode] = useState<Mode>(beta ? "signin" : initialMode);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [oauthBusy, setOauthBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const change = (m: Mode) => {
    setMode(m);
    setError("");
    setNotice("");
    setPassword("");
  };
  const onOAuth = async (provider: "google" | "twitch") => {
    setError("");
    setOauthBusy(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: authCallbackUrl(window.location.origin) },
      });
      if (error) throw error;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to connect this account.");
      setOauthBusy(false);
    }
  };
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (mode === "forgot") {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + "/reset-password",
        });
        if (error) throw error;
        setNotice("If an account exists, check your email for a password reset link.");
      } else if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: authCallbackUrl(window.location.origin),
            data: { name: name.trim() },
          },
        });
        if (error) throw error;
        if (data.session) await navigate({ to: "/onboarding" });
        else setNotice("Check your email to confirm your account, then sign in.");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        if (beta) {
          try {
            if (!(await fetchIdentity())) throw new Error("Uninvited account");
          } catch {
            await supabase.auth.signOut({ scope: "local" });
            throw new Error(
              "Beta access could not be verified. Use your invited account or retry later.",
            );
          }
        }
        await navigate({ to: "/dashboard" });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthShell
      title={
        mode === "signin"
          ? "Welcome back"
          : mode === "signup"
            ? "Create your account"
            : "Reset your password"
      }
      subtitle={
        beta
          ? "Log in with your invited beta account."
          : mode === "signin"
            ? "Log in to keep clipping."
            : mode === "signup"
              ? "Start creating with NoetharaClipZ."
              : "We'll send a password reset link."
      }
      {...(beta ? {} : { onOAuth })}
      oauthBusy={oauthBusy || busy}
      footer={
        beta ? (
          <>This beta is invitation only.</>
        ) : mode === "signin" ? (
          <>
            New here?{" "}
            <button
              type="button"
              onClick={() => change("signup")}
              className="text-foreground underline-offset-4 hover:underline"
            >
              Create an account
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              type="button"
              onClick={() => change("signin")}
              className="text-foreground underline-offset-4 hover:underline"
            >
              Log in
            </button>
          </>
        )
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {mode === "signup" && (
          <Field
            label="Name"
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={80}
            autoComplete="name"
          />
        )}
        <Field
          label="Email"
          type="email"
          placeholder="you@channel.com"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        {mode !== "forgot" && (
          <Field
            label="Password"
            type="password"
            placeholder="At least 8 characters"
            required
            minLength={mode === "signup" ? 8 : undefined}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
        {!beta && mode === "signin" && (
          <div className="text-right text-xs">
            <button
              type="button"
              onClick={() => change("forgot")}
              className="text-muted-foreground hover:text-foreground"
            >
              Forgot password?
            </button>
          </div>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="text-sm text-foreground">
            {notice}
          </p>
        )}
        <Button className="w-full" type="submit" disabled={busy || oauthBusy}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {mode === "signin" ? "Log in" : mode === "signup" ? "Create account" : "Send reset link"}
        </Button>
        {mode === "signup" && (
          <p className="text-center text-xs text-muted-foreground">
            By signing up you agree to the Terms and Privacy Policy.
          </p>
        )}
      </form>
    </AuthShell>
  );
}
