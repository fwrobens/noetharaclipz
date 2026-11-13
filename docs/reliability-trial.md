# Monitored reliability trial: completed and stopped

The existing m6i.2xlarge remains the host. The reviewed SmolVLM2-500M image and
pinned Whisper assets are reused; no new image, larger model, infrastructure or
paid service is required. Normal website clipping already passed on EC2.
The authorized monitored attempt `bebbf5ad-094f-4b6f-964f-c7ac22e1f760`
failed its startup network gate at **05:07:23 UTC on November 9** and stopped
with container exit 0, no OOM and no restart. Its controller exited 1 because
the gate failed. No model loaded, job was claimed, highlight was generated or
crash was injected. Its absolute approval deadline remains **05:32:30 UTC**;
neither that receipt nor its installed configuration is rewritten or reused.

The operator's raw-table output confirms the cause: Docker drops traffic to
live staging/Supabase container IPs before the filter-table worker REJECT
counter. The probe mistakenly used those live IPs. This was a diagnostic error,
not evidence of successful network access. The reviewed filter policy still
matches admission. The correction uses unused addresses in the same private
subnets, as the earlier successful preflight did. It checks Docker allocations
and raw-table interception read-only and retains the requirement for a positive
matching counter delta. Partial proof files now retain the target, socket errno
and before/after counters on failure. No firewall rule is changed.

The new configuration below is **installed on EC2 and separately authorized**.
The user approved one bounded trial with one worker-only crash test. Its fixed
window is **05:34:44–06:04:44 UTC on November 9**; the shutdown reserve is
included and the deadline cannot be recalculated. One fresh QA identity and its
root-private approval receipt were issued. The normal browser test observed
scoped readiness for the pinned 500M model, uploaded the real 180-second sample,
and a live first-attempt analysis lease was observed. The operator confirmed
startup and one automatic restart; both generations passed actual kernel and
network proofs. The same analysis job completed on attempt two, and normal
Edit/Save/Refresh/Export/private MP4 Download passed. A sequential cached repeat
and live authentication/storage/invalid-input checks also passed. The final
collector confirms automatic deadline stop at **06:03:11.648 UTC**, exit 0,
no OOM, no remaining grant, both generations' final snapshots captured and
complete resource coverage. See [the final host evidence](evidence/reliability-followup-final.json).
See the [authorization record](evidence/reliability-followup-authorization.json);
no server credentials or QA password appear in that file.

The operator returned `prepared=true`, `ready_for_approval=true` with the exact
plan SHA below. That preparation receipt confirms no worker, approval receipt
or new QA account was created **during preparation**, old evidence was preserved
and network rules were unchanged. Preparation success does not itself establish
a successful live traffic or inference test.
The successful expired trial and failed attempt
retain their original containers, files and deadlines. See the
[operator failure evidence](evidence/reliability-startup-failure.json) and
[fresh hosted database check](evidence/reliability-post-failure-supabase.json).
[Corrected bundle verification and private-transfer metadata](evidence/reliability-followup-preparation.json)
record the exact artifact hashes without including the temporary signed URL.

## Immutable scope

| Item | Prepared value |
| --- | --- |
| New trial ID | `f3fc3665-76e9-4cc5-b6e6-2c437873a6a4` |
| Canonical plan SHA256 | `80acdb44a931f6cfeba318d58b034b7232a3b7e1032866f6cd1827656536529d` |
| Host | `i-0be10e530045fc650`, m6i.2xlarge, us-east-2 |
| Image | `sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`, Linux amd64 |
| Provider/model | Explicit local SmolVLM2-500M, existing pinned revision |
| Worker limits | 8 GiB, 2 vCPU, no extra swap, 256 PIDs, one processing job |
| Time limit | At most 1,800 seconds from the later approval; shutdown reserve included |
| Network | Existing dedicated egress bridge; no public ports; IPv6 disabled |
| Queue | Fresh empty QA owner only; global false; old owners/jobs held |
| Gemini | Disabled; no provider fallback |
| Fault | One SIGKILL to the new worker's exact runner child during approved-source analysis |
| Measurement | Durable host-side cgroup samples every two seconds and final-snapshot acknowledgement |

