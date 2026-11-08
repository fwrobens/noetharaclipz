# Verification — updated 2026-11-08

## Release gate

**Latest local-worker follow-up: implemented, hosted acceptance blocked.**
`NC_AI_PROVIDER=local` now selects real SmolVLM2 in the normal worker with
Whisper/scenes/audio, validated highlights, honest provider usage, caches and
queued rendering. A fresh disposable PostgreSQL/PGMQ run passed normal worker
analysis → saved edit → queued export → real 22.2-second captioned MP4/full
decode, without inserted highlight/completion fixtures. This is SQL/file-adapter
integration, **not** hosted browser acceptance. The hosted protocol probe and
browser launcher stopped before creating accounts or starting a worker because
the reviewed database proposal is not deployed. The user's queued job is
unchanged. No heartbeat migration was reapplied.

Current repeated checks: **60 worker tests** (authorized footage, zero skipped),
**15 frontend tests**, TypeScript, build, Ruff and lint (11 existing warnings).
Actual model testing covers Elephants Dream, Sintel, SuperTuxKart gameplay, a
muted visual derivative and a synthetic empty negative. A real blank-video false
positive and a cold NumPy serialization failure were found and corrected; raw
descriptions still hallucinate and are separated from measured evidence.
See [implementation, benchmarks, exact gates and reproduction](local-worker-integration.md)
and [disposable queue evidence](evidence/local-queue-pipeline.json).

**Can a website user now upload and automatically receive a downloadable clip?
Not yet verified on hosted infrastructure.** Do not merge or publish. The
database proposal requires authorization/versioning/deployment and the ordinary
browser flow must pass with an owner-scoped QA worker. Gemini remains disabled;
no paid inference or Lovable credits were used. Historical sections below
describe earlier runs, not additional current passes.

**Blocked. Do not merge or publish.** The newer [credential-backed verification](credential-backed-verification.md) supersedes the earlier runtime-binding blocker: Supabase worker authentication, actual private rendering/download and Gemini model metadata now pass. Automatic AI selection remains unverified with the false free-tier flag preserved. The heartbeat repair now passes real credential-backed checks; see the [post-repair record](heartbeat-repair.md) for version alignment and queue/media recheck limitations. No mock result was used to pass the complete AI gate.

The follow-up also passes modern/legacy key transport contract tests, paginated cleanup regression, graceful shutdown/recovery checks, and single-use PKCE callback tests. Real local SmolVLM2 video description succeeded, but is not accepted as AI highlight selection. The full acceptance gate remains blocked. The sections below retain the earlier implementation task's results; see the newer report for checks actually repeated in the configured environment.

## Executed checks

| Check                                                    | Result                                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `npm run build`                                          | Passed; existing Nitro/Cloudflare hosting preset retained                                               |
| Bun 1.4.4 frozen install, TypeScript, tests, build, lint | Passed with the existing Bun lockfile synchronized                                                      |
| `npx tsc --noEmit`                                       | Passed                                                                                                  |
| `npm test`                                               | 15 tests passed                                                                                         |
| `npm run lint`                                           | 0 errors; 11 Fast Refresh warnings, including existing UI-library warnings                              |
| Worker tests, with `NC_SAMPLE_VIDEO`                     | 37 tests passed, including actual authorized-footage processing                                         |
| `ruff check`                                             | Passed                                                                                                  |
| Hosted SQL `supabase/tests/access_and_jobs.sql`          | All transactional ownership, render, cancellation, lease, and idempotency assertions passed             |
| Browser email/password login                             | Passed with two provisioned temporary, preconfirmed QA accounts; confirmation email delivery not tested |
| Browser composer upload                                  | Actual 4,372,373-byte source uploaded through resumable TUS; persisted project and queued job appeared  |
| Browser playback                                         | Actual `<video>` advanced beyond 1.9 seconds, duration 52.208333 s, readyState 4                        |
| Reload persistence                                       | Project, initial instructions, queue state, and saved edit persisted                                    |
| Editor                                                   | Seek to real transcript interval, caption display, save/reload, actual render-job submission passed     |
| Delete/restore                                           | Both persisted through navigation and refresh                                                           |
| Brand Kit                                                | Saved caption color survived refresh                                                                    |
| Sign-out                                                 | Subsequent protected navigation redirected to sign-in                                                   |
| Follow-up Auth callback browser checks                   | Protected-route redirect, missing/invalid PKCE code handling, no unhandled browser errors passed        |
| Responsive                                               | No horizontal overflow on tested home/workspace/editor views at 390, 768, and 1440 px                   |
| Anonymous database access                                | Denied (401)                                                                                            |
| Cross-user projects/clips                                | Hidden by RLS                                                                                           |
| Cross-user source URL signing                            | Denied                                                                                                  |
| Cross-user finalization/export                           | Denied                                                                                                  |
| Browser source overwrite                                 | Denied                                                                                                  |
| Browser rendered-output upload                           | Denied                                                                                                  |
| Forged job completion / worker RPC                       | Denied                                                                                                  |
| Duplicate source finalization                            | Returned the same durable job                                                                           |
| Paid activation / fallback / Lovable generation          | None performed                                                                                          |

