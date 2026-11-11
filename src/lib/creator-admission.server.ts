import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/integrations/supabase/types";
import { betaEnabled } from "./beta";
import { consentActive, parseConsent } from "./consent-policy";

// Protocol v2 is already deployed. Keep its narrow runtime adapter separate
// from generated database types; every call still carries the owner's session.
export async function requireCreatorAdmission(supabase: SupabaseClient<Database>, owner: string) {
  if (!betaEnabled()) return;
  const rpc = supabase as unknown as {
    rpc(name: "processing_consent" | "pipeline_health"): Promise<{
      data: unknown;
      error: { message: string } | null;
    }>;
  };
  const result = await rpc.rpc("processing_consent");
  if (result.error) throw new Error("Processing permission could not be verified. Please retry.");
  const consent = parseConsent(result.data);
  if (consent?.owner_id !== owner || !consentActive(consent)) {
    throw new Error(
      "Local processing requires your consent and an active beta approval. Check Account settings.",
    );
  }
  const readiness = await rpc.rpc("pipeline_health");
  const health = readiness.data as { online?: boolean; ai_ready?: boolean } | null;
  if (readiness.error || health?.online !== true || health.ai_ready !== true) {
    throw new Error(
      "Local processing is temporarily unavailable. Please try again when your worker is ready.",
    );
  }
}
