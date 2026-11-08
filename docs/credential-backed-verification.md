# Credential-backed verification — 2026-11-07

Historical test record. The heartbeat defect described below was subsequently repaired. See the [2026-11-08 follow-up](heartbeat-repair.md) for the passing real heartbeat, aligned migration version, and current queue/media recheck limitations.

The published `noetharaclipz` environment supplies the runtime variables that were
absent in the earlier implementation task. This run fetched and checked out
`feat/real-video-pipeline` at `b6c69bb1b1845ebfb5585e4da32778f124c423f9`.
GitHub `main`, the published app, and the saved environment configuration were
not changed. No paid inference, subscriptions or hosting were activated.

## Results

- **Supabase worker authentication works.** The bound credential is a legacy
  `service_role` JWT and was verified remotely against the intended project,
  `zxdnjnsghdnviflahvry`. All ten application tables are accessible to the worker;
  all five buckets are private. Modern `sb_secret_` transport remains covered by
  contract tests; a modern key was not supplied for this live run.
- **Gemini model access works.** An authenticated metadata request for
  `models/gemini-3.8-flash` returned HTTP 200 and supports `generateContent`.
  `GEMINI_FREE_TIER_VERIFIED=false` was preserved. Metadata does not establish
  billing status, account eligibility or remaining quotas. No hosted generation
  or token-count request was made.
- **NVIDIA authentication works for account metadata.** The configured key
  returned HTTP 200 for the official NVCF functions listing; an invalid control
  returned HTTP 401. The public model catalog returned 200 even anonymously, so
  that catalog alone was not counted as authenticated access. Credit balance,
  free inference permission and production eligibility remain unverified.
- **AnyModel remains unverified.** Its variable is present, but no official API
  base URL/account configuration is available. No credential was sent to a
  guessed endpoint.
- **15 frontend tests and 37 worker tests passed**, with the authorized Sintel
  sample enabled and no worker tests skipped. TypeScript, production build,
  Python lint and frontend lint passed; frontend lint retains 11 warnings.

## Live media and private download

`scripts/check_live_pipeline.py` runs an independent browser/worker test rather
than weakening `scripts/acceptance.py`. It creates temporary confirmed test
accounts, requires the false hosted-inference gate, uses real media and removes
its own remote objects/projects/accounts afterward. Account passwords remain in
memory, and no runtime secret values are included in its report.

The final run passed 18 functional/security checks:

- Actual browser sign-in and resumable upload of the authorized 4,372,373-byte
  Sintel trailer, with idempotent upload finalization.
- Real durable job claiming and worker source download, preprocessing, frame
  uploads and local Whisper transcription. The checkpoint contains 12 scenes,
  22 frames, 32 audio events and two timestamped speech segments. Processing
  stopped explicitly at the false Gemini gate; no provider usage or automatic
  highlights were created.
- A temporary interval explicitly labelled **MANUAL QA — NOT AI-selected**
  enabled independent rendering checks. Actual playback, a keyboard trim change,
  saving, reload persistence and idempotent export submission passed.
- The actual Python worker rendered, uploaded and committed the private output.
  The UI downloaded it successfully, and FFmpeg decoded the whole file.
  The MP4 contains H.264/AAC, lasts 4.166667 seconds and is 632,346 bytes.
  Its source trim is 11.0–15.16 seconds. A decoded frame was visually inspected
  and contains the real speech caption burned into the image.
- Cross-user table reads, media signing/download, export and finalization were
  denied. Anonymous public-file access, source overwrites, browser output
  uploads, forged job completion and browser worker access were denied.
- Editor layouts at 390/768/1440 px had no horizontal overflow. Brand defaults,
  delete/restore persistence, sign-out/protected redirects, missing/invalid PKCE
  callbacks and absence of unhandled browser errors were verified.

Measured durations on this development instance (single warm-cache run, not a
production performance guarantee): preprocessing/transcription/upload 24.19 s;
render/upload/completion 4.09 s; browser/media test including cleanup 62.35 s.
The complete 37-test worker suite took 61.90 s, including its sample/media work.

Local artifacts, ignored by Git:

- `test-results/live-independent-pipeline.json`
- `test-results/live-manual-qa-download.mp4`
- `test-results/live-caption-frame.png`
- `test-results/current-provider-check.json`
- `test-results/nvidia-account-metadata.json`

