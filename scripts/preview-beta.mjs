// Local production-runtime verification only. No account login or deployment.
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
const config = JSON.parse(await readFile(".output/server/wrangler.json", "utf8"));
if (config.main !== "index.mjs" || config.assets?.directory !== "../public") {
  throw new Error("Unexpected production runtime configuration; review before preview.");
}
const permitted =
  /^(PATH|HOME|TMPDIR|TMP|TEMP|LANG|CI|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy|NODE_EXTRA_CA_CERTS|SSL_CERT_FILE|SSL_CERT_DIR|NODE_USE_ENV_PROXY)$/;
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => permitted.test(key)));
env.WRANGLER_SEND_METRICS = "false";
const child = spawn(
  process.execPath,
  [
    "deploy/beta/preview/node_modules/wrangler/bin/wrangler.js",
    "dev",
    "--local",
    "--config",
    ".output/server/wrangler.json",
    "--ip",
    "127.0.0.1",
    "--port",
    "8081",
  ],
  { env, stdio: "inherit" },
);
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
child.on("error", () => {
  console.error("Install the pinned local runtime with npm run setup:beta-preview.");
  process.exitCode = 1;
});
