// Shared invite list. Knowing an id grants nothing by itself: the server still
// requires a GoTrue-validated session, and storage signing requires one too.
const OWNER_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const betaAccessPolicy = {
  version: 1,
  owners: [
    "21b61ad1-bda4-4abd-ac35-7a0bf477ed69",
    "f0235878-e130-45a9-a031-f21cd91da7b9",
  ],
  confirmed_email_required: true,
  anonymous_allowed: false,
  routing: "private-by-default-including-server-functions-v1",
} as const;

export type BetaUser = {
  id: string;
  role?: string;
  is_anonymous?: boolean;
  email_confirmed_at?: string | null;
};

// null means the list is missing, empty, or malformed. Callers must deny.
export function readBetaAllowlist(policy: unknown = betaAccessPolicy): string[] | null {
  if (!policy || typeof policy !== "object") return null;
  const owners = (policy as { owners?: unknown }).owners;
  if (!Array.isArray(owners) || owners.length === 0) return null;
  const ids: string[] = [];
  for (const owner of owners) {
    if (typeof owner !== "string" || !OWNER_ID.test(owner)) return null;
    ids.push(owner);
  }
  return ids;
}

export function betaOwnerAllowed(user: BetaUser | null, policy: unknown = betaAccessPolicy) {
  const owners = readBetaAllowlist(policy);
  if (!owners || !user) return false;
  return (
    user.role === "authenticated" &&
    user.is_anonymous !== true &&
    !!user.email_confirmed_at &&
    owners.includes(user.id)
  );
}
