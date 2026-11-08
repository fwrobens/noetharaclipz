# Local automatic highlight detection — 2026-11-08

**Newer follow-up:** [normal worker integration](local-worker-integration.md)
now implements explicit local provider selection and tests actual queue-driven
analysis/rendering on disposable PostgreSQL/PGMQ. The [normal hosted website flow](hosted-local-acceptance.md) now passes with the
deployed local-worker protocol. The following is the earlier
`8230acc` isolated-runner proof and its historical limitations.

One genuine locally selected highlight has been played/edited in the existing
frontend, rendered, stored privately, downloaded through the browser and fully
decoded. This is an **explicit isolated local runner**, not acceptance of the
shared queued-upload/Gemini pipeline. The user's queued upload was not claimed,
cancelled or changed. No migration, frontend redesign, infrastructure provisioning
or paid inference was performed. Gemini remains disabled.

## Queued upload inspection

Read-only object access and FFprobe confirmed a complete 39,882,848-byte source,
H.264/AAC, 151.126667 seconds, 540×1080 and approximately 37.32 fps. These pass the
existing worker's media limits. The temporary metadata-inspection copy was
removed; no AI/transcription or frame analysis ran on the user's footage.

The analysis job remains `queued`, zero attempts, no lease, and no preprocessing
metadata. No worker has claimed it. The default shared worker has deliberately
not been started in this workspace: its only integrated provider remains Gemini,
whose free-tier gate is false. It could preprocess/transcribe the footage but
would stop before hosted inference. This is not evidence of a failed upload.
The new local runner does not automatically switch or consume that job.

## Selection implementation

`worker/noetharaclipz/local_detector.py` uses pinned, Apache-2.0
`HuggingFaceTB/SmolVLM2-500M-Video-Instruct`, revision
`7b375e1b73b11138ff12fe22c8f2822d8fe03467`. It loads standard Transformers code
with `trust_remote_code=False` and CPU PyTorch. No hosted inference API is used.

- FFprobe/FFmpeg validate and prepare actual media. PySceneDetect supplies scene
  boundaries; Whisper supplies timestamped speech/words; RMS analysis supplies
  intensity/silence events and a waveform.
- At most eight bounded candidate windows come from measured scene/speech
  boundaries and uniform coverage. They are sampled, not exhaustive long-video
  analysis. The model sees four decoded frames per candidate plus compact
  transcript, scene and measured audio evidence. It is a video model with
  supporting audio/ASR features, not a native waveform/audio-language model.
- The model compares all candidates and chooses a candidate label or **none**.
  The stored scores are relative constrained-label likelihoods, not calibrated
  interest/virality/confidence estimates. None produces no fabricated fallback.
- Timestamps come from the actual candidate interval, never generated freeform
  by the model. Bounds/finite values are checked. Titles use timestamped ASR words;
  explanations retain measured evidence. Raw model visual observations are
  stored separately with an explicit warning: they may hallucinate and should
  not be presented as established facts.

A preliminary pointwise yes/no probe rejected every clip. Its arbitrary cutoff
was not treated as calibrated confidence; it is not a passing result. The final
implementation uses a bounded comparative task with an explicit none choice.
Word-level evidence is compacted to keep the final comparison within the pinned
model's context limit. No thresholds were lowered to fabricate a passing clip.

## Authorized sample and observed result

Source: the first 60 seconds of **Elephants Dream**, distinct from the earlier
Sintel tests. Download:
https://download.blender.org/ED/elephantsdream-480-h264-st-aac.mov

Attribution: **(c) copyright 2006, Blender Foundation / Netherlands Media Art
Institute / www.elephantsdream.org**. Edited excerpt, CC BY 2.5:
https://creativecommons.org/licenses/by/2.5/ . Official licence/context:
https://orange.blender.org/blog/creative-commons-license-2/ . Attribution is
embedded in the downloaded MP4's copyright metadata and retained in a sidecar.

The local model compared actual video tensors `[8,4,3,512,512]`, using 3,877
input tokens, and chose candidate G: **42.857–52.857 seconds**. Its relative label
score was 0.348871; none was 0.019457. These are not quality guarantees. The full
pipeline including media preparation, real Whisper, comparison, visual
observation and initial rendering took 112.02 seconds on this instance.

