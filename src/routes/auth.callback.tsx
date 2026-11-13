import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { fetchIdentity } from "@/lib/auth.functions";
import { finishAuthCallback, readAuthCallback } from "@/lib/auth-callback";
import { betaEnabled } from "@/lib/beta";
import { supabase } from "@/lib/supabase/client";
export const Route = createFileRoute("/auth/callback")({ component: Callback });
function Callback() {
  const started = useRef(false);
  const [note, setNote] = useState("Completing sign in…");
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const { code, flowId, error } = readAuthCallback(window.location.href);
    if (error) {
      setNote(error);
      return;
    }
    if (!code) {
      setNote("This sign-in link is missing its code. Return to sign in.");
      return;
    }
    void supabase.auth
      .exchangeCodeForSession(code, flowId ? { flowId } : undefined)
      .then(async ({ error: exchangeError }) => {
        if (exchangeError) {
          setNote(exchangeError.message);
          return;
        }
        if (betaEnabled()) {
          try {
            if (!(await fetchIdentity())) throw new Error("Uninvited account");
          } catch {
            await supabase.auth.signOut({ scope: "local" });
            setNote("Beta access could not be verified. Use your invited account or retry later.");
            return;
          }
        }
        finishAuthCallback();
      })
      .catch(() => setNote("Sign in could not be completed. Return to sign in and try again."));
  }, []);
  return (
    <div className="p-8">
      <p role="status">{note}</p>
      <Link to="/login" className="text-primary">
        Sign in
      </Link>
    </div>
  );
}
