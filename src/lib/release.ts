import { betaEnabled, releaseInfo } from "./beta";
import { betaAccessIdentity } from "./beta-access.server";

// Public build identity. Callers do not send a session. The document is an
// allowlist: no owner ids, credentials, cookies, or environment values.
export function publicReleaseDocument() {
  const info = releaseInfo();
  if (!betaEnabled()) {
    return {
      app: info.app,
      build: info.build,
      mode: info.mode,
      access: { mode: "inactive" as const },
    };
  }
  const access = betaAccessIdentity();
  return {
    app: info.app,
    build: info.build,
    mode: info.mode,
    access: { mode: access.mode, owners: access.owners, sha256: access.sha256 },
  };
}

export function isReleasePath(request: Request) {
  try {
    const url = new URL(request.url);
    const decoded = decodeURIComponent(url.pathname);
    const path = new URL(decoded, url.origin).pathname.replace(/\/+$/, "") || "/";
    return path === "/api/release";
  } catch {
    return false;
  }
}
