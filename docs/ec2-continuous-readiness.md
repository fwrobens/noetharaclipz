# Continuous SmolVLM2-500M readiness — final QA results, 9 November 2026 UTC

**Keep the existing m6i.2xlarge and SmolVLM2-500M. The bounded reliability stage
passed and stopped automatically. Continuous/global processing remains disabled.**
No resize, larger model, paid inference or new infrastructure is indicated by
these measurements. A continuous rollout still needs reviewed boot isolation,
ongoing monitoring and explicit queue opt-in controls.

Host observations come from operator-pasted, read-only SSM collectors; Codex has
no direct EC2 execution connection. Browser and hosted REST checks ran from the
development environment against actual Supabase and the actual EC2 worker.
No public website deployment, merge or paid-service activation occurred.

## Completed monitored trial

| Check | Final evidence |
| --- | --- |
| Instance | `i-0be10e530045fc650`, m6i.2xlarge, us-east-2; 8 vCPU / 32 GiB host |
| Trial | `f3fc3665-76e9-4cc5-b6e6-2c437873a6a4` |
| Approved window | 05:34:44–06:04:44 UTC; never reset or extended |
| Plan SHA256 | `80acdb44a931f6cfeba318d58b034b7232a3b7e1032866f6cd1827656536529d` |
| Reviewed image | `sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`, Linux amd64; reused without rebuild/pull |
| Actual controls in both generations | 8 GiB; CPU quota 200000/100000; no extra swap; 256 PIDs; one active processing job |
| Actual shutdown | **06:03:11.648 UTC**, automatic `deadline` reason, exit **0**, no OOM |
| Restart count | **1**, caused by the single authorized runner-only SIGKILL |
| Recovery | Same job completed on attempt two; reclaim observed after **118.672 s**; new token and stale-token rejection |
| Network proofs | Both generations passed kernel controls, IPv6 disabled, public DNS/TLS and all seven scoped denial-counter checks |
| Final controller | `closed`; no error or cleanup error; processing grant removed; approved code hashes unchanged |
| Resources | **2,719,240,192 bytes (2.53 GiB) kernel peak RAM; 205.439% sampled peak CPU; 306.891388 CPU seconds** |
| Coverage | **781 samples**, both generations' final snapshots captured, `resource_coverage_complete=true` |
| Existing services | All six match their admission baseline; five Docker health checks healthy, REST has no health check as before |
| Earlier containers | Successful expired trial and failed startup attempt both remain exited, zero restarts, unchanged start/finish times |
| Protected upload | Whole row unchanged; queued, zero attempts, no cancellation or lease |

[Final host report](evidence/reliability-followup-final.json),
[authorization and launch receipts](evidence/reliability-followup-authorization.json),
[dual-generation isolation proof](evidence/reliability-followup-monitor-0541.json).

At **06:07:51 UTC**, [post-deadline hosted checks](evidence/reliability-followup-post-shutdown-supabase.json)
independently confirm the QA owner reports `online=false`, `ai_ready=false`,
all four QA jobs remain completed, zero active unfinished leases and the original
upload's identical queued/zero-attempt row. The expired scoped health falls back
to stale global detail text; no heartbeat or queue mutation was issued to refresh it.

CPU peak is the maximum observed interval rate, with one core = 100%; it is not
an instantaneous hardware maximum. Preserve the measured 205.439% without
clamping; the actual two-CPU quota was separately read from both cgroups.
CPU counters were summed across distinct domains without restart double-counting.
Totals include preprocessing, crash/recovery, rendering, the cached repeat and
idle time. These observations establish this bounded workload's usage; they do
not establish sustained production throughput or worst-case 300-second input use.

## Normal website workflow and security

The new authorized input was a genuine contiguous **180-second SuperTuxKart**
video, H.264/AAC, 18,575,024 bytes. The first run performed new local multimodal
inference, selected a 151.967–161.967 s highlight, survived the controlled crash,
and completed the ordinary website workflow. One fresh QA processing owner was
used throughout; the existing user's queued upload was outside that scope.

| Website run | Upload + analysis | Full workflow | Download |
| --- | ---: | ---: | --- |
| Long gaming with forced crash/recovery | 286.988 s | 310.965 s | 9.9 s, 720×1280 H.264/AAC MP4, 2,044,140 bytes |
| Sequential cached repeat | 18.267 s | 43.574 s | Same decoded MP4 hash; zero new inference tokens |