Sanitized machine-readable evidence is retained in
[`evidence/credential-backed-verification.json`](evidence/credential-backed-verification.json).

## Live queue recovery

Six additional real HTTP control checks passed in 127.31 seconds. A temporary
uploaded source was queued, and the actual worker's graceful shutdown preserved
its active lease. After waiting for the real 120-second visibility/lease expiry,
the job was reclaimed with a fresh token and incremented attempt count. The old
token was rejected. Global concurrency, cancellation acknowledgement, retry and
rejection of finished-job resurrection also passed. This is queue-control
evidence rather than AI analysis or cancellation during an actual FFmpeg render.
Its temporary source, project and account were removed. Raw local evidence is
`test-results/live-queue-recovery.json`.

## Newly exposed heartbeat defect

The independent media test deliberately exits **nonzero** because its remaining
worker-health check fails. The actual `worker_heartbeat` RPC returns database
error `21000`, **`UPDATE requires a WHERE clause`**. The function updates
`private.worker_health` without a predicate; the hosted database's safe-update
guard rejects it. Authenticated `pipeline_health` consequently reports
`online: null`, `ai_ready: false` and no heartbeat detail.

The required function correction is to scope that singleton update with
`WHERE id = true`, preserving the worker authorization check and database
safe-update enforcement. The definition is in
`supabase/migrations/20261107180530_clipping_pipeline.sql`, around line 301.
Apply the [authorized versioned function correction](heartbeat-repair.md)
through Supabase SQL/migration tooling, then rerun the health and live acceptance checks. Do not
rewrite the applied migration or disable the safety guard.

The repository's `AGENTS.md` assigned database changes to Lovable during the
initial test task. The user subsequently authorized a narrow exception for the
heartbeat repair; its new migration and local regressions are recorded in the
linked follow-up. No hosted schema/function modification has been performed,
because the Supabase SQL plugin is not exposed in this chat. Direct `Worker.once`
processing was used to verify the independent media path while recording the
health failure, rather than representing the application as release-ready.

## Local multimodal benchmark

The existing, pinned SmolVLM2 research probe was rerun on the real 11–21 s Sintel
interval. It used actual video tensors `[1, 4, 3, 512, 512]`, 372 input tokens and
25 generated tokens. Warm inference/processing took **11.24 seconds** on CPU,
excluding model loading/download. Raw output is in
`test-results/current-local-video-description.json`.

This is a coarse visual-description benchmark. Its interpretation has not been
validated for accuracy or timestamp selection and is not a worker fallback or
an AI-selected highlight. It does not pass the AI release gate.

## Reproduction

Use the existing isolated checkout; do not create a worktree for these checks.
Never copy runtime credentials into `.env.example`, frontend variables or Git.

```sh
cd /workspace/noetharaclipz
npm ci
uv sync --project worker --frozen
NC_SAMPLE_VIDEO=/path/to/authorized/sintel.mp4 bash scripts/verify.sh
NODE_USE_ENV_PROXY=1 npm run dev -- --host 0.0.0.0 --port 8080 --strictPort
```

In a separate shell, with `scripts/requirements-e2e.txt`
installed in the Python environment, a system Chromium available,
and the already bound server credential:

```sh
NC_SAMPLE_VIDEO=/path/to/authorized/sintel.mp4 python scripts/check_live_pipeline.py
```

Until the function correction is applied, the independent script's expected
outcome is 18 successful functional checks plus the failing heartbeat check and
exit status 1. The original complete-AI acceptance script was not run with a
stub, patched readiness, altered free-tier flag or synthetic provider output.

## Remaining release gates

Keep PR #1 draft and do not merge or publish. Fix and validate worker health;
independently confirm a permitted free hosted inference account and actual
quotas; then execute actual automatic highlight selection and the original
complete browser acceptance script. Continuous hosting, production confirmation
email/redirect configuration and the dashboard-only global Storage limit still
need their separate operational verification.

The earlier administrative SQL transaction suite and Supabase advisor were not
rerun in this session: no administrative SQL integration or database connection
credential is attached. The six live queue checks above exercised the real
worker's HTTP boundary instead. Previously reported SQL/advisor outcomes remain
historical evidence, not new results from this run.

The Sintel trailer is Blender Foundation footage under CC BY 3.0:
https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4
(context/license: https://durian.blender.org/about/).
