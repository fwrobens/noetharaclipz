// Prepare the existing Lovable/Cloudflare production artifact. Never deploys it.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, readdir, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { loadEnv } from "vite";

const root = process.cwd();
const source = execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
const dirty = !!execFileSync("git", ["status", "--porcelain"], { encoding: "utf8" }).trim();
if (dirty && !process.argv.includes("--allow-dirty")) {
  throw new Error(
    "Commit source before sealing a beta artifact. --allow-dirty is for local verification only.",
  );
}
const publicNames = new Set([
  "VITE_SUPABASE_URL",
  "VITE_SUPABASE_PUBLISHABLE_KEY",
  "VITE_NC_BETA_MODE",
  "VITE_NC_BUILD_SHA",
]);
const publicEnv = {
  ...loadEnv("beta", root),
  ...Object.fromEntries(Object.entries(process.env).filter(([k]) => k.startsWith("VITE_"))),
};
if (
  Object.keys(publicEnv).some((key) => !publicNames.has(key)) ||
  Object.values(publicEnv).some((value) =>
    /sb_secret_|service_role|-----BEGIN .*PRIVATE KEY/.test(value ?? ""),
  )
) {
  throw new Error("Unreviewed public build configuration; values withheld.");
}
// Preserve inherited proxy/CA trust. Provider, Supabase server, AWS and hosting
// tokens are intentionally absent from the compiler child environment.
const permitted =
  /^(PATH|HOME|TMPDIR|TMP|TEMP|LANG|CI|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy|NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|SSL_CERT_DIR|NODE_USE_ENV_PROXY)$/;
const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => permitted.test(k)));
Object.assign(env, publicEnv, {
  VITE_NC_BETA_MODE: "true",
  VITE_NC_BUILD_SHA: source,
  WRANGLER_SEND_METRICS: "false",
});
execFileSync(process.execPath, ["node_modules/vite/bin/vite.js", "build", "--mode", "beta"], {
  env,
  stdio: "inherit",
});

const files = {};
const secretValues = Object.entries(process.env)
  .filter(
    ([k, v]) =>
      !k.startsWith("VITE_") &&
      /SECRET|TOKEN|PASSWORD|PRIVATE_KEY|SERVICE_ROLE|API_KEY/.test(k) &&
      (v?.length ?? 0) > 15,
  )
  .map(([, v]) => Buffer.from(v));
async function collect(directory) {
  for (const item of await readdir(directory, { withFileTypes: true })) {
    const name = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error("Artifact symlinks require review.");
    if (item.isDirectory()) await collect(name);
    else {
      const raw = await readFile(name);
      if (
        secretValues.some((v) => raw.includes(v)) ||
        /sb_secret_[A-Za-z0-9_-]+|-----BEGIN .*PRIVATE KEY/.test(raw.toString())
      ) {
        throw new Error("A private credential was found in output; do not transfer this artifact.");
      }
      files[name.replaceAll(path.sep, "/")] = createHash("sha256").update(raw).digest("hex");
    }
  }
}
await collect(".output");
const artifactHash = createHash("sha256").update(JSON.stringify(files)).digest("hex");
await mkdir("test-results/beta", { recursive: true });
await writeFile(
  "test-results/beta/build.json",
  JSON.stringify(
    {
      source_commit: source,
      source_dirty: dirty,
      release_eligible: !dirty,
      artifact_sha256: artifactHash,
      target: "existing-lovable-cloudflare",
      files,
      public_config_names: [...publicNames],
      private_credentials_found: false,
      published: false,
    },
    null,
    2,
  ) + "\n",
);
console.log(
  JSON.stringify({
    source_commit: source,
    source_dirty: dirty,
    artifact_sha256: artifactHash,
    published: false,
  }),
);