[The corrected canonical plan](../deploy/worker/reliability-followup-plan.json)
pins all nine host code files and fourteen prior evidence files. The original
[failed plan](../deploy/worker/reliability-plan.json) remains byte-for-byte
unchanged; its historical code is retained in commit `75e3b83` and its installed
immutable EC2 directory. The new absolute deadline and QA identity are now
bound once in the separately authorized root-private approval receipt. EC2
launch binds that receipt to a write-once activation. Docker
restarts cannot recalculate or extend that deadline. Preparation cannot issue the
receipt, create a user, create/start a container or start a systemd unit.

The prior containers, their deadlines/receipts, private QA accounts/media and all
old evidence remain untouched. The corrected preparation bundle contains
fourteen hash-pinned evidence copies, including the failed admission and fresh
read-only hosted checks, installed in its `previous-evidence/` directory.
The existing JSON files in Git are unchanged. The new trial has separate cache, temporary data, gates
and reports. Only read-only pinned model assets and the existing file secret
are shared. Preparation checked secret-file metadata without reading its value.

## Commands on EC2

The hash-verified, private preparation-only block completed successfully on EC2.
It installed only the new immutable files after read-only host checks. Its
temporary download object was removed after the receipt; do not rerun that
download block. No image rebuild/transfer, GitHub token, registry login or
credential paste was needed. The commands below apply to the installed files.

Set task-specific shell variables once:

```sh
NC_RELIABILITY_TRIAL=f3fc3665-76e9-4cc5-b6e6-2c437873a6a4
NC_RELIABILITY_CTL=/etc/noetharaclipz-isolated/trials/$NC_RELIABILITY_TRIAL/code/reliability_host.py
```

**Safe now — show final status.** This does not read a credential or start
anything:

```sh
sudo -n python3 "$NC_RELIABILITY_CTL" status --trial-id "$NC_RELIABILITY_TRIAL"
```

Expected current stage: `closed`, Docker `exited`, exit code 0, one controlled
restart and `resource_coverage_complete=true`. The approved window is finished;
do not rerun its launch block or try to extend/reset its receipt.

**The separately authorized launch block was supplied.** It installs the actual
hash-verified root-private receipt and invokes the installed controller once.
No placeholder launch command is supplied. The expired receipt is invalid for
the corrected plan and cannot be used to obtain more time. Rerunning launch
cannot reopen an activated trial or recalculate its absolute deadline.

The launcher rechecks host headroom, stopped old container, existing services,
image, assets, network policy, protected row and fresh empty QA identity before
activation. It then starts only a dedicated transient monitor unit and one new
container, named `nccz-reliability-f3fc366576e9-worker`. It never runs the expired
container. A failed or expired activation cannot be reopened by rerunning launch.

**After an authorized launch — status and own-unit logs:**

```sh
sudo -n python3 "$NC_RELIABILITY_CTL" status --trial-id "$NC_RELIABILITY_TRIAL"
sudo -n journalctl -u nccz-reliability-f3fc366576e9 --no-pager -n 60
```

Wait for `ai_ready=true`, not merely `running=true`. The approved browser test
will upload the prepared long sample through the normal UI. The one controlled
fault happens automatically only when that exact source hash reaches real
analysis, with a valid first-attempt lease and enough time remaining. No manual
PID selection or broad process kill is required.

**Safe rollback — request a graceful stop of this new trial only:**

```sh
sudo -n python3 "$NC_RELIABILITY_CTL" stop --trial-id "$NC_RELIABILITY_TRIAL"
sudo -n python3 "$NC_RELIABILITY_CTL" status --trial-id "$NC_RELIABILITY_TRIAL"
```

Before launch, stop reports that no worker was started. During a trial it requests
shutdown; if the monitor is stale it captures remaining counters and stops only
the container whose new trial label matches. It never resets/cancels/deletes
jobs, removes evidence, touches the expired container, restarts another service,
flushes rules, changes security groups or restarts Docker. Recheck status until
the trial is closed. No `docker compose up` or old QA startup command belongs in
this procedure.

Public reports are under:

```text
/var/lib/noetharaclipz-isolated/trials/f3fc3665-76e9-4cc5-b6e6-2c437873a6a4/reports/
```

Use the status command or read `final.json`, `metrics-summary.json`,
`metrics.jsonl`, `crash-result.json`, `network-*.json` and partial
`network-attempt-*.json`. Do not paste
`crash-private.json`: it contains a short-lived lease token used to test stale
updates. Server credentials and QA passwords are never printed in reports.

## Monitoring and restart isolation

