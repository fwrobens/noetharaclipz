import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase/client";
export const Route = createFileRoute("/auth/callback")({ component: Callback });
function Callback() {
  const [note, setNote] = useState("Completing sign in…");
  useEffect(() => {
    const code = new URL(window.location.href).searchParams.get("code");
    if (!code) {
      setNote("This sign-in link is missing its code. Return to sign in.");
      return;
    }
    void supabase.auth.exchangeCodeForSession(code).then(({ error }) => {
      if (error) setNote(error.message);
      else window.location.replace("/library");
    });
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
