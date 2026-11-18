# Optional AI refinement router

Status: **implemented with mocked providers only; disabled by default.** No real
NVIDIA or AnyModel request has been made. Enabling it in any deployed worker needs
the separately approved stages listed at the end.

## Where it sits

```
Existing EC2 pipeline (unchanged)
  Whisper transcription + SmolVLM2 local selection (LocalProvider.analyze / detect())
        |
        v   local Analysis  -- always the base result
Optional refinement router (worker/noetharaclipz/router.py)   NC_ROUTER_ENABLED=false by default
  visual_context       -> GLM       (NVIDIA)  text only: transcript, scene list, SmolVLM2 description
  highlight_reasoning  -> DeepSeek  (NVIDIA)  titles, categories, tighter intervals, user instructions
  fallback (each task) -> Nemotron  (NVIDIA)  -> Nemotron (AnyModel, only if its key is configured)
        |
        v   strict schema + measured-bounds + rank_candidates() checks
worker_finish_analysis (unchanged RPC, unchanged local provenance)
  invalid output or total failure -> the original local Analysis object, unchanged
```

The router runs in `Worker.refine_with_router` (`worker/noetharaclipz/runner.py`) only in
the `NC_AI_PROVIDER=local` path, after `LocalProvider.analyze()` and before the
`worker_finish_analysis` RPC. The Gemini path is untouched. `artifacts.provider` /
`artifacts.model` stay `local-smolvlm2` / pinned SmolVLM2, so `worker_finish_analysis`,
its local-provenance checks and the `worker_protocol` provider allowlist
(`gemini`, `local-smolvlm2`) are unchanged.

Whisper (`transcription`) and SmolVLM2 (`video_analysis`) are local-only tasks;
`ModelRouter.routes()` refuses to build hosted routes for them.

## What a refinement may change

For each local highlight, exactly once (by `index`): `title` (<=120 chars), `category`
(Clutch/Funny/Hype/Reaction/Tutorial/Other), `explanation` (<=600 chars), and `start`/`end`,
which must stay inside that highlight's measured local interval. `score` and
`visual_evidence` always remain the local measurements. Highlights cannot be added,
dropped, duplicated or moved outside measured bounds. The refined list must also pass
`Candidate` validation and `rank_candidates()` without losing any entry. The router never
receives job, project, owner or lease identifiers, and responses containing any extra field
(such as `project_id`) fail schema validation. The worker additionally checks that the
job/project/owner identity is unchanged after refinement.

## Five safety requirements

| Requirement | How it is met |
| --- | --- |
| Independent fallback | Route order per task: NVIDIA primary -> NVIDIA Nemotron -> AnyModel Nemotron (`ModelRouter.routes`). AnyModel is skipped (recorded as `skipped/no_credential`) when no key is configured. |
| Strict validation | `parse_json_object` (strict JSON, no NaN/Infinity), closed pydantic schemas with `extra="forbid", strict=True` (`VisualContext`, `HighlightRefinement`), measured-bounds check, `Candidate` re-validation and `rank_candidates()` (`validate_refinement`). Invalid => next route. |
| No raw video uploads | `RouterInput` holds only transcript text, scene times and SmolVLM2's description text. `assert_text_only` rejects non-string content parts (image/video/audio), extra message keys and inline `data:` media before any request. |
| Safe model logging | `ModelRun.as_record` has a fixed field list (no prompts, transcript, responses or keys). Error messages are fixed templates, redacted and truncated to 160 chars. Logging goes through `worker_log_model_runs` best-effort; RPC failure is logged locally and ignored. Proposed table/RLS: `docs/model-runs-schema.sql`. |
| Hard off switch | `NC_ROUTER_ENABLED` unset/false/malformed => `DisabledRouter`: no key files are read, no HTTP client is constructed, no model request and no logging RPC. Total failure returns the original local object. |

Retries: up to 2 attempts per route for 429, 5xx, timeouts and transport errors (backoff
<=4 s); 4xx is not retried. A 180 s scheduling deadline prevents new attempts from starting
after the budget expires; each in-flight request receives the smaller of the configured
request timeout and remaining budget, and retry sleep is capped by the remaining budget.
HTTPX timeouts are per-operation/inactivity limits, not strict wall-clock cancellation, so
this is not a mathematically hard 180 s wall-clock bound. A cancellable transport is required
before claiming that stronger guarantee or enabling live provider calls. Lease cancellation
raised by `tick()` always propagates.

## Configuration

Names only; values belong in server-side secrets, never in the repo, never `VITE_`-prefixed.

| Variable | Default |
| --- | --- |
| `NC_ROUTER_ENABLED` | `false` |
| `NVIDIA_API_KEY` / `NVIDIA_API_KEY_FILE` | unset |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `ANYMODEL_API_KEY` / `ANYMODEL_API_KEY_FILE` | unset (AnyModel fallback skipped) |
| `ANYMODEL_BASE_URL` | `https://anymodel.org/v1` |
| `NC_REASONING_MODEL` | `deepseek-ai/deepseek-v4.1-flash` |
| `NC_VISION_CONTEXT_MODEL` | `z-ai/glm-5.3-flash` |
| `NC_FALLBACK_MODEL` | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| `NC_ANYMODEL_FALLBACK_MODEL` | `am/nemotron-3.5-lightning-30b-a3b` |
| `NC_ROUTER_TIMEOUT_SECONDS` | `30` (clamped 1..120) |

Base URLs must be `https`. The deploy supervisor (`deploy/worker/noetharaclipz_deploy/supervisor.py`)
and `continuous_entry.py` still strip `NVIDIA_API_KEY` / `ANYMODEL_API_KEY` from the worker
child, and compose does not set `NC_ROUTER_ENABLED`; that is intentional. Enabling the router
on EC2 requires a later, separately approved deploy change (secret files + env + egress review).

## model_runs table

`docs/model-runs-schema.sql` is a proposal to apply **through Lovable** (AGENTS.md forbids
hand-editing `supabase/migrations/`). It adds `public.model_runs` with owner-only SELECT via
project ownership, no user INSERT/UPDATE/DELETE, and a service-role-only
`worker_log_model_runs(jid, token, runs)` RPC that verifies the live lease and derives the
project from the job. Until it is applied, the worker's logging call fails harmlessly.

SQL regression (disposable in-process PGlite, never touches Supabase):

```
npm install --no-save @electric-sql/pglite   # or PGLITE_DIR=<dir with it installed>
node scripts/test_model_runs_sql.mjs
```

## Tests

`worker/tests/test_model_router.py` uses `httpx.MockTransport` only and patches the real
HTTP transport to fail if touched. It covers the off switch, DeepSeek success, GLM text-only
input, timeout/429/5xx fallback to NVIDIA Nemotron, AnyModel fallback (and skip when
unconfigured), invalid JSON/schema/bounds => next route, total failure => unchanged local
result, record contents, logging failure, cancellation, configured request-timeout capping,
retry-backoff capping and the unchanged `NC_AI_PROVIDER` no-fallback rule.

## Staged approvals

1-3 (approved, this change): router + mocked providers, tests + model-run logging, one PR.

Each of the following needs its own explicit approval:

4. Real NVIDIA/AnyModel API tests. NVIDIA's free API endpoints are governed by the NVIDIA
   API Trial Terms (internal testing/evaluation only, no production use). They must not be
   quietly used as a production provider; licensing is evaluated separately first.
5. Rebuild the worker image and start EC2 (including the deploy change above).
6. Merge and publish (and applying `docs/model-runs-schema.sql` through Lovable).