The monitor starts before Docker starts the new container and lives outside its
cgroup. It derives the real cgroup path from `/proc/<container-init-pid>/cgroup`
rather than assuming a cgroup parent. It records actual `memory.current`, kernel
`memory.peak`, memory events, CPU counters, quotas and PID counts. Empty/missing
measurements remain unavailable, not zero.

CPU peak means the maximum **observed interval rate**, where 100% is one core;
it is not an instantaneous hardware maximum. Counter domains/inodes distinguish
recreated cgroups from retained ones, so restart CPU time is not double-counted.
Every generation waits briefly after model processes end for a final host sample
and acknowledgement before exiting. Missing acknowledgements or generations make
coverage incomplete; they cannot produce a false complete measurement report.
The host files survive container crash/restart and normal shutdown. No monitoring
agent, subscription or paid service is installed.

Every container generation checks its actual kernel resource limits, creates a
fresh nonce and waits **before model or credential loading**. The monitor checks
the existing rule presence/order, public DNS/TLS and each private/IMDS/host/
gateway/non-HTTPS rejection with matching firewall counter increases. Only then
does it issue a short-lived root-owned grant for that nonce. Grants are mounted
read-only and cannot carry over to a restarted generation. Rule changes, stale
monitoring or revocation stop processing; the host controller never applies rules.

No unattended boot deployment is installed. If host/daemon restart removes
isolation or the monitor, the worker cannot receive a fresh grant. Durable
continuous-worker service/firewall ordering still needs its own reviewed rollout;
this test does not reboot a shared host or alter host-wide Docker settings.

## Worker-only crash test and normal website acceptance

After later approval, a fresh QA owner is created and tagged with this trial ID.
It must have been created after approval and have no preexisting projects. The
expired trial's account stays archived; only the new identity can process work.
The cloud-only issuer uses existing bound credentials and is deliberately not
run during preparation. Its private `.identified.json` record supplies the
browser test; passwords/server credentials are not sent in chat or the host plan.

The usual `scripts/await_ec2_qa.py` runs on the development machine with that
private account file and the new sample. It waits for real scoped readiness and
then calls the normal `scripts/acceptance.py`: sign in, upload, instructions,
Generate, real queue claim, automatic highlight, select/edit/save/refresh, normal
Export and authenticated private MP4 download/full decode. It starts no worker
and inserts no highlights. The existing frontend, cancellation, retries, leases,
RLS and provider provenance remain unchanged.

The host monitor will:

1. Match the actual long-video source SHA, first analysis attempt and current
   lease. Require container uptime of at least ten seconds and at least ten
   minutes left for fault injection/recovery. A write-once receipt permits one
   injection only; uncertain outcomes never retry the signal.
2. Validate new container/trial ownership, local mode and its exact health-file
   runner PID/cmdline. Signal only that runner child. It cannot signal PID 1,
   supervisor, host PID, old container or another application.
3. Capture generation metrics, observe nonzero exit and exactly one automatic
   Docker restart. Re-prove isolation with a new nonce before model readiness.
4. Let the real lease/visibility expire naturally. Observe the same job's second
   attempt and new lease token. A stale-token check must receive the expected
   database lease/finished-job error; an unrelated HTTP outage cannot count as
   successful rejection.
5. Require one completed local provenance record and genuine highlights for
   recovery success. The normal browser must still finish editing, queued export
   and private MP4 download. Verify the fixed deadline, service baseline, original
   row hash and complete resource coverage before calling the trial successful.

If there is no supported highlight, input validation fails, the monitor loses
isolation, or metrics/restart checks fail, the report must say so. No rendering
fixture or model switch may manufacture a pass. The existing 500M quality and
media-timing limitations remain; this is a reliability test, not an accuracy claim.

## Opt-in and queue release policy

- Default: held. There is no global consumer or global-enable command.
- This trial's opt-in is the separate, time-bounded approval plus a **fresh empty
  processing identity**. Existing SQL atomically filters claims to that owner.
  Old QA and normal-user jobs are outside that scope, even if they are retried.
- The protected job `9c5c8869-ec2e-4a3e-927d-697615bb58a3` is never claimed,
  cancelled, reset, deleted or processed. The entire row hash is checked before
  activation, periodically during the approved trial and at final verification.
- Stop/revocation removes processing permission, preserves leases for natural
  recovery and retains queued data. Normal user cancellation/retry remains in the
  existing authenticated application API.
