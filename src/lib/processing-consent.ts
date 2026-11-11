import { supabase } from "./supabase/client";
import { publishableKey, supabaseUrl } from "./supabase/config";

import { consentActive, parseConsent } from "./consent-policy";
export { consentActive, parseConsent, type ProcessingConsent } from "./consent-policy";
const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;

// These owner-only RPCs already exist in deployed protocol v2. Do not edit the
// generated DB types or expose an operator/service-role RPC to the browser.
async function ownerRpc(
  name:
    | "processing_consent"
    | "request_processing_consent"
    | "revoke_processing_consent"
    | "pipeline_health",
  body: Record<string, string> = {},
) {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) throw new Error("Sign in to manage processing permission.");
  const response = await fetch(`${supabaseUrl}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: publishableKey,
      Authorization: `Bearer ${data.session.access_token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Processing permission could not be verified. Please retry.");
  return response.json() as Promise<unknown>;
}

export async function readProcessingConsent() {
  return parseConsent(await ownerRpc("processing_consent"));
}

export async function requestProcessingConsent(requestId: string, explicitConsent: boolean) {
  if (!explicitConsent || !uuid.test(requestId))
    throw new Error("Confirm your processing consent first.");
  return parseConsent(
    await ownerRpc("request_processing_consent", {
      request_id: requestId,
      terms_version: "local-video-v1",
    }),
  );
}

export async function withdrawProcessingConsent(consentId: string) {
  if (!uuid.test(consentId)) throw new Error("A current consent request is required.");
  if ((await ownerRpc("revoke_processing_consent", { consent: consentId })) !== true) {
    throw new Error("Processing permission could not be withdrawn. Please retry.");
  }
}

export async function requireBetaAdmission() {
  const consent = await readProcessingConsent();
  if (!consentActive(consent)) {
    throw new Error(
      "Local processing requires your consent and an active beta approval. Check Account settings.",
    );
  }
  const health = (await ownerRpc("pipeline_health")) as {
    online?: boolean;
    ai_ready?: boolean;
  } | null;
  if (!health || health.online !== true || health.ai_ready !== true) {
    throw new Error(
      "Local processing is temporarily unavailable. Please try again when your worker is ready.",
    );
  }
}
