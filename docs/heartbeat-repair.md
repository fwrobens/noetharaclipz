# Worker-heartbeat repair and version reconciliation — 2026-11-08

**Live credential-backed heartbeat now passes.** The operator reported applying
the repair as Supabase migration `20261108013140` and passing the hosted SQL
regression/security checks. The SQL test was rolled back without a synthetic
heartbeat. This follow-up independently called the real endpoint with the bound
worker credential and received HTTP 204. Authenticated health then reported
`online=true`, `ai_ready=false`, and a detail truncated to 300 characters.

Anonymous calls to heartbeat/claim/tick returned 401. Regular authenticated QA
calls returned 403. The temporary account was removed. The operator's report of
preserved owner, SECURITY DEFINER, grants and advisor results is separate from
these independently executed HTTP checks; live catalog/ledger inspection is
still unavailable in this chat.

## Migration alignment

The Git file was renamed from
`20261107201038_worker_heartbeat_singleton.sql` to
`20261108013140_worker_heartbeat_singleton.sql` to match the operator-reported
Supabase ledger version. The SQL bytes are identical, and the local regression
script/documentation references use the aligned filename. There is only one
heartbeat migration file. The six original migrations remain unchanged.

**Do not reapply the heartbeat migration or modify the migration ledger.** This
follow-up performed no DDL or ledger writes. The rename reconciles Git with the
reported deployed version; it does not perform another database deployment.

The narrow repair retains the worker authorization check, function signature,
PL/pgSQL, SECURITY DEFINER and empty search path and adds only `WHERE id = true`.
The prior isolated PostgreSQL 17.11 regression verified singleton targeting,
unchanged identity/owner/ACL/execution metadata, repeatability and denied browser
roles. The user's narrow AGENTS.md exception remains specific to this repair.

## Tests after repair

- Real credential-backed heartbeat, detail limit and six unauthorized RPC
  requests: passed.
- Local worker suite with authorized Sintel footage: **37 passed, zero skipped**,
  31.61 seconds. Includes actual preprocessing, transcription, all export ratios,
  caption rendering, subprocess cancellation and worker-recovery contracts.
- Frontend: **15 passed**. TypeScript and production build passed; ESLint has
  zero errors and 11 existing warnings.
- Live queue and browser/media rechecks: **blocked before creating QA data**.
  An existing non-QA MOV analysis job is queued. Both scripts correctly refused
  to consume unrelated work. The user explicitly requested leaving that upload
  queued; it was not claimed, cancelled or modified. Earlier successful live
  queue/private-download tests remain historical evidence, not new passes.

No continuously running worker was started because it could claim the existing
upload. A successful test heartbeat is time-limited; it is not a claim of ongoing
worker availability. Hosted Gemini inference remains disabled, and the complete
AI-selected-highlight acceptance gate remains unverified.

Sanitized current evidence:
[`evidence/postrepair-verification.json`](evidence/postrepair-verification.json).
The older `heartbeat-repair.json` is explicitly retained as a historical
predeployment record.

## Next checks

Once the upload owner has handled the pending job or the queue is otherwise
idle, rerun these from the existing isolated checkout without creating a worktree:

```sh
worker/.venv/bin/python scripts/check_worker_heartbeat.py
NC_SAMPLE_VIDEO=/path/to/authorized/sintel.mp4 worker/.venv/bin/python scripts/check_live_queue.py
NC_SAMPLE_VIDEO=/path/to/authorized/sintel.mp4 python scripts/check_live_pipeline.py
```

The media script needs the app running on port 8080 and its pinned Playwright
dependencies. It tests a clearly labelled manual interval while hosted inference
stays false; it does not replace the original complete AI acceptance script.

Keep PR #1 draft. No merge, publication, paid service, environment-configuration
change, unrelated database modification or Lovable generation was performed.