- Existing-user or individual old-job release is **blocked** by
  `reliability_policy.existing_user_release`. The current RPC cannot safely
  enforce a per-job release list atomically; a read-then-claim filter is not an
  acceptable substitute. Before such a rollout, review a server-side release
  protocol with owner/job/source revision, explicit approval/audit record,
  revocation, hard protected-job exclusion and atomic claim checks. No SQL or
  migration was added/applied in this preparation.

## Longer authorized gaming sample

Prepared `test-results/supertuxkart-long-180s.mp4`: **180.000 s, 18,575,024 bytes**,
H.264/AAC, 640×360, 24 fps. SHA256:
`08ce51d71e20d7119a9b3800f1b152d6d98d672ff31974c42edf28ade03861cb`.
Full FFmpeg decoding passed and a sampled frame was manually checked as actual
kart racing. The two normal browser uploads below processed this exact source:
one genuine multimodal inference run with crash recovery and one cached repeat.

Source: [SuperTuxKart 2.x GP with 24% handicap and road tracks](https://commons.wikimedia.org/wiki/File:SuperTuxKart_2.x_GP_with_24%25_handicap_and_road_tracks_(open_source_Mario_Kart-like_Linux_game).webm),
**kimden STK**, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Used the
official 240p derivative, a contiguous source interval from 120 to 300 seconds,
scaled/transcoded for the application. No looping, concatenation or invented
events. Attribution/license and these modifications must accompany redistribution.
The normal browser upload uses this prepared cloud-workspace file; no source
fixture is inserted directly into the database during preparation.

## Preparation verification and next decision

### Actual authorized follow-up results

The operator's [05:41 monitor report](evidence/reliability-followup-monitor-0541.json)
confirms one automatic restart of container
`6c66cb349cbf21ff16ee168c079289a6e17712f3beb81f2eb1da724a71e5db6e`
after the one guarded runner SIGKILL. Both container generations proved actual
8 GiB / 2 vCPU / no-swap / 256-PID controls, IPv6 disabled, public DNS/TLS, and
all seven matching private/IMDS/host/gateway/non-HTTPS REJECT-counter increases.
The old containers remained exited with zero restarts, and all existing services
matched their baseline. Reclaim was observed after **118.672 seconds**, with a
new token, second attempt and stale-token rejection.
The [05:54 host snapshot](evidence/reliability-followup-monitor-0554.json)
subsequently confirms `status=completed`, `recovery_verified=true`, exactly one
restart, unchanged pinned code and the original fixed stop time. The active
grant and missing final report at that pre-deadline timestamp are expected.

| Normal website run | Upload + analysis | Full workflow | Actual downloaded file |
| --- | ---: | ---: | --- |
| 180 s gaming; forced crash/recovery | 286.988 s | 310.965 s | 9.9 s H.264/AAC MP4; 2,044,140 bytes |
| Same source/prompt; sequential cached repeat | 18.267 s | 43.574 s | Same decoded MP4 SHA256 |

The first run recorded genuine new local multimodal inference: **3,711 input
and 12 output tokens**, one completed local provenance record, and one automatic
highlight at **151.967–161.967 s**. The model compared eight four-frame candidate
videos plus a none option. The result reports measured zero speech segments,
five audio events and one scene boundary; its relative choice score 0.354 is not
calibrated accuracy. Prepared-media and transcript caches survived the crash.
The repeat used the prepared, transcript and analysis caches and recorded zero
new inference tokens, preserving original inference provenance separately.
These timings include upload, queue, recovery, edit and rendering overhead;
they are not a controlled model-only speedup measurement.

Both browser runs selected the generated highlight, played it, saved an edit,
refreshed, used the normal Export button, and privately downloaded and decoded
the queued FFmpeg render. The persisted edit trims its start to 152.1 s and uses
9:16 framing/captions. Output SHA256:
`971241b594bc54bb617d5b753e2ab32f3cce64a31cc00fa79cf0599ee949e8e5`.
No highlights were inserted by a fixture or rendering shortcut. The frontend was
the existing development server against hosted Supabase and the real EC2 worker;
the public website was not deployed. These are QA-account results.

[Crash-run browser evidence](evidence/reliability-followup-live-acceptance.json),
[cached repeat](evidence/reliability-followup-cached-acceptance.json), and
[live security evidence](evidence/reliability-followup-security.json) preserve
the actual results. Security checks deny anonymous/authenticated privileged
worker calls (401/403), cross-owner rows and private source access/signing, and
public rendered-file access. Owner downloads work. Duplicate Export returns the
existing job; forged completion and invalid uploads are rejected. No account,
worker or global claim is created by those security checks.

At **05:50:50 UTC**, [read-only hosted checks](evidence/reliability-followup-api-checks.json)
confirmed all four QA jobs completed, one highlight/clip per project, only local
provider records with zero recorded provider cost, no active unfinished leases,
and the original upload's identical full row: queued, zero attempts, no lease
or cancellation. Temporary preparation and approval download objects were
removed after receipt, with unrelated objects untouched.

The [final collector](evidence/reliability-followup-final.json), checked at
**06:03:13.892 UTC**, confirms automatic deadline stop at **06:03:11.648 UTC**,
inside the configured shutdown reserve before the fixed 06:04:44 deadline.
Container exit is 0, no OOM, restart count one, and the processing grant is
absent. Controller error/cleanup fields are null. Both old containers remain
exited with zero restarts and unchanged start/finish times; existing services
match admission, and the protected upload remains unchanged.

At **06:07:51 UTC**, [fresh hosted checks after the fixed deadline](evidence/reliability-followup-post-shutdown-supabase.json)
confirmed `online=false`, `ai_ready=false`, four completed QA jobs, zero active
unfinished leases and the protected upload's identical queued/zero-attempt row.
The RPC's detail falls back to an older global heartbeat description after the
scoped row expires; that text is stale, and no heartbeat was issued by this check.

**781 durable samples** cover both generations, each with a captured final
snapshot and distinct CPU counter domain. Kernel peak RAM is
**2,719,240,192 bytes (2.53 GiB)**, sampled peak CPU **205.439%** (one core =
100%) and cumulative CPU **306.891388 seconds**. The controller confirms
`resource_coverage_complete=true`, `final_snapshots_complete=true`, two verified
network generations and completed-job `recovery_verified=true`. Preserve the
observed CPU rate without clamping; both generations independently proved a
200000/100000 CPU quota. Interval CPU samples are not instantaneous maxima.
These totals include preprocessing, crash/recovery, the cached repeat and idle
time; they are not a sustained throughput or calibrated model-accuracy benchmark.

The on-failure:3 policy does not restart the normal exit. The dedicated monitor
was launched with `Restart=no`, its grant is removed, and the unchanged pinned
entrypoint checks the original expiry before models/credentials on any new
generation. No trial receipt/deadline or old container was reset or restarted.
Continuous/global mode remains disabled; safe boot ordering and atomic
existing-owner opt-in/release remain separate rollout requirements.

**229 worker tests passed; one optional sample test skipped; Ruff passed.** The
reliability checks cover immutable limits, absent approval/no startup, expired/stale
grants, fresh-owner/old-backlog rejection, scoped signal targets, real harmless
process-group shutdown, final-sample ordering and resource counters across reset
and retained cgroups. These unit/simulation checks do not substitute for a live
new trial. Seven additional regression cases replay the operator's actual raw
DROP rules, reject a newly occupied probe IP, require each target's own counter
increase, reject timeouts/incorrect responses/decreasing counters and retain
partial failure evidence. Application/worker-image sources and the frontend are
unchanged. The existing image digest is reused with newly hash-pinned read-only
startup scripts; this is not a claim that the mounted configuration is identical.

At **05:24:19 UTC**, hosted read-only checks confirmed the protected upload's
whole row remained identical: queued, zero attempts, no lease and no cancellation.
There were no active unfinished leases or projects for the failed trial's fresh
owner. Its startup-only measurements (26,980,352 bytes peak memory; 0.704408 CPU
seconds; 32.684% sampled peak CPU, incomplete final snapshot) are **not model
benchmarks**. Longer-input browser processing and final deadline/shutdown
resource coverage now passed as above.

The corrected EC2 preparation receipt passed and the user separately authorized
this exact plan SHA, the fixed **05:34:44–06:04:44 UTC** window, one fresh
processing owner, long gaming input and one worker-only fault. This does not
authorize continuous/global processing, old-upload release, merge, publication,
paid services, a larger model, resize or other infrastructure changes. None of
those actions occurred during preparation.
