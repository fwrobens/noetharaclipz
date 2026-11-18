#!/usr/bin/env node
// Disposable in-process PostgreSQL (PGlite) regression for docs/model-runs-schema.sql.
// Never contacts hosted Supabase. PGlite is not a project dependency; install it
// temporarily, e.g. `npm install --no-save @electric-sql/pglite`, or point
// PGLITE_DIR at a directory whose node_modules contains it.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
let PGlite;
try {
  const base = process.env.PGLITE_DIR
    ? join(process.env.PGLITE_DIR, "package.json")
    : import.meta.url;
  ({ PGlite } = createRequire(base)("@electric-sql/pglite"));
} catch {
  console.error("@electric-sql/pglite is not installed; see header of this script.");
  process.exit(2);
}

const test = readFileSync(join(root, "worker/tests/sql/model_runs.sql"), "utf8");
const proposal = readFileSync(join(root, "docs/model-runs-schema.sql"), "utf8");
const sql = test.replace(
  "-- >>> proposal (inserted by the runner from docs/model-runs-schema.sql)",
  () => "-- >>> proposal\n" + proposal, // function form: "$$" must not be expanded
);
if (sql === test) throw new Error("Proposal marker missing");

const passes = [];
const db = new PGlite();
try {
  await db.exec(sql, {
    onNotice: (n) => n.message.startsWith("PASS:") && passes.push(n.message),
  });
} catch (error) {
  console.error(passes.join("\n"));
  console.error("SQL regression failed:", error.message);
  process.exit(1);
}
const expected = (test.match(/^select public\.nc_(assert|rejects)\(/gm) || []).length;
console.log(passes.join("\n"));
console.log(
  JSON.stringify({
    passed: passes.length === expected,
    assertions: passes.length,
    expected,
    hosted_database_changed: false,
  }),
);
process.exit(passes.length === expected ? 0 : 1);
