# Hosted local-provider acceptance — 2026-11-08

The **normal application workflow passes against live Supabase** with a local
SmolVLM2 worker scoped to a temporary QA owner. A user can use the ordinary
upload/Generate/editor/Export/Download interface with an active local worker;
no separate per-video detector/render script or inserted highlight fixture is
required. The frontend tested here is the development website connected to the
existing project, not a new publication of the public Lovable website.

**Keep Draft PR #1 draft. Nothing was merged or published.** QA workers are
stopped and QA accounts/data are removed after testing. No always-on production
CPU worker has been provisioned. Existing-user processing has not been enabled;
the protected upload remains queued with zero attempts and no lease.

## Migration recorded, never reapplied

The user reports successful application and ledger recording as
`20261108152724_local_worker_queue`. Under their specific authorization, the
reviewed SQL was copied verbatim into
`supabase/migrations/20261108152724_local_worker_queue.sql`.

SHA256 of both the recorded migration and frozen proposal:
`37ff1347f255c3a3217258c3c54daa58f7a1342c392643e1ee5e8a01f04324fd`.
Historical proposal comments are retained to preserve those exact bytes. No
hosted migration/DDL command was executed in this task. The already deployed
heartbeat migration remains unchanged.

The actual ledger version and catalog/RLS inspection are attributed to the
operator's report. Independently, the bound service credential now passes
`worker_protocol()` version 1 and scoped health/claims over the live API, and the
local provider loads successfully. The normal hosted analysis and export jobs
then completed through those functions. This session does not expose SQL catalog
or Lovable tools, so a full catalog/remote-editor drift comparison is not claimed.

The disposable SQL harness now recognizes the recorded migration and checks
its equality with the proposal instead of applying both. Existing access/jobs,
heartbeat and local provider SQL suites pass against fresh PostgreSQL/PGMQ.

## First normal website run

[Raw first-run evidence](evidence/hosted-local-website-first.json) records:

1. Confirmed temporary QA account signs in through the normal login page.
2. The normal composer uploads authorized Elephants Dream footage using TUS,
   takes the desired-highlights prompt and creates the real processing job.
3. The owner-scoped normal worker claims the analysis message (attempt 1), runs
   actual Whisper/video/scenes/audio analysis and selects a genuine highlight.
4. The saved highlight appears in the project workspace at **31.650–54.000 s**.
   Transcript/measurement evidence and actual pinned local model provenance are
   stored. No Gemini usage records are substituted.
5. The user selects it, opens the existing editor, plays actual footage, changes
   the trim to **31.700–54.000 s**, saves, and refreshes. The changed edit persists.
6. The **normal Export button** queues a real render job, claimed on attempt 1.
   The worker renders captioned H.264/AAC and commits it to private
   `rendered-clips` storage through the existing completion RPC.
7. The **normal Download MP4 button** downloads the authenticated private output.
   FFprobe and full FFmpeg decode pass: **720×1280, 22.300000 s, 5,070,117 bytes**.
   SHA256: `9040142ea33351973fe377c2958c7ac1f85a4c57c81dd30dd9df2795f0cc4e53`.

The entire path uses ordinary queued application processing. No manual
highlights, direct terminal-job writes or isolated-render audit shortcuts are
used. Cross-user project/video/highlight/clip/job/artifact/usage reads are hidden,
cross-user private output is denied, browser worker operations are denied, and
invalid uploads are rejected. No unhandled browser error was recorded.

[Actual model result](evidence/hosted-local-model-source.json) retains the first
run's fresh inference: **98.937 seconds**, **4,246 input / 29 output tokens**,
actual comparison tensor hash and pinned model revision. This is model-analysis
time, not upload-to-download time. The raw visual description remains separately
marked as hallucination-prone.

Two follow-up attempts exposed an acceptance-test race: it clicked Play on the
project preview while the editor's authenticated route was still loading, then
observed that old element pause on unmount. The retained
[event trace](evidence/hosted-playback-test-race.json) shows the old element at
0.066 s and the new editor element at 31.650 s. The test now waits for the actual
Library heading, editor URL and initialized trim controls. No product playback
or frontend design change was needed. Failed attempts' QA data was removed.

The corrected stricter follow-up **passed** the complete normal website flow in
**45.652 seconds**, with 19.722 seconds through upload/analysis. It reused the
real first-run media/ASR/model cache, recorded **zero new inference tokens** and
retained the original 4,246-token model evidence; this is not a second fresh
inference benchmark. Actual queued rendering and browser download/decode still
ran. Its 22.3-second MP4 is 5,070,115 bytes, SHA256
`b562e9a85825dc5dd5f789a9c1bc9a01da5d99d7e9b11cbbce9d56bedc5f1caa`.
[Full final evidence](evidence/hosted-local-website.json),
[saved editor screenshot](evidence/hosted-local-saved-edit.png), and
[normal Export ready screenshot](evidence/hosted-local-export-ready.png).

## Security and queue controls

The follow-up browser/security run **passed** anonymous private-media denial,
cross-user source URL signing denial, owner-browser source/output overwrite
denial, browser job-state forgery denial, anonymous privileged-worker denial,
and shutdown clearing local readiness. All its checks and both QA-account
removals are recorded in the final evidence above.

The live queue test uses a separate authorized Sintel upload and an explicit QA
owner scope for **every** claim. It exercises normal worker shutdown before
processing, actual 120-second lease/visibility expiry, fresh-token reclaim,
stale-token rejection, concurrency, owner cancellation/worker acknowledgement,
retry, terminal-job protection and the three-attempt limit. It never uses a
global claim or changes the protected upload. All checks **passed in 125.72
seconds** and its test data/account were removed. Reports distinguish these API
queue-control checks from the actual video/browser proof above.
[Actual live recovery/cancellation evidence](evidence/hosted-local-queue-recovery.json).

Final automated regression: **60 worker tests**, zero skipped with authorized
Sintel footage (38.83 s), **15 frontend tests**, TypeScript, production build,
Ruff, and lint with zero errors/11 existing warnings. The full protected job row
hash matches the preceding task's snapshot exactly, including zero attempts,
no lease and no cancellation request. No global consumer was started.

## Operational limits

`GEMINI_FREE_TIER_VERIFIED=false` stays in effect. Local mode makes no Gemini or
other hosted inference calls, incurs no model API usage, and creates truthful
local-provider usage at zero estimated cost. No paid service, Lovable generation
or billing activation was performed.

The [multi-sample quality/performance results](local-worker-integration.md) still
apply: descriptions can hallucinate, candidate sampling is bounded and scores
are uncalibrated. One passing website flow does not establish broad highlight
accuracy. Production availability still requires an authorized persistent CPU
worker, production Auth/email/redirect/storage-limit checks and the remaining
Lovable/configuration drift review. None is silently provisioned by this test.
