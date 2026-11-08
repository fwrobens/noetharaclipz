# Local provider and normal queue integration — 2026-11-08

**The normal website flow now passes against live Supabase** with an explicitly
selected local provider and owner-scoped QA worker. See the
[hosted acceptance report](hosted-local-acceptance.md). The migration was applied
by the operator, then recorded here at its exact reported version without
reapplying it. The protected upload remains queued and unchanged. The heartbeat
repair at `e22528b` is untouched. Keep the PR draft; no merge or publication is
authorized. A persistent production CPU worker has not been provisioned.

## Worker path

Set `NC_AI_PROVIDER=local` explicitly. `build_provider` chooses the pinned
SmolVLM2-500M implementation; unsupported values fail and there is no fallback.
The backwards-compatible unset default remains `gemini`; `.env.example` now
shows explicit local selection. Keep `GEMINI_FREE_TIER_VERIFIED=false`.
Local mode does not inspect Gemini metadata, require its key/quotas, reserve
Gemini usage, or call hosted inference. No Lovable credits or paid services are
used.

The ordinary `Worker.once → Worker.process` path downloads the exact uploaded
source, validates size/media, extracts playback/frames/scenes/audio, transcribes
with Whisper, compares actual candidate videos, checks timestamps and saves
highlights through the existing atomic completion RPC. The existing render-job
branch consumes the saved edit and produces/validates an actual captioned MP4.
Existing frontend components, layout, authentication and private buckets remain
in place. No frontend fixture or completed-job insertion is needed by this path.

`ai_ready` becomes true only after the selected provider loads successfully.
Local startup checks for at least **6 GiB available RAM**, warms both models once,
and refuses work if dependencies/resources/protocol are missing. Real inference
peaked at about 4.1 GiB RSS here; use an 8 GiB or larger CPU host and one active
job. This does not establish viability on a 4 GiB machine. Graceful shutdown
clears readiness; interrupted jobs retain their recoverable lease. Cancellation
checks run between actual transformer layers as well as FFmpeg/ASR stages.

## Database proposal and protected queue

The [reviewed SQL proposal](proposals/local-worker-queue.sql) was applied by the
operator and recorded under the user's explicit AGENTS.md exception as
`supabase/migrations/20261108152724_local_worker_queue.sql`. Both files have
identical SHA256 `37ff1347f255c3a3217258c3c54daa58f7a1342c392643e1ee5e8a01f04324fd`.
No hosted SQL/migration was reapplied. The exact ledger version is based on the
operator's report; actual protocol/readiness, queue operations and normal
website processing were independently verified over HTTP. Full catalog/Lovable
editor drift inspection remains unavailable in this session.

The proposal contains only:

- Provider-aware completion with unchanged function signature/security, fenced
  non-null leases, measured local usage and pinned model provenance. Local usage
  is inserted atomically with highlights/job completion, with cost zero. Cache
  replay/empty admission have honest zero executed tokens; unexplained zero is
  rejected. Gemini's existing reservation path stays intact.
- Service-only owner-scoped claims and health. Scoped claims join the owner's
  job to its exact PGMQ message and change visibility only for that message;
  they never call a global `pgmq.read`. The existing global single-job advisory
  lock, attempts, cancellation, lease/visibility renewal and retry rules remain.
- A private owner-keyed health table with browser access revoked and RLS on.
  Authenticated health shows that owner's fresh scoped worker, otherwise the
  existing global health; stale readiness is false. Other users do not see QA
  readiness. A service-only protocol RPC prevents consumption before deployment.

Development must use `NC_WORKER_OWNER_ID=<temporary QA owner UUID>`. The new
browser launcher supplies this automatically and skips global cleanup. It
compares the protected live job before/after; SQL regression additionally checks
an unrelated queue message byte-for-byte. No global consumer was started.

## Actual quality and performance evidence

[Full raw V3 benchmark](evidence/local-provider-benchmark-v3.json),
[earlier failure/control run](evidence/local-provider-benchmark-baseline-v2.json),
and [quiet visual run](evidence/local-provider-quiet.json) retain actual tensor
hashes, tokens, scores, intervals, CPU time and sampled memory. Model scores are
relative constrained-label likelihoods, **not accuracy, virality or calibrated
confidence**. There is no labeled evaluation corpus or accuracy claim.

