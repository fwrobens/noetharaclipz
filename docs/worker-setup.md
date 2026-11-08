# Worker setup and live acceptance

Use the existing project only: `https://zxdnjnsghdnviflahvry.supabase.co`.

See [isolated deployment preparation](worker-deployment.md) for the standby-first
Docker configuration, resource/cost review and authorization gates. No EC2
service has been started.

## Current local provider setup

The [normal local-worker integration](local-worker-integration.md) is implemented
and [normal hosted website acceptance](hosted-local-acceptance.md) now passes.
The operator-applied protocol is recorded as `20261108152724_local_worker_queue`;
do not reapply it. Do not start a global worker around the protected upload. The heartbeat
repair must not be reapplied.

Use explicit `NC_AI_PROVIDER=local`, `GEMINI_FREE_TIER_VERIFIED=false`,
`WHISPER_MODEL=small` and the existing Supabase worker credential. Local mode
does not need Gemini keys or quotas. An unset provider retains legacy `gemini`;
unsupported values fail and there is no fallback. Install the pinned optional
CPU model environment described in
[local setup](local-automatic-highlights.md#reproduction), including
`scripts/requirements-local-highlights.txt`, in the Python that runs the worker.
At least 6 GiB available RAM is checked before startup (use an 8 GiB or larger
host). Both models load once; one active job is allowed. The private cache root
is configurable with `NC_WORKER_CACHE_DIR`.

Current development **must use `NC_WORKER_OWNER_ID=<temporary QA owner UUID>`**.
An unset scope permits global consumption and must not be used. The safe
launcher below creates that owner and starts the normal worker scoped to it;
it skips global cleanup. It checks the deployed protocol before creating any
account or worker. It never inserts highlights/completed jobs or bypasses the
normal Export button.

```sh
NC_AI_PROVIDER=local GEMINI_FREE_TIER_VERIFIED=false /path/to/local-vlm/bin/python scripts/check_worker.py
# Repeat isolated acceptance against the already deployed protocol:
NC_AI_PROVIDER=local GEMINI_FREE_TIER_VERIFIED=false NC_LOCAL_PYTHON=/path/to/local-vlm/bin/python NC_SAMPLE_VIDEO=/path/to/authorized/sample.mp4 CHROMIUM_PATH=/usr/bin/chromium python scripts/accept_local_queue.py
```

Use an E2E Python environment with `scripts/requirements-e2e.txt` and the app
running at `NC_BASE_URL` (default `http://127.0.0.1:8080`). Model Python is
`NC_LOCAL_PYTHON`. Secure test credentials stay in child-process environment.
Readiness is false until the selected provider/protocol/models are ready;
startup failure disables claims. Local `check_worker.py` never contacts Gemini.
Current hosted protocol/readiness and scoped website acceptance pass. See [the report](local-worker-integration.md) for benchmarks,
queue tests and exact remaining release gates.

The following Gemini requirements are retained for that explicit provider;
they do not gate local processing.

## Requirements

Python 3.11–3.13, uv, FFmpeg/FFprobe with libx264, AAC and libass, and an unprivileged worker process. Dependencies and PyAV are pinned in `worker/uv.lock`. Bundled caption fonts retain their OFL licenses.

Supply these through secure environment settings or an ignored local secret file loaded by your shell/service manager:

- `SUPABASE_URL`: the existing project URL above.
- `SUPABASE_SECRET_KEY` (preferred) or `SUPABASE_SERVICE_ROLE_KEY`: a server-only worker credential from that project. Either name accepts a modern `sb_secret_` key; the legacy alias also supports a `service_role` JWT. Modern keys are sent only in `apikey`; JWT credentials use `apikey` and `Authorization: Bearer`. Never use a publishable key or user access token as the worker credential.
- `GEMINI_API_KEY`: from a genuinely free, billing-disabled AI Studio project eligible for development use.
- `GEMINI_FREE_TIER_VERIFIED=true`: only after checking that project's tier.
- `GEMINI_VERIFIED_RPM`, `GEMINI_VERIFIED_RPD`, `GEMINI_VERIFIED_TPM`: actual account limits shown in AI Studio; zero disables inference.
- `WHISPER_MODEL=small` (default).

Never paste keys in chat or commit them. The application deliberately has no paid activation or automatic model fallback. Supplying a key from a paid project is not a way to enforce free usage; verify the underlying project first.

Current official references reviewed for this implementation:

- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/terms

The model is fixed to `gemini-3.8-flash` on the development allowlist. Free tier content may be used for product improvement and reviewed by humans, with regional exceptions described in Google's terms. Do not submit sensitive/confidential/personal information. The composer requires a permission/data acknowledgement.

## Check and run

```sh
uv sync --project worker --frozen
cd worker
uv run python ../scripts/check_worker.py
# Do not start an unscoped/global consumer while the protected upload is queued.
```

In explicit Gemini mode the check command checks database access and model metadata independently, without generation. A false verification flag is never automatically changed to true; metadata does not establish free-tier/account eligibility or quota. The normal service now checks selected-provider readiness before claiming jobs. Without a ready provider/worker credential, queued jobs remain waiting.

## Complete the release gate

1. Verify Auth site URL and allowed callback URLs for local development and `https://noetharaclipz.lovable.app/auth/callback`. Verify confirmation email delivery; Google OAuth is optional and currently disabled.
2. Confirm the project's global Storage limit. Buckets/app cap sources and exports at 45 MB, and the Free plan's ceiling is 50 MB. A lower configured global limit still wins.
3. Start the worker and check its readiness. Use authorized, non-sensitive sample footage.
4. Upload from the actual composer, describe a real moment, and observe a claimed background job with persisted progress.
5. Inspect live provider usage, actual transcript/visual evidence, and at least one valid AI-selected highlight. Do not replace this step with a fixture.
6. Seek/play the source, save a trim and captions, export, and wait for verified completion. Download the private MP4 and inspect/decode it.
7. Refresh and sign back in to verify persistence; use a second account to verify isolation.
8. Record evidence in `docs/verification.md`. Only then make the PR ready, satisfy repository checks, merge, and publish through existing Lovable hosting.

Do not provision paid hosting, enable billing, change unrelated projects, or publish while this gate is blocked.

## Repeatable browser acceptance

`scripts/acceptance.py` performs the actual browser flow and requires completed usage for the explicitly selected provider, actual claimed analysis/render jobs, genuine model evidence, saved edits and a downloaded/decoded private MP4. It has no provider fixtures. The safe local launcher above supplies temporary QA credentials and scoped worker selection. For an already authorized test account/worker, set `NC_TEST_EMAIL`, `NC_TEST_PASSWORD`, `NC_SAMPLE_VIDEO`, `NC_AI_PROVIDER`, `NC_BASE_URL` and optionally `CHROMIUM_PATH` securely. The local hosted gate now passes with the deployed queue protocol; Gemini remains disabled. See [current verification](local-worker-integration.md).

`scripts/check_live_pipeline.py` separately verifies real worker preprocessing,
transcription, browser editing, manual-interval rendering, private download and
cross-user isolation while requiring the hosted inference flag to stay false.
It is historical independent/manual QA evidence and its idle-queue guard must not
be bypassed. It never replaces the complete AI acceptance gate.
