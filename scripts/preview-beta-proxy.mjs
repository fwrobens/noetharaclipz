// Local workerd verifier for this managed proxy environment. No deployment.
// outboundService forwards real TLS requests to the existing Supabase project;
// it supplies no identity, fabricated auth response, worker credential or AI call.
import {
  Miniflare,
  convertV4MiniflareOptions,
  Response as MFResponse,
} from "../deploy/beta/preview/node_modules/miniflare/dist/src/index.js";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
const allowedEnv =
  /^(PATH|HOME|TMPDIR|TMP|TEMP|LANG|CI|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy|NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|SSL_CERT_DIR|NODE_USE_ENV_PROXY)$/;
for (const name of Object.keys(process.env)) if (!allowedEnv.test(name)) delete process.env[name];
process.env.WRANGLER_SEND_METRICS = "false";
if ((process.env.HTTPS_PROXY || process.env.HTTP_PROXY) && process.env.NODE_USE_ENV_PROXY !== "1")
  throw new Error("Run this proxy-aware verifier with NODE_USE_ENV_PROXY=1.");
const root = path.resolve(".output/server");
const modules = [];
async function collect(dir) {
  for (const f of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, f.name);
    if (f.isDirectory()) await collect(p);
    else if (/\.m?js$/.test(f.name))
      modules.push({ type: "ESModule", path: p, contents: await readFile(p, "utf8") });
  }
}
await collect(root);
modules.sort((a, b) =>
  a.path === root + "/index.mjs"
    ? -1
    : b.path === root + "/index.mjs"
      ? 1
      : a.path.localeCompare(b.path),
);
const cfg = JSON.parse(await readFile(root + "/wrangler.json", "utf8"));
const mf = new Miniflare(
  convertV4MiniflareOptions({
    name: cfg.name,
    host: "127.0.0.1",
    port: 8082,
    modulesRoot: root,
    modules,
    compatibilityDate: cfg.compatibility_date,
    compatibilityFlags: cfg.compatibility_flags,
    assets: {
      directory: path.resolve(".output/public"),
      binding: "ASSETS",
      routerConfig: { has_user_worker: true },
      run_worker_first: true,
    },
    cf: false,
    telemetry: { enabled: false },
    outboundService: async (req) => {
      const url = new URL(req.url);
      if (url.origin !== "https://zxdnjnsghdnviflahvry.supabase.co")
        return new MFResponse("Local verification transport denied", { status: 403 });
      const init = {
        method: req.method,
        headers: Object.fromEntries(req.headers),
        redirect: "manual",
        signal: AbortSignal.timeout(30000),
      };
      if (!["GET", "HEAD"].includes(req.method)) init.body = await req.arrayBuffer();
      const r = await fetch(url, init);
      const h = new Headers(r.headers);
      h.delete("content-length");
      h.delete("content-encoding");
      return new MFResponse(await r.arrayBuffer(), {
        status: r.status,
        headers: Object.fromEntries(h),
      });
    },
  }),
);
console.log("Proxy-aware workerd verification at " + (await mf.ready));
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, async () => {
    await mf.dispose();
    process.exit(0);
  });