| Footage | Observed selection | Time / CPU / peak RSS | Assessment |
| --- | --- | --- | --- |
| Elephants Dream, 60 s | Model window 42.857–52.857; utterance-completed 31.650–54.000 s | 88.402 s / 179.175 CPU s / 3.46 GiB | Real spoken reaction; whole measured utterances preserved. Description falsely claims a rooftop. |
| Sintel, 52.208 s | 37.292–47.292 s | 82.590 s / 168.162 CPU s / 4.08 GiB | Dramatic visual/action candidate; subjective interest is not verified ground truth. |
| SuperTuxKart, 60 s | 36.600–46.600 s | 87.711 s / 176.848 CPU s / 4.09 GiB | Coarse reviewed racing/boost interval; no streamer speech. Raw model description invents a gun/shooting. |
| Black/silence, 8 s | No highlight after measured admission fix | 0.060 s / 0.060 CPU s / 2.54 GiB resident loaded models | Earlier model falsely chose 4.571–8.000 s. Retained as a real failure, not hidden. |
| Muted Sintel derivative, 15.083 s | 8.619–15.083 s | 79.074 s / 142.079 CPU s / 3.22 GiB | Detailed quiet footage reaches the model; not rejected merely for silence. No spoken/audio evidence is asserted. |

The first four V3 trials reuse **media and ASR**, but perform fresh versioned
model inference on positive samples. Their 83–88 seconds are not directly
comparable to the prior 112-second full cold proof. V2 cold preparation/inference
took 108.035/105.220/104.903 seconds for the three positives; different cache and
run conditions prevent attributing the full difference to one optimization.
The quiet run includes fresh media preparation and overlapped another isolated
CPU test, so its wall time is not an isolated throughput measurement.

Second identical analyses reuse prepared media, transcription and model result
in **0.002–0.011 seconds**, with zero new inference tokens and unchanged
selections. These are provider/cache timings, not browser-to-download timings.
V3 initializes RSS sampling before each trial; V2's fast cached trials sometimes
sampled no RSS and recorded zero—those zeros mean unavailable, not zero memory.
CPU percentages are relative to one core (roughly 200% for the main positives).
One model instance serves all samples per benchmark. An actual transformer-layer
cancellation interrupted computation in 0.23 seconds after two checkpoints.

Source/model/version/prompt-keyed caches reuse transcripts, playback, candidate
extraction and inference. Temporary JSON/video files are atomically renamed;
cache roots are worker-private. Other entries older than 24 hours or over the
1 GiB budget are pruned when preparing another source. Candidate sampling stays
bounded (up to eight windows/four frames each) and can miss brief events. Only
one highlight is selected per source, so duplicate selections are structurally
absent in these runs; this is not evidence of multi-highlight recall.

The empty-media guard requires actual flat, unmoving frames **and** no speech or
meaningful measured audio. A quiet detailed image remains eligible. Measured
ASR segment bounds extend clips when they fit the 60-second export limit. These
positive runs have zero measured ASR boundary cuts; badly segmented/long speech
can still need manual trimming. A cold-run NumPy timestamp serialization failure
found by the real queue test was corrected and given regression coverage.

Funny moments, streamer spoken reactions, ordering bias, false negatives,
exhaustive long-video coverage and broad genre accuracy remain unverified. Raw
visual observations are private diagnostic data with warnings, separate from
timestamped transcript/audio/scene evidence shown in the saved highlight.

## Authorized sources

