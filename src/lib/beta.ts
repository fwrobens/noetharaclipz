// Public build settings only. No owner allowlist, credentials, or operator grants.
// Production builds keep the invite gate on even when Lovable runs a plain
// `vite build` and does not set VITE_NC_BETA_MODE. An explicit false only
// opts out of local dev and tests. A production build never becomes open
// because the variable is missing or set to false.

type GateEnv = {
  PROD?: boolean;
  DEV?: boolean;
  VITE_NC_BETA_MODE?: string;
  VITE_NC_BUILD_SHA?: string;
};

const COMMIT_SHA = /^[a-f0-9]{40}$/;

function currentEnv(env?: GateEnv): GateEnv {
  return env ?? (import.meta.env as GateEnv);
}

export function betaEnabled(env?: GateEnv) {
  const current = currentEnv(env);
  if (current.PROD === true) return true;
  if (current.VITE_NC_BETA_MODE === "true") return true;
  if (current.VITE_NC_BETA_MODE === "false") return false;
  return current.DEV !== true;
}

export function releaseInfo(env?: GateEnv) {
  const current = currentEnv(env);
  const candidate = current.VITE_NC_BUILD_SHA ?? "";
  const enabled = betaEnabled(current);
  return {
    app: "NoetharaClipz",
    build: COMMIT_SHA.test(candidate) ? candidate : current.PROD === true ? "unknown" : "development",
    mode: enabled ? "owner-scoped-beta" : "application",
  };
}
