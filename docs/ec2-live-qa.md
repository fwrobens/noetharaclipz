# EC2 local-worker QA — 9 November 2026 UTC

The normal application UI successfully produced downloadable, automatically
selected clips using the existing EC2 worker and live hosted Supabase. Three
distinct authorized samples passed; an additional cached gaming run also passed.
No highlights were inserted manually and no rendering shortcut was used.

This is an **owner-scoped, time-limited QA deployment**. It does not enable
normal users or the global queue. The user's original queued upload remains
byte-for-byte identical as a database row, with zero attempts. Draft PR #1 is
still draft; nothing was merged or published.

## What actually ran

- Existing instance `i-0be10e530045fc650`, Ohio, m6i.2xlarge.
- Reviewed Linux amd64 image manifest
  `sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`.
  No rebuild, pull, resize or new infrastructure.
- Container `fbe3d4f4d9b1c95cb3cae77278a40a5cf5d52c77435eccdc3d14c60d17c06f99`;
  one temporary QA owner, one active job, 8 GiB / 2 vCPU / no extra swap /
  256 PID cap, no public ports, dedicated volumes and egress policy.
- Explicit local SmolVLM2-500M at revision
  `7b375e1b73b11138ff12fe22c8f2822d8fe03467`; Whisper-small at
  `536b0662742c02347bc0e980a01041f333bce120`. Gemini/global approval remain false.
- The controller verified resource configuration before starting. The real
  container's deadline wrapper checked its kernel quotas before loading a key or
  model. Operator readiness reported existing services unchanged.
- Existing Supabase service credential delivered as RSA4096-OAEP-SHA256
  ciphertext through existing private storage. The host unsealed it locally;
  its transport private key was removed after successful readiness. The private
  54,754-byte startup handoff object was deleted after the operator receipt.

The browser UI was served by the development website in this cloud workspace;
authentication, queue, database and private storage were the actual hosted
Supabase project, and processing/rendering ran on EC2. The public production
website was not redeployed. In this managed cloud environment the Node 24 test
server needs `NODE_USE_ENV_PROXY=1` and the provided CA trust. The initial
server-auth attempt failed before uploading because that launch setting was
missing; restarting only the cloud test website resolved it. No EC2 service or
authentication policy was changed.

## Browser results

Each successful run used login → upload → instructions → Generate → actual
queue claim → multimodal analysis → saved highlight → Select clip → Edit →
Save → refresh → normal Export dialog → actual render queue → Download MP4.
Each downloaded file passed full FFmpeg decoding and duration/codec checks.
No unhandled browser errors occurred in these successful runs.

| Authorized input | Model-selected interval | Actual inference | Upload + analysis | Full UI workflow | Download |
| --- | --- | ---: | ---: | ---: | --- |
| Elephants Dream, 60 s, dialogue | 50–60 s | 63.682 s | 109.012 s | 130.786 s | 9.9 s H.264/AAC, 1,760,385 bytes |
| SuperTuxKart, 60.007 s | 36.6–46.6 s | 60.280 s | 104.159 s | 128.660 s | 9.9 s H.264/AAC, 3,645,799 bytes |
| Same gaming input + prompt, cached | 36.6–46.6 s, original genuine result reused | No new inference | 22.784 s | 47.040 s | 9.9 s H.264/AAC, 3,645,799 bytes |
| Muted Sintel, approximately 15 s | 8.691–15.209 s in worker metadata | 45.692 s | 65.724 s | 82.049 s | 6.367 s H.264, 617,104 bytes |

UI trim edits change the selected start before export and persist after refresh.
The gaming uncached workflow includes an intentional cancellation/retry, so its
timing is not a controlled baseline for calculating a cache speedup. The cached
run proved preparation, transcript and analysis cache hits and recorded **zero
new input/output inference tokens**, with original source/model provenance
retained. Different downloads of identically sized exports can have different
hashes; each actual file's hash is recorded in its evidence.

The quiet derivative is reported as 15.209 s by the EC2 media toolchain and
15.083 s by the cloud toolchain. Its output remains within the test's 0.25 s
duration tolerance. This cross-version boundary difference needs tighter
normalization before claiming frame-exact timing; it was not hidden by changing
the deployed image during QA.

## Recovery, cancellation and security

The normal UI cancelled gaming inference; the actual worker acknowledged it in
10.409 s. The UI then retried the same job, which completed on attempt two with
`cancel_requested=false`. Preparation/transcription were reused, while genuine
model analysis and rendering still occurred. The harness now waits for the
asynchronous retry RPC's server acknowledgement; its first attempt read stale
cancelled state even though the application had already retried successfully.