Both runs used sign-in, real upload/instructions, scoped job queue, genuine
highlight, playback/edit/save/refresh, normal Export, queued FFmpeg rendering
and authenticated private MP4 download/full decode. No manually inserted
highlight or isolated rendering shortcut. The local model recorded 3,711 input
and 12 output tokens on the recovered inference run, with one completed local
provenance record. Prepared-media/transcript caches survived the crash; the
repeat reused all three caches while retaining original provenance separately.
Timings include different recovery/control paths and are not a controlled
model-only speedup estimate.

Live security checks passed: anonymous and regular authenticated privileged
worker calls denied (401/403); cross-owner rows/source access/signing denied;
public rendered-file access denied; owner downloads permitted; duplicate Export
reuses the existing job; forged completion and invalid uploads rejected.
All four QA jobs completed, with local provider records and zero recorded
provider cost. Gemini stayed disabled and no provider fallback was used.

[Recovery browser result](evidence/reliability-followup-live-acceptance.json),
[cached repeat](evidence/reliability-followup-cached-acceptance.json),
[live security](evidence/reliability-followup-security.json),
[hosted checks](evidence/reliability-followup-api-checks.json), and
[full trial procedure, actual results and footage attribution](reliability-trial.md).

The earlier [three-source browser results](ec2-live-qa.md) remain valid. The
frontend was the existing development server against live Supabase and EC2;
the public website was not published. These are verified QA-owner results.
Model scores are not calibrated accuracy, and raw narration can hallucinate.
The gaming explanation separates measured audio/scene evidence from visual
observations. No larger model was installed to conceal those limits.

## Closed-trial restart safeguards

The actual policy remains `on-failure:3`; normal exit 0 does not trigger it.
The dedicated transient controller was launched with `Restart=no`. The final
read-only collector confirms no running/restarting worker and no processing
grant. The approved entrypoint and nine pinned files remain unchanged. Every
new generation checks the original expiry before models/credentials and needs
a fresh, short-lived root-owned network grant. There is no fresh approval or
automatic deadline reset. Do not restart this closed container or reuse its
receipt for a continuous service.

Both earlier trials and all archived evidence remain untouched. The first
successful trial stopped cleanly at 00:50:37 UTC; its historical resource peaks
were unavailable. The failed 05:07 trial never loaded AI or claimed work: Docker
raw PREROUTING drops intercepted probes to live container IPs before the filter
counters. The corrected unused-IP probes were then verified on the actual host,
without changing firewall rules. See [original shutdown](evidence/ec2-qa-shutdown-host.json)
and [failed startup evidence](evidence/reliability-startup-failure.json).

## Remaining gates before continuous processing

1. **Safe boot and isolation ordering.** The active crash trial proved
   generation restart/regrant, not host/daemon boot ordering. The base Compose
   profile defaults to standby; its `unless-stopped` policy needs a dedicated
   isolation-before-queue controller for active continuous rollout. Require
   Docker, dedicated mounts and a reviewed worker-only isolation unit, verify
   bridge ownership/collisions, actual hook order and live rejection counters,
   then issue fresh grants. Keep periodic verification/revocation active. Restore
   only explicitly approved worker rules; do not flush shared chains, modify
   host-wide Docker settings or reboot this shared host without authorization.
2. **Explicit queue opt-in.** Keep global off. Existing SQL atomically scopes
   claims by owner. The protected old upload must remain held. Existing-owner
   or individual old-job release remains blocked until a reviewed server-side
   atomic release protocol enforces consent, source revision, protected-job
   exclusion, revocation and audit. No schema/RLS change was made here.
3. **Continuous operations configuration.** Prepare a separately reviewed
   controller/scope configuration with bounded restart/backoff, durable bounded
   log/metric retention, stale-readiness/resource alerts, disk headroom and
   temporary-file cleanup. Retain one job, 8 GiB, 2 vCPU, private file secrets,
   no public ports and explicit local provenance. The current hard 30-minute
   policy and receipt remain intact. No monitoring subscription or persistent
   boot unit was installed during this QA stage.

Rollback must revoke the dedicated grant and gracefully stop only the matching
worker/container/controller. Preserve assets, evidence and queued work; leave
Noethara and Supabase services untouched. The current trial already completed
that safe stop automatically; no additional stop/restart is needed.

**Recommendation:** the existing host and 500M worker are suitable candidates
for a limited, owner-scoped continuous pilot after the dedicated startup and
queue-control rollout is prepared and authorized. The measured reliability
stage is complete. General-user/global processing remains disabled, and this
recommendation does not authorize a restart, deployment, merge or publication.

Validation: **229 worker tests passed, one optional sample skipped; Ruff passed.**
The seven probe regression cases supplement the earlier reliability tests.
Approved code/image and prior evidence hashes were unchanged during live QA;
only verification documentation/evidence changed afterward. Existing frontend,
TypeScript, build and lint results remain applicable; no frontend code changed.