Visual inspection caught subtitles disappearing after a nonzero trim: output seeking left libass on source timestamps while captions were clip-relative. Input seeking now resets filter timestamps correctly. A rendered-frame regression test checks that text is absent before speech and visibly burned into the expected interval; the actual sample was rendered again and visually inspected with captions present.

The initial hosted upload test exposed a `pgmq.send` set-returning-function incompatibility. A migration fixed it; repeated source finalization and transactional queue tests subsequently passed. Actual Whisper execution exposed incompatible PyAV 19 behavior; PyAV 16.0.1 is now pinned and transcription passes.

The environment's Node fetch initially bypassed its proxy, preventing SSR auth. Running Node 24 with `NODE_USE_ENV_PROXY=1` fixed connectivity; browser login and server-protected routes were then tested successfully.

## Actual media evidence

Source: Blender Foundation's **Sintel trailer**, CC BY 3.0, downloaded from:
https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4

License/context: https://durian.blender.org/about/

- Actual metadata: 52.208333 seconds, 854×480, 24 fps, audio present.
- Local preprocessing: 12 detected scenes, 22 extracted frames, actual RMS waveform/audio events.
- Local `faster-whisper small` CPU int8: two timestamped speech segments, including “What brings you to the land of the gatekeepers?” at 11.92–14.16 s and “I'm searching for someone.” at 18.35–19.73 s.
- FFmpeg proof: a 10-second 720×1280, 30 fps MP4 with H.264 video and AAC audio was rendered and fully decoded. All four export ratios also pass codec/dimension/duration tests with generated deterministic media.
- Actual sample tests render timestamped captions from actual Whisper speech. Synthetic codec fixtures test renderer behavior only and are not counted as AI evidence.

A clearly labeled **manual QA interval** from the real speech segment was temporarily inserted into a QA account to test the editor and render-request UI. It was explicitly marked “NOT an AI-selected highlight,” and is not counted as successful AI detection. That fixture and its render request are removed after testing. The full AI release gate remains blocked.

## Database and storage

Six recorded migrations create ten RLS-protected application tables, five private buckets, and the private/worker orchestration routines. Local migration filenames are reconciled with the actual hosted migration versions. The existing project and organization were used throughout.

Bucket/app file limits are 45 MB; an actual 4.4 MB upload succeeded. The Free plan's documented per-file ceiling is 50 MB. The project's dashboard-only global setting still needs confirmation before asserting the full 45 MB upload boundary is available.

Supabase's security advisor reports no exposed-table RLS errors. Remaining notices: an intentionally default-deny private worker-health table has no browser policy; leaked-password protection is disabled in the existing Auth configuration. No paid Auth upgrade was enabled.

Two QA accounts and approximately 8.8 MB of source footage are retained only in this project pending authenticated worker cleanup. Their accounts are disabled, jobs cancelled, and projects marked expired after verification; their credentials remain outside Git. The cleanup worker removes expired projects via the Storage API before deleting database rows. Do not delete the accounts first and orphan their stored objects.

## Unverified or intentionally deferred

- Live Gemini metadata access, account eligibility/quotas, inference quality, automatic highlights, complete analysis-to-private-export flow.
- Worker HTTP access using the real server credential, interrupted live-worker recovery, and cancellation during an actual hosted render. SQL lease/cancellation behavior and local subprocess handling are tested separately.
- Production confirmation email delivery, Auth callback allowlist, optional Google OAuth, and continuous worker hosting.
- Conversational editing, authorized platform URL retrieval/metadata, facecam extraction, subject tracking, split/montage editing, watermark rendering, multi-hour recordings, and advanced batch processing.

The branch is submitted as a draft PR. GitHub `main`, Lovable publishing, and the existing production frontend remain unchanged.