The existing editor then changed the start to **43.0 seconds** and the aspect
ratio to **1:1**, saved the edit and retained it after refresh. The local renderer
loaded that actual saved Edit and produced a 720×720 H.264/AAC MP4, duration
**9.866667 seconds**, with real timed captions. Its private browser download
matched the uploaded bytes and decoded completely. Browser playback checks
require the playhead to advance while the video is unpaused, not just a nonzero
seek position. The stricter check exposed and then verified fixes for mounting the editor before saved trims were initialized and for starting playback below a nonzero clip boundary. The existing frontend layout is unchanged.

`check_local_highlights.py` writes only temporary QA rows/objects in the existing
Supabase project. It does **not** call `worker_claim`, finalize an analysis upload,
create pgmq messages or enqueue an export. After actual CPU rendering/upload it
records a truthful completed-render audit row with
`execution=explicit-isolated-local`, enabling the existing Download MP4 UI.
This is not proof of a shared-queue claim or of the normal app Export button
processing a queued render. Local provider provenance is stored truthfully;
no Gemini usage or completed Gemini analysis is manufactured.

The temporary QA account, project and private objects were removed after testing.
The original active-job snapshot was identical before/after. Sanitized actual
results are in [the evidence file](evidence/local-automatic-highlights.json).
The local downloaded artifact is under
`test-results/local-auto-ed-final/downloaded-automatic-highlight.mp4`.

## Reproduction

Use the existing isolated checkout, not a new worktree. Keep all keys in their
existing secure runtime bindings, never browser variables or source files.
Prepare an optional environment independent of the worker's frozen dependencies:

```sh
uv venv /workspace/.tools/local-vlm
uv pip install --python /workspace/.tools/local-vlm/bin/python torch==2.9.0 torchvision==0.24.0 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python /workspace/.tools/local-vlm/bin/python -r scripts/requirements-local-highlights.txt
HF_HOME=/workspace/.cache/huggingface HF_HUB_DISABLE_XET=1 /workspace/.tools/local-vlm/bin/python scripts/detect_local_highlights.py /path/to/authorized/sample.mp4 --output test-results/local-auto --prompt 'Find a clear speaking or gesturing moment.'
```

The detector writes analysis evidence, a validated editable `edit.json`, and a
real `automatic-highlight.mp4`. `--edit` accepts a saved validated Edit for export.
The bounded sampler supports media up to five minutes but covers only up to eight
windows; multi-hour streams are not supported.

For the isolated UI/private-download test, run the app with
`NODE_USE_ENV_PROXY=1 npm run dev -- --host 0.0.0.0 --port 8080 --strictPort`,
prepare the worker environment and the pinned `scripts/requirements-e2e.txt`
environment, then run:

```sh
python scripts/check_local_highlights.py /path/to/authorized/sample.mp4 test-results/local-auto --attribution 'Appropriate source credit and licence'
```

This command creates and removes only its own temporary QA data. It requires the
already bound server credential and the false Gemini gate; it does not require
an idle shared queue.

## Model research and remaining limits

Official Hugging Face metadata identifies SmolVLM2 500M and SmolVLM2 2.2B as
ungated Apache-2.0 models. The latter has approximately 2.25B parameters and a
larger CPU/memory cost; it was investigated, not benchmarked or silently enabled.
Qwen2.5-VL-3B was also considered; its licence was not established by the metadata
lookup, so it was not selected. Exact revisions and metadata are retained in the
result file. Only the pinned 500M model was used for this proof.

The 500M model's raw visual sentence is coarse and not fully reliable (including
an unverified rooftop interpretation). Selected windows may cut utterances;
ASR can misrecognize words. Sampling, temporal coherence, hallucination rates,
choice/order bias and subjective highlight quality need broader evaluation.
This single real sample does not establish production detection quality.

The default worker/completion RPC and original acceptance script remain
Gemini-specific. Connecting an opt-in local provider to normal queue orchestration
requires a separately reviewed change that preserves truthful provider metadata,
leases, cancellation and atomic completion. No such migration or automatic
provider fallback was introduced. Keep PR #1 draft; no merge/publication until
that normal workflow and quality gates are verified.
