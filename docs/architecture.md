# Architecture

## Existing frontend

TanStack Start/React 19, TanStack Router/Query, Radix, Tailwind, and the Lovable hosting build stay in place. The newer Lovable Supabase connection files were recovered through its integration because commit `71ceb528` is not available as a GitHub ref. No Lovable AI prompt or regeneration was used.

Cookie-backed Supabase sessions are validated in a request-scoped server client before protected routes render. Browser data requests carry the user's JWT and are governed by RLS. Server identity responses are private/no-store. Only publishable configuration enters browser bundles.

## Database and orchestration

| Table                 | Responsibility                                                                    |
| --------------------- | --------------------------------------------------------------------------------- |
| profiles              | Auth-linked display information and preferences                                   |
| projects              | Ownership, instructions, timestamps, soft deletion, source and status             |
| videos                | Immutable source path, verified metadata, playback/thumbnail paths                |
| processing_jobs       | Durable state, attempts, lease, cancellation, progress, immutable render snapshot |
| highlights            | Source-relative intervals, categories, explanations, evidence and ranking         |
| clips                 | Versioned edit decisions and verified output references                           |
| conversation_messages | Initial instructions and actual analysis responses                                |
| brand_settings        | Caption and template defaults                                                     |
| analysis_artifacts    | Transcript, scenes, audio signals, real waveform and frames                       |
| provider_usage        | Atomic request reservations, usage, unknown outcomes, zero-dollar guard           |

The authenticated API prepares a unique upload path and reserves capacity. The browser uploads directly using TUS. `finalize_upload` checks the stored object's exact size and atomically creates a unique job plus a `pgmq` message. Repeated finalization returns the same job.

Public RPCs are invoker wrappers. Privileged bodies live in a non-exposed private schema, with explicit ownership or worker-role checks and restricted execute grants. Browser roles cannot set processing state, detected highlights, output paths, or worker leases. No CPU-heavy work runs in an Edge Function or web request.

`source-videos`, `thumbnails`, `processing-artifacts`, `rendered-clips`, and `brand-assets` are private. Source insertion requires the exact reservation and an uploading status. Source replacement and browser-written rendered output are denied. Signed URLs are short-lived; object locations, not signed URLs, are persisted.

## Worker

The [local provider integration](local-worker-integration.md) adds explicit
`NC_AI_PROVIDER=local` selection to the normal worker. It loads pinned CPU
SmolVLM2 and Whisper once, caches actual media/ASR/inference by source/model/
version/prompt, compares scene/speech/uniform candidate videos with measured
audio evidence and persists validated results with truthful local provenance.
It does not require Gemini or invoke hosted inference. The reviewed database
proposal adds provider-aware atomic completion and service-only owner-scoped
claims/health; it is deployed and recorded as `20261108152724_local_worker_queue`.
QA workers never use global claims or cleanup. Normal hosted browser acceptance
and scoped queue recovery/cancellation have passed; see the
[hosted report](hosted-local-acceptance.md). No persistent production worker has
been provisioned.

A Python worker pulls the logged `pgmq` queue over Supabase's API. Worker-only RPCs claim a fenced 120-second lease. A heartbeat renews it every 20 seconds. Global active-worker concurrency is one. Interrupted claims become eligible again; attempts are capped at three. Explicit cancellation terminates subprocesses when observed. Each job has a 20-minute processing deadline; FFmpeg operations have their own timeouts.

Processing uses FFprobe/FFmpeg, OpenCV/PySceneDetect, and faster-whisper `small` with CPU int8. Demuxers and network protocols are restricted, commands never use a shell, and media paths are server generated. Temp directories are removed after jobs and stale directories after 24 hours. Incomplete uploads expire after 24 hours; deleted projects are purged after 30 days by the running worker through the Storage API.

Native Gemini video windows are at most 90 seconds, with 10-second overlap. Local timestamped evidence accompanies the actual compressed video. A provider protocol keeps format-specific implementation separate. No text-only provider receives video. Candidate times are mapped to the source, bounded, ranked, and overlap-filtered. Empty results stay empty.

Model access is checked against the API before inference. Billing tier/account quotas must be verified in AI Studio because model metadata does not establish them. Atomic usage reservations enforce the conservative application limit. Transport failures have no automatic paid or inference retry; unknown outcomes block duplicate dispatch. Completed window JSON is cached privately.

Rendering consumes a versioned immutable edit snapshot, original footage, and timestamped speech. Outputs are H.264/AAC MP4 with fast-start, at 720×1280, 1280×720, 720×720, or 720×900. FFprobe and a full decode validate each output. Completion checks the exact private Storage object and size before permitting a download.

## Production boundaries

The local worker is a development process, not permanent hosting. Deploying the frontend alone cannot process videos. Run the worker as an unprivileged service on an authorized machine with FFmpeg and sufficient CPU/disk. Use a dedicated host/container and maintained media binaries for production untrusted uploads.

There is no remote URL download path in this MVP, preventing arbitrary URL/SSRF access. Account confirmation email delivery, OAuth, redirects, worker credentials, free provider eligibility/quotas, and an always-on worker remain operational prerequisites for production release.
