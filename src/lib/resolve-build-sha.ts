import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const SHA = /^[0-9a-f]{40}$/;

// Lovable writes this same source commit onto the homepage as
// `data-commit-sha` on its injected `/__l5e/events` script. Resolving HEAD
// here keeps `/api/release` on that commit when the build can see the checkout.
export function resolveBuildSha(root = process.cwd()) {
  return gitRevParse(root) ?? readGitFiles(root) ?? envSha() ?? "unknown";
}

function gitRevParse(root: string) {
  try {
    const sha = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: root,
      encoding: "utf8",
      timeout: 5000,
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return SHA.test(sha) ? sha : null;
  } catch {
    return null;
  }
}

function readGitFiles(root: string) {
  const gitDir = resolveGitDir(root);
  if (!gitDir) return null;
  let head: string;
  try {
    head = readFileSync(path.join(gitDir, "HEAD"), "utf8").trim();
  } catch {
    return null;
  }
  if (SHA.test(head)) return head;
  const ref = head.startsWith("ref: ") ? head.slice(5).trim() : "";
  if (!ref) return null;
  try {
    const direct = readFileSync(path.join(gitDir, ref), "utf8").trim();
    if (SHA.test(direct)) return direct;
  } catch {
    // Packed refs are the fallback when the loose ref file is absent.
  }
  try {
    const packed = readFileSync(path.join(gitDir, "packed-refs"), "utf8");
    for (const line of packed.split("\n")) {
      if (!line || line.startsWith("#") || line.startsWith("^")) continue;
      const [sha, name] = line.split(" ");
      if (name === ref && sha && SHA.test(sha)) return sha;
    }
  } catch {
    return null;
  }
  return null;
}

function resolveGitDir(root: string) {
  const gitPath = path.join(root, ".git");
  if (!existsSync(gitPath)) return null;
  try {
    if (statSync(gitPath).isDirectory()) return gitPath;
    const pointer = readFileSync(gitPath, "utf8");
    const match = pointer.match(/^gitdir:\s*(.+)\s*$/m);
    if (!match?.[1]) return null;
    return path.resolve(root, match[1]);
  } catch {
    return null;
  }
}

function envSha() {
  for (const key of ["VITE_NC_BUILD_SHA", "GITHUB_SHA", "CF_PAGES_COMMIT_SHA", "COMMIT_REF"]) {
    const value = process.env[key]?.trim();
    if (value && SHA.test(value)) return value;
  }
  return null;
}
