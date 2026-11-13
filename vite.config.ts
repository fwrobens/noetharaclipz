// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// Never set ssr.external or resolve.external: the Worker has no runtime module resolution, so
// the build fails. Never add compression (compressPublicAssets, vite-plugin-compression):
// hosting already compresses at the edge.
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import { resolveBuildSha } from "./src/lib/resolve-build-sha.ts";

// Lovable's plain `vite build` does not run scripts/build-beta.mjs. Stamp the
// source commit onto VITE_NC_BUILD_SHA before its env define runs, using the
// same commit Lovable later prints as homepage `data-commit-sha` when the
// checkout is available. Tests keep control of the variable via vi.stubEnv.
if (process.env["VITEST"] !== "true") {
  process.env["VITE_NC_BUILD_SHA"] = resolveBuildSha();
}

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
