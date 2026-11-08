import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { Brand } from "@/components/Brand";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { pageHead } from "@/lib/seo";
export const Route = createFileRoute("/reset-password")({ head: () => pageHead("Reset password", "Set a new password for your creator account."), component: ResetPassword });
function ResetPassword() {
  const [recovery, setRecovery] = useState(false);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setRecovery(new URLSearchParams(window.location.hash.slice(1)).get("type") === "recovery"); }, []);
  const submit = async (e: FormEvent) => { e.preventDefault();setBusy(true); const { error } = await supabase.auth.updateUser({ password });setBusy(false);setMessage(error ? error.message : "Password updated. You can sign in now."); };
  return <div className="min-h-screen p-6"><Brand /><main className="mx-auto max-w-sm py-24"><h1 className="text-3xl">Reset your password.</h1>{recovery ? <form className="mt-8 space-y-4" onSubmit={submit}><label className="block text-sm">New password<input type="password" minLength={8} required value={password} onChange={e => setPassword(e.target.value)} className="form-input mt-2" autoComplete="new-password" /></label><Button disabled={busy} className="w-full">Save password</Button></form> : <p className="mt-6 text-muted-foreground">Open the password reset link from your email to continue.</p>}{message && <p role="status" className="mt-4 text-sm">{message}</p>}<Button asChild variant="link" className="mt-6"><Link to="/auth">Back to sign in</Link></Button></main></div>;
}