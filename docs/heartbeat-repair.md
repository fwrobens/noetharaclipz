# Scoped worker-heartbeat repair — 2026-11-07

**Prepared and locally verified; not applied to hosted Supabase.** The user
explicitly authorized an exception to `AGENTS.md` for this one repair. That
authorization is sufficient. The remaining blocker is the absence of Supabase
SQL tools in this chat, not a requirement to use Lovable or obtain approval.

## Narrow migration

`supabase/migrations/20261107201038_worker_heartbeat_singleton.sql` replaces only
`private.worker_heartbeat(boolean,text)`, adding `WHERE id = true` to its update.
It retains `private.require_worker()`, the same parameter names/return type,
PL/pgSQL, `SECURITY DEFINER` and empty `search_path`. `CREATE OR REPLACE` preserves
the existing function identity, ownership and grants. It makes no changes to
the public wrapper, tables, RLS, queue, role permissions or other functions.
All six earlier migration files are byte-for-byte unchanged from the PR head.

The repository definition at `b6c69bb` confirms the update has no predicate. A
fresh request using the real authorized server credential still returns HTTP
400, database code `21000`, `UPDATE requires a WHERE clause`. This is evidence
of the live failure, not a claim that the live function's catalog definition or
metadata has been inspected. Those catalog reads still require SQL access.

## Verification completed

- The isolated PostgreSQL 17.11 regression test reproduces the original update
  addressing both local fixture rows. Applying the new migration twice then
  updates only `id=true`; the local `id=false` sentinel stays untouched. The
  hosted table's singleton constraint is not changed.
- The test verifies unchanged OID, owner, ACL, signature, return type, definer
  flag, search path, language, strictness, volatility, parallel setting, cost,
  row estimate and function comment.
- Worker-role invocation and the 300-character detail limit pass locally. An
  invalid JWT-role assertion is rejected even when the SQL role has EXECUTE.
  Anonymous and authenticated browser roles cannot invoke the function.
- Real HTTP negative tests pass for `worker_heartbeat`, `worker_claim` and
  `worker_tick`: anonymous callers receive 401 and authenticated QA callers
  receive 403. The temporary QA account is deleted.
- The live authorized heartbeat test still fails until deployment. Its script
  exits 1 and records `online: null`, `ai_ready: false`; it does not override
  health or enable Gemini inference to pass.
- All six live queue-control checks passed again in 125.34 seconds, including
  actual lease expiry/reclaim, stale-token rejection, concurrency, cancellation
  and retry. This is a baseline recheck, not post-deployment evidence. The
  backend/recovery Python subset also passed all 12 tests.

Sanitized results are committed in
[`evidence/heartbeat-repair.json`](evidence/heartbeat-repair.json).

The local PostgreSQL container has no network access or published ports, uses
only disposable fixture data and is removed after the test. Its successful
result is not represented as a hosted repair.

Commands and reusable checks:

```sh
cd /workspace/noetharaclipz
worker/.venv/bin/python scripts/test_heartbeat_migration.py
worker/.venv/bin/python scripts/check_worker_heartbeat.py
NC_SAMPLE_VIDEO=/path/to/authorized/sintel.mp4 worker/.venv/bin/python scripts/check_live_queue.py
```

The first command uses the local managed Docker socket and a digest-pinned
official PostgreSQL image. The second and third use the existing bound server
credential, create only scoped temporary QA data and never run hosted inference.
The third requires an otherwise idle queue and waits for its actual 120-second
visibility/lease expiry. Existing backend/recovery Python tests were also rerun.

## Access and drift checks

- GitHub CLI authentication works. PR #1 remains open and draft; its starting
  head was `b6c69bb1b1845ebfb5585e4da32778f124c423f9`. `main` remains at
  `d81aa69edf2e5f81faf7c6fea7cd2b9d135bfeb5` and contains no `supabase/` directory.
  Backend migrations are intentionally still on the unmerged feature branch.
- `supabase/config.toml` identifies only project `zxdnjnsghdnviflahvry`. Runtime
  credential validation also refuses any other project URL.
- No Supabase or Lovable plugin tool is exposed in this chat. In particular,
  neither SQL execution nor migration application is callable. The Supabase CLI
  independently reports no administrative access token. No management token or
  database connection credential is bound; the existing app service-role key
  is not an administrative SQL connection.
- The public Lovable site was checked separately. Its reachability does not
  expose the editor's configuration, Git synchronization state or deployment
  commit. Those drift checks remain unverified without the Lovable integration.
- The live migration ledger and function/permission metadata cannot currently
  be compared to GitHub. The new migration is therefore **pending**, not marked
  applied. No migration history has been repaired or fabricated.

## Complete once Supabase SQL tools are available

Use the connected plugin with **project ID `zxdnjnsghdnviflahvry`** throughout:

1. Read the project identity and execute the read-only
   `supabase/tests/inspect_worker_heartbeat.sql`. Retain the function definition,
   owner, grants, execution settings, health-table security metadata and migration
   ledger. Confirm the live function matches the expected unbounded definition;
   investigate any difference before replacing it.
2. Apply the new migration through the supported migration capability so the
   function change and versioned ledger stay consistent. If using a raw SQL
   execution tool, first establish its supported migration-recording workflow;
   do not insert an invented ledger record or silently leave drift.
3. Repeat the inspection and compare all metadata before/after. The only
   function-definition change must be the singleton predicate. Verify the live
   migration version agrees with the committed filename.
4. Execute transactional `supabase/tests/worker_heartbeat.sql`, then run the real
   credential-backed heartbeat and queue-recovery scripts above. The heartbeat
   script must return 0 with `online=true`, and browser calls must remain denied.
5. Finish the Lovable project/configuration drift check without generating UI
   or consuming AI credits. Update PR #1 with actual hosted evidence, retaining
   draft status while the independent AI acceptance gate is unresolved.

No further repair authorization is needed. No hosted schema change, merge,
publication, paid service or Lovable generation has been performed by this
follow-up.
