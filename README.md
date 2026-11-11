# NoetharaClipz

AI video clipping, continuing the existing Lovable/TanStack Start frontend. The internal Clipwave design, animation classes, navigation, and responsive panels are retained.

**Implementation branch:** `feat/real-video-pipeline`

**Existing app:** https://noetharaclipz.lovable.app

**Existing Supabase project:** `zxdnjnsghdnviflahvry` (`NoetharaClipZ`, us-east-1)

## Current status

The backend, real media worker, authentication, resumable upload, real player, persistent editor, and asynchronous MP4 export integration are implemented. Build/type checks, media integration tests, browser upload/playback/persistence tests, and hosted ownership/queue tests pass.

**The normal local-AI website workflow has passed against live Supabase:** upload,
queued SmolVLM2 analysis, automatic highlights, saved edits, normal queued Export
and authenticated private MP4 download/decode. See the
[hosted acceptance report](docs/hosted-local-acceptance.md). Gemini remains
disabled; the existing queued upload is protected.

The [24-hour owner-scoped EC2 pilot](docs/continuous-24h-pilot.md) completed and
stopped cleanly. The next stage is a [limited workload beta](docs/owner-scoped-beta.md)
on the same m6i.2xlarge, with SmolVLM2-500M and an 8 GiB / 2 CPU / one-job cap.
Its production frontend candidate, consent controls and independent alert monitor
are prepared; a new hosted rollout and worker start require separate approval.
The [current release gates](docs/beta-release-gates.md) record fresh owner consent,
server access controls, the attended alert option and a divergent Lovable editor
lineage that must be resolved before publication.
Global processing and Gemini remain disabled. Keep Draft PR #1 unmerged and
unpublished until separately authorized.

See [verification evidence](docs/verification.md), [architecture](docs/architecture.md), and [worker setup](docs/worker-setup.md).

## Experimental local automatic detection

The explicitly selected local provider uses pinned SmolVLM2-500M, actual video,
Whisper, scenes and audio evidence in the normal worker. Its hosted queued flow
is verified; descriptions and bounded sampling still have quality limitations.
[Model benchmarks and deployment limits](docs/worker-deployment.md) include a
real gaming test with requested 2-vCPU/8-GiB settings (kernel enforcement
was not established on the rootless executor; see the corrected preflight) and a memory-aborted 2.2B research attempt. The
larger model is not enabled in the production provider or database allowlist.

## Development

```sh
npm ci
cp .env.example .env.local
npm run dev
```

The supplied URL and publishable key are public configuration for this project. Only `VITE_*` values belong in frontend configuration. Never put a service credential or AI key in a `VITE_*` variable, a committed file, or chat.

In a cloud environment that requires the inherited HTTP proxy, use Node 24 with `NODE_USE_ENV_PROXY=1 npm run dev`. This environment's server-side auth was verified with that flag.

```sh
npx tsc --noEmit
npm test
npm run lint
npm run build
uv sync --project worker --frozen
uv run --project worker pytest worker/tests -q
```

`scripts/verify.sh` runs these checks. Set `NC_SAMPLE_VIDEO` to authorized footage to include local transcription and rendering integration. CI is manual only; verify the private repository's Actions allowance before dispatching it. CI has no production secrets or AI access.

## Supported first workflow

- Email/password sign-in, persistent cookie sessions, protected routes, account display name, sign-out. Confirmation delivery and production auth redirects still require operational verification. Google appears only when enabled in Supabase.
- Direct MP4/MOV/WebM uploads with progress, cancellation, retries, and private storage. Maximum 45 MB and five minutes; the Storage server also enforces any lower global limit.
- Separate worker: inspection, playback proxy, scene detection, audio intensity/silence signals, real thumbnails/waveform, local Whisper timestamps, native-video Gemini analysis, validated highlights, and FFmpeg rendering.
- Saved trims, manual crop position, ratios, volume, transcript caption corrections, caption styling, and export jobs. Download is offered only after the output object has been verified.
- Persistent projects, initial instructions/analysis messages, delete/restore, caption defaults, and template defaults.

Conversational editing, URL retrieval, recording, splitting, facecam detection, subject tracking, watermark rendering, long streams, and batch orchestration are not enabled. Their unsupported controls do not produce simulated successes. No Lovable AI credits are needed.

## Data and costs

Ten application tables have RLS. Five private buckets store sources, clips, thumbnails, analysis artifacts, and brand assets. Supabase's Free plan has a documented 50 MB per-file ceiling, 1 GB storage allowance, and finite egress quotas. The app reserves a conservative 200 MB per user and 800 MB overall; orphaned objects count toward admission checks.

Paid AI providers and fallback routes are absent. Gemini remains disabled unless an operator verifies a genuinely free AI Studio project and supplies its actual RPM/RPD/TPM. API metadata checks verify model access before generation. The development cap is at most one request/minute and five per rolling 24 hours, or lower account quotas.

A local worker uses CPU/disk and downloads open Whisper weights. An always-on production worker requires an existing authorized machine or separately approved hosting. No hosting, subscription upgrades, new Supabase projects, or second website were provisioned.
