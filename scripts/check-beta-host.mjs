// Read-only publication gate; no login, consent, uploads, jobs or notification.
const [origin, expectedBuild] = process.argv.slice(2);
const url = new URL(origin);
if (
  url.protocol !== "https:" ||
  url.pathname !== "/" ||
  url.username ||
  url.password ||
  url.search ||
  url.hash ||
  !/^[a-f0-9]{40}$/.test(expectedBuild ?? "")
) {
  throw new Error("Supply the reviewed HTTPS origin and exact 40-character build commit.");
}
async function get(route) {
  return fetch(new URL(route, url), {
    redirect: "manual",
    signal: AbortSignal.timeout(15000),
    cache: "no-store",
  });
}
const release = await get("/api/release");
if (!release.ok || !release.headers.get("content-type")?.includes("application/json"))
  throw new Error("Hosted beta release is unavailable.");
const info = await release.json();
if (
  info.app !== "NoetharaClipz" ||
  info.build !== expectedBuild ||
  info.mode !== "owner-scoped-beta" ||
  !release.headers.get("cache-control")?.includes("no-store")
)
  throw new Error("Hosted release differs from reviewed beta.");
const login = await get("/login");
if (!login.ok || !login.headers.get("x-robots-tag")?.includes("noindex"))
  throw new Error("Beta login route or indexing protection failed.");
const callback = await get("/auth/callback");
if (![200, 302, 303, 307].includes(callback.status))
  throw new Error("Auth callback route is unavailable.");
console.log(
  JSON.stringify({
    origin: url.origin,
    build: expectedBuild,
    release_verified: true,
    login: login.status,
    callback: callback.status,
    authenticated_acceptance_pending: true,
    published: false,
  }),
);
