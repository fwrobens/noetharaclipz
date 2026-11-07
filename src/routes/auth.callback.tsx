import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/lib/supabase/client";
export const Route = createFileRoute("/auth/callback")({ component: Callback });
function Callback() {
  const started = useRef(false);
  const [note, setNote] = useState("Completing sign in…");
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const params = new URL(window.location.href).searchParams;
    const code = params.get("code");
    const flowId = params.get("sb_flow_id");
    if (!code) {
      setNote("This sign-in link is missing its code. Return to sign in.");
      return;
    }
    void supabase.auth
      .exchangeCodeForSession(code, flowId ? { flowId } : undefined)
      .then(({ error }) => {
        if (error) setNote(error.message);
        else window.location.replace("/library");
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
