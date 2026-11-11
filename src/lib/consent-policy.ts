export type ProcessingConsent = {
  owner_id: string;
  consent_id: string;
  approved_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
};

const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;

export function parseConsent(value: unknown): ProcessingConsent | null {
  if (value === null) return null;
  if (typeof value !== "object" || !value) throw new Error("Processing consent is unavailable.");
  const row = value as Record<string, unknown>;
  if (
    typeof row["owner_id"] !== "string" ||
    !uuid.test(row["owner_id"]) ||
    typeof row["consent_id"] !== "string" ||
    !uuid.test(row["consent_id"]) ||
    !["approved_at", "expires_at", "revoked_at"].every(
      (key) =>
        row[key] === null ||
        (typeof row[key] === "string" && Number.isFinite(Date.parse(row[key]))),
    )
  ) {
    throw new Error("Processing consent is unavailable.");
  }
  return row as ProcessingConsent;
}

export function consentActive(consent: ProcessingConsent | null, now = Date.now()) {
  return (
    !!consent?.approved_at &&
    Date.parse(consent.approved_at) <= now &&
    !consent.revoked_at &&
    !!consent.expires_at &&
    Date.parse(consent.expires_at) > now
  );
}
