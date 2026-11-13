// Public build settings only. No owner allowlist, credentials or operator grants.
export const betaEnabled = () => import.meta.env["VITE_NC_BETA_MODE"] === "true";

export function releaseInfo() {
  const candidate = import.meta.env["VITE_NC_BUILD_SHA"] ?? "development";
  return {
    app: "NoetharaClipz",
    build: /^[a-f0-9]{40}$/.test(candidate) ? candidate : "development",
    mode: betaEnabled() ? "owner-scoped-beta" : "application",
  };
}