For recovery, the single QA owner uploaded deliberately invalid test media via
the normal upload API. The test claimed only that new owner's job once through
`worker_claim_scoped` and abandoned the real lease without modifying time or
renewing it. The EC2 worker reclaimed it after **123.138 s**, with a new token and
attempt two, and rejected it through real FFprobe validation. A stale token could
not update/revive the job. The permitted third attempt also failed safely; a
fourth retry was denied. No highlights or inference usage were created for the
malformed media. This is actual lease recovery, **not a Docker/host crash test**.

Live security checks passed:

- Anonymous privileged protocol/scoped-claim calls: 401; authenticated QA calls:
  403. No global claim RPC was used by these tests.
- Cross-owner project/job/video/highlight rows hidden; cross-owner private source
  download and signing denied. Those read-only checks did not process the upload.
- Anonymous/public rendered-file access denied; authenticated owner access works.
- Duplicate Export returns the same completed render job and creates no duplicate.
- Browser clients cannot forge worker completion. Invalid size, MIME and prompt
  inputs are rejected without creating projects.
- New QA provider usage is local SmolVLM2 with zero recorded inference cost;
  there are no fake Gemini usage records or paid provider calls in this path.
- Repeated full-row hashing confirms the user's original job remains unchanged,
  queued, with zero attempts.

## Highlight quality and limits

All three distinct sources produced one in-bounds highlight according to worker
metadata and no duplicate selections within a project. The automated ASR
boundary-cut metric was zero; this does not establish semantic completeness or
ground-truth transcription. The dialogue selection reaches the input's end.

Raw model narration remains a **warned private diagnostic**, separate from the
transcript/audio/scene evidence saved in the workspace. This distinction matters:
the gaming narration incorrectly described gunfire, while sampled source frames
show kart racing with boost trails, bends and a rock arch. The false narration
was not promoted into the user-facing title/explanation. Racing action is a
plausible candidate; this test does not establish it as the best or funniest
moment. Scores 23/37/47 are relative choices, not calibrated confidence.

Three samples do not establish broad accuracy for humor, surprises or spoken
reactions. Quiet footage is handled without inventing speech/audio evidence.
No larger model was installed or activated. Keep 500M as the tested production
candidate; these results provide no reason to resize EC2, but quality remains a
separate evaluation task.

## Trial lifecycle and remaining work

The immutable deadline is **00:52:12 UTC on 9 November 2026**; graceful shutdown
starts before it and crash retries retain the same deadline. No new work may
extend this window. A read-only monitor is watching for the scoped stopped
heartbeat. At report time exact Docker exit, Docker crash restart, host reboot
recovery and actual peak CPU/RAM counters have not been directly observed by
this agent. The operator has been asked for read-only cgroup usage counters.
Do not equate resource limits with measured consumption.

Always-on/global deployment is not enabled. It still needs an authorized rollout
with host restart/firewall persistence reviewed, runtime resource evidence and
crash-restart verification. The existing queued upload remains protected. Do not
merge or publish automatically after this QA success.

Automated checks: 155 worker tests passed, one optional sample skipped; Ruff
passed. The unchanged frontend's 15 tests, TypeScript and build passed; ESLint
retains 11 existing warnings and zero errors. No Lovable credits or billable
Actions/registry operations were activated. No migrations were reapplied.

## Evidence and source attribution

- [Operator startup receipt](evidence/ec2-qa-host-ready.json)
- [Dialogue browser acceptance](evidence/ec2-qa-dialogue.json)
- [Gaming cancellation/retry and browser acceptance](evidence/ec2-qa-gaming-cancel-retry.json)
- [Cached gaming browser acceptance](evidence/ec2-qa-gaming-cache.json)
- [Quiet visual browser acceptance](evidence/ec2-qa-silent-visual.json)
- [Live access/security checks](evidence/ec2-qa-security.json)
- [Lease recovery, invalid input and retry limits](evidence/ec2-qa-lease-recovery.json)
- [Model observations, warnings and quality limits](evidence/ec2-qa-model-quality.json)

Footage attribution: Elephants Dream © 2006 Blender Foundation / Netherlands
Media Art Institute / www.elephantsdream.org, CC BY 2.5; Sintel trailer © Blender
Foundation, CC BY 3.0; SuperTux Kart-Autoren benchmark recording, CC BY-SA 4.0.
The quiet sample removes audio, and exported samples are cropped/trimmed
derivatives. [Original source and license links](local-worker-integration.md#authorized-sources)
must accompany redistributed derivatives, including CC BY-SA terms for the
gaming export. No footage from the user's protected upload was used.
