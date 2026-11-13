import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { requireAuth, useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase/client";
import { betaEnabled } from "@/lib/beta";
import { ProcessingConsentCard } from "@/components/ProcessingConsent";
export const Route = createFileRoute("/settings")({ beforeLoad: requireAuth, component: Settings });
function Settings() {
  const { user } = useAuth();
  const [name, setName] = useState<string | null>(null);
  const current = name ?? user?.user_metadata?.["display_name"] ?? "";
  async function save() {
    const { error } = await supabase.auth.updateUser({ data: { display_name: current } });
    if (error) {
      toast.error(error.message);
      return;
    }
    const { error: profileError } = await supabase
      .from("profiles")
      .upsert({ id: user!.id, display_name: current });
    if (profileError) toast.error(profileError.message);
    else toast.success("Account updated");
  }
  return (
    <div className="max-w-xl p-4 sm:p-8">
      <h1 className="text-2xl font-bold">Account settings</h1>
      <div className="mt-6 space-y-4 rounded-2xl border bg-card p-5 shadow-soft">
        <p className="break-all text-sm text-muted-foreground">{user?.email}</p>
        <label className="block text-sm">
          Display name
          <input
            maxLength={120}
            value={current}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-xl border bg-background p-3"
          />
        </label>
        <button
          onClick={() => void save()}
          className="rounded-xl bg-primary px-4 py-2 text-primary-foreground"
        >
          Save
        </button>
        <button
          onClick={() => void supabase.auth.signOut().then(() => window.location.assign("/"))}
          className="ml-3 rounded-xl border px-4 py-2"
        >
          Sign out
        </button>
      </div>
      {betaEnabled() && <ProcessingConsentCard />}
    </div>
  );
}