- Elephants Dream: © 2006 Blender Foundation / Netherlands Media Art Institute /
  www.elephantsdream.org, CC BY 2.5. [Source](https://download.blender.org/ED/elephantsdream-480-h264-st-aac.mov),
  [official license](https://orange.blender.org/blog/creative-commons-license-2/).
- [Sintel trailer](https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4), Blender Foundation, CC BY 3.0; the same authorized 52.208-second
  sample used in existing verification. The quiet sample removes audio and
  copies the first 15 seconds (container ends at 15.083 s).
- [Benchmark SuperTux Kart Base Profile 2025.07.04 - 10.19.10.02.webm](https://commons.wikimedia.org/wiki/File:Benchmark_SuperTux_Kart_Base_Profile_2025.07.04_-_10.19.10.02.webm),
  SuperTux Kart-Autoren, CC BY-SA 4.0. Used the official 240p VP9 derivative
  (4,731,822 bytes), not the 1.67 GB original; first 60 seconds transcoded for
  testing. Credit/license must accompany redistributed derivatives.
- Black/silence is an FFmpeg-generated negative control.

No user's queued footage was used for this evaluation.

## Reproduce and finish the hosted gate

Prepare the optional CPU environment using [local setup instructions](local-automatic-highlights.md#reproduction),
install `scripts/requirements-local-highlights.txt`, and use the already-pinned
official CPU Torch/Torchvision versions. `HF_HOME` can reuse downloaded weights.
The standard worker lock remains light; do not install a larger model.

```sh
NC_SAMPLE_VIDEO=/path/to/authorized/sample.mp4 worker/.venv/bin/python -m pytest -q worker/tests
worker/.venv/bin/python scripts/test_local_worker_sql.py
# Optional: real model, real disposable queue, and real queued render, no hosted DB:
NC_AI_PROVIDER=local GEMINI_FREE_TIER_VERIFIED=false NC_SAMPLE_VIDEO=/path/to/authorized/sample.mp4 /path/to/local-vlm/bin/python scripts/test_local_worker_sql.py --pipeline
```

The SQL harness uses pinned PostgreSQL 17 and checksum-verified real PGMQ 1.8.1.
Its Auth/Storage metadata fixture is explicit and is not hosted authentication
or Storage acceptance. `--pipeline` uses a SQL/local-file adapter around the
**ordinary worker**, not a separate detector/render shortcut. It does not insert
highlights, usage records or terminal job statuses. It cannot prove browser
transport, Supabase Auth, hosted private download or UI behavior.

Actual fresh `--pipeline` result: **passed**. Preparation, ASR and inference were
all uncached; analysis including model warmup took **127.347 seconds** while
other isolated CPU checks also ran. The normal worker selected 31.650–54.000 s,
the owner saved a changed 31.800–54.000 s square edit, and the normal render job
created a **3,109,088-byte, 22.200000-second** H.264/AAC MP4 that fully decoded.
The saved edit, truthful local usage, duplicate finalize/export prevention,
cross-user RLS denial, and complete protected job/message equality all passed.
No highlight, terminal job or usage record was inserted by the harness.
[Actual queue evidence](evidence/local-queue-pipeline.json).

Final repeated automated checks: **60 worker tests**, zero skipped with authorized
Sintel footage; **15 frontend tests**, TypeScript, build, Ruff, and frontend lint
with 11 existing warnings. The SQL harness also passes the existing access/jobs
and heartbeat suites plus new scoped provider/cancellation/recovery/provenance
checks. No existing migration or heartbeat function was modified on the host.

The proposal is now deployed and recorded. To repeat isolated acceptance, start
the unchanged app and run:

```sh
NC_AI_PROVIDER=local GEMINI_FREE_TIER_VERIFIED=false python scripts/check_worker.py
NC_AI_PROVIDER=local GEMINI_FREE_TIER_VERIFIED=false NC_LOCAL_PYTHON=/path/to/local-vlm/bin/python NC_SAMPLE_VIDEO=/path/to/authorized/sample.mp4 CHROMIUM_PATH=/usr/bin/chromium python scripts/accept_local_queue.py
```

Use an E2E Python environment with `scripts/requirements-e2e.txt`. The launcher
creates its own confirmed QA owner and another user, waits for scoped readiness,
and drives the ordinary website login/upload/instructions/Generate, highlight
selection, playback, changed trim/Save/refresh, **Export button → real render
queue**, and **Download MP4 button → decode**. It checks completed actual queue
claims, true local provenance, persisted edits, invalid uploads, cross-user row
and private-output denial, browser privileged-operation denial, and the
protected job snapshot. It cleans up only its own completed QA data. If its own
job remains active after failure, it retains that QA data for scoped recovery
rather than deleting an in-flight job or touching another user's queue.

Current run: **normal hosted browser acceptance passed**, including genuine
queued local analysis, normal Export, private browser download and decode.
Actual scoped lease recovery/cancellation/retry controls also passed in 125.72
seconds. See [current machine-readable status](evidence/local-hosted-status.json)
and [the hosted report](hosted-local-acceptance.md). QA workers/data are removed
after testing. No merge, publication, new hosting or paid activation occurred.
