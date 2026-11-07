# Worker setup and live acceptance

Use the existing project only: `https://zxdnjnsghdnviflahvry.supabase.co`.

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
uv run python -m noetharaclipz.runner
```

The check command checks database access and Gemini model metadata independently, but performs no generation. A false verification flag does not prevent an explicitly requested model metadata lookup when a key is bound, and is never automatically changed to true. Metadata does not establish free-tier/account eligibility or quota. With missing AI credentials, preprocessing and transcription can still run when the Supabase worker credential is supplied; the job then fails explicitly before any inference. Without the worker credential, queued jobs remain waiting.

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

`scripts/acceptance.py` performs the actual browser flow and refuses to pass without a completed Gemini usage record, real highlights, a stored output, and a downloaded/decoded MP4. It has no provider fixtures. Install the pinned dependencies in `scripts/requirements-e2e.txt` in a test environment with Chromium, then set `NC_TEST_EMAIL`, `NC_TEST_PASSWORD`, and `NC_SAMPLE_VIDEO` through secure environment configuration. Set `NC_BASE_URL` for the development app and optionally `CHROMIUM_PATH` for a system browser. Run `python scripts/acceptance.py` only with the authorized worker/free AI account ready. It has been syntax checked here; its live AI acceptance run is blocked by the missing credentials described above.
