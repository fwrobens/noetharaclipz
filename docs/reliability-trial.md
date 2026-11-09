# Final reliability trial: prepared, not authorized or started

The existing m6i.2xlarge remains the host. The reviewed SmolVLM2-500M image and
pinned Whisper assets are reused; no new image, larger model, infrastructure or
paid service is required. Normal website clipping already passed on EC2.
This stage prepares the remaining monitored crash/recovery test.

The operator has run the preparation-only command on EC2 and returned:
`prepared=true`, `ready_for_approval=true`, `worker_started=false`,
`approval_receipt_created=false`, `new_qa_account_created=false`,
`old_evidence_preserved=true`, `network_rules_changed=false`.
That is **preparation success**, not a new live reliability result. No start
approval is inferred from the preparation receipt.

## Immutable scope

| Item | Prepared value |
| --- | --- |
| New trial ID | `bebbf5ad-094f-4b6f-964f-c7ac22e1f760` |
| Canonical plan SHA256 | `f61e6a59341a82bfb136a098f9fd0465590cad727b31a8f7170bb3d8c9630947` |
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

[The canonical plan](../deploy/worker/reliability-plan.json) pins all nine host
code files and twelve prior evidence files. The absolute deadline and new QA
identity deliberately do not exist yet. After separate authorization they are
bound once in a root-private approval receipt and write-once activation. Docker
restarts cannot recalculate or extend that deadline. Preparation cannot issue the
receipt, create a user, create/start a container or start a systemd unit.

The prior container, its deadline/receipt, private QA account/media and all old
evidence remain untouched. Twelve evidence copies were verified and installed
under the new configuration's `previous-evidence/` directory. The old JSON files
in Git are unchanged. The new trial has separate cache, temporary data, gates
and reports. Only read-only pinned model assets and the existing file secret
are shared. Preparation checked secret-file metadata without reading its value.

## Commands on EC2

The private preparation bundle was hash-verified and installed through SSM; its
temporary download object was removed after the successful receipt. No GitHub
token, registry login, release asset, image upload or service credential paste
is needed. This file is the command reference after installation.

Set task-specific shell variables once:

```sh
NC_RELIABILITY_TRIAL=bebbf5ad-094f-4b6f-964f-c7ac22e1f760
NC_RELIABILITY_CTL=/etc/noetharaclipz-isolated/trials/$NC_RELIABILITY_TRIAL/code/reliability_host.py
```

**Safe now — show preparation status.** This does not read a credential or start
anything:

```sh
sudo -n python3 "$NC_RELIABILITY_CTL" status --trial-id "$NC_RELIABILITY_TRIAL"
```

Expected current stage: `prepared_not_authorized`, `worker_started=false`.

**Future only — do not run until separate authorization and a verified receipt
are supplied.** There is no approval file now; the following intentionally
cannot launch this prepared trial. A later handoff will install the root-private
receipt and supply its real SHA, without exposing credentials:

```sh
sudo -n python3 "$NC_RELIABILITY_CTL" launch \
  --trial-id "$NC_RELIABILITY_TRIAL" \
  --approval-file "/etc/noetharaclipz-isolated/trials/$NC_RELIABILITY_TRIAL/approval-receipt.json" \
  --approval-sha256 'ISSUED_ONLY_AFTER_SEPARATE_AUTHORIZATION'
```

The launcher rechecks host headroom, stopped old container, existing services,
image, assets, network policy, protected row and fresh empty QA identity before
activation. It then starts only a dedicated transient monitor unit and one new
container, named `nccz-reliability-bebbf5ad094f-worker`. It never runs the expired
container. A failed or expired activation cannot be reopened by rerunning launch.

**After an authorized launch — status and own-unit logs:**

```sh
sudo -n python3 "$NC_RELIABILITY_CTL" status --trial-id "$NC_RELIABILITY_TRIAL"
sudo -n journalctl -u nccz-reliability-bebbf5ad094f --no-pager -n 60
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
/var/lib/noetharaclipz-isolated/trials/bebbf5ad-094f-4b6f-964f-c7ac22e1f760/reports/
```

Use the status command or read `final.json`, `metrics-summary.json`,
`metrics.jsonl`, `crash-result.json` and `network-*.json`. Do not paste
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
kart racing. It has not been analyzed by AI or submitted to the queue.

Source: [SuperTuxKart 2.x GP with 24% handicap and road tracks](https://commons.wikimedia.org/wiki/File:SuperTuxKart_2.x_GP_with_24%25_handicap_and_road_tracks_(open_source_Mario_Kart-like_Linux_game).webm),
**kimden STK**, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Used the
official 240p derivative, a contiguous source interval from 120 to 300 seconds,
scaled/transcoded for the application. No looping, concatenation or invented
events. Attribution/license and these modifications must accompany redistribution.
The normal browser upload uses this prepared cloud-workspace file; no source
fixture is inserted directly into the database during preparation.

## Preparation verification and next decision

**222 worker tests passed; one optional sample test skipped; Ruff passed.** The
44 new checks cover immutable limits, absent approval/no startup, expired/stale
grants, fresh-owner/old-backlog rejection, scoped signal targets, real harmless
process-group shutdown, final-sample ordering and resource counters across reset
and retained cgroups. These unit/simulation checks do not substitute for a live
new trial. Application/worker-image sources and the previous frontend are unchanged.

EC2 preparation passed, so this new plan is **ready for separate approval**.
Approval should cover only this exact plan SHA, at most thirty minutes, the new
single processing owner, long gaming input and one worker-only fault. It does not
authorize continuous/global processing, old-upload release, merge, publication,
paid services, a larger model, resize or other infrastructure changes. None of
those actions occurred during preparation.
