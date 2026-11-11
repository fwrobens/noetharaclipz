import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  consentActive,
  readProcessingConsent,
  requestProcessingConsent,
  withdrawProcessingConsent,
} from "@/lib/processing-consent";
import { useAuth } from "@/lib/auth";

export function ProcessingConsentCard() {
  const { user } = useAuth();
  const requestId = useRef(crypto.randomUUID());
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["processing-consent", user?.id],
    queryFn: readProcessingConsent,
    enabled: !!user,
    refetchInterval: 30000,
  });
  const consent = query.data ?? null;
  const active = consentActive(consent);
  const pending = !!consent && !consent.approved_at && !consent.revoked_at;

  async function act(withdraw: boolean) {
    setBusy(true);
    setError("");
    try {
      if (withdraw && consent) await withdrawProcessingConsent(consent.consent_id);
      else await requestProcessingConsent(requestId.current, checked);
      await query.refetch();
      setChecked(false);
      requestId.current = crypto.randomUUID();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Processing permission could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 space-y-4 rounded-2xl border bg-card p-5 shadow-soft">
      <h2 className="text-lg font-semibold">Local AI processing</h2>
      <p className="text-sm text-muted-foreground">
        This beta needs your consent and a separate operator approval. Only new projects created
        during your approved window can be processed. Saved projects remain private after it ends.
      </p>
      <p role="status" className="text-sm">
        {query.isPending
          ? "Checking processing permission…"
          : query.isError
            ? "Processing permission is unavailable."
            : active
              ? `Processing approved until ${new Date(consent!.expires_at!).toUTCString()}.`
              : pending
                ? "Your request is awaiting operator approval."
                : "Processing is not currently approved."}
      </p>
      {!active && !pending && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
          I consent to local AI processing of the videos I choose to upload. I can withdraw this
          permission at any time.
        </label>
      )}
      {!active && !pending && (
        <button
          disabled={!checked || busy || query.isPending || query.isError}
          onClick={() => void act(false)}
          className="rounded-xl bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50"
        >
          {busy ? "Saving…" : "Request processing approval"}
        </button>
      )}
      {consent && !consent.revoked_at && (
        <button
          disabled={busy || query.isError}
          onClick={() => void act(true)}
          className="rounded-xl border px-4 py-2 text-sm"
        >
          Withdraw processing permission
        </button>
      )}
      {query.isError && (
        <button onClick={() => void query.refetch()} className="text-sm text-primary">
          Retry
        </button>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
