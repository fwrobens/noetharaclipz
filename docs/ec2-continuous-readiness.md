# Continuous SmolVLM2-500M readiness — 9 November 2026 UTC

**Recommendation: keep the existing EC2 instance and 500M model; hold continuous
production/global processing until the remaining lifecycle and monitoring checks
pass.** The expired QA trial is closed and must not be restarted or extended.
No new infrastructure, larger model or paid inference is recommended.

**05:07 UTC follow-up:** the separately authorized monitored attempt stopped at
its pre-model network gate. Docker's raw PREROUTING drops on live container IPs
prevented the diagnostic's filter counter from increasing. The network policy
remained unchanged; no AI work or crash injection ran. The corrected probe uses
unused private destinations, rejects allocated/raw-shadowed targets read-only,
and still requires matching counter increases. All 229 worker tests pass, with
one optional skip. The operator has now confirmed successful installation of
the corrected immutable configuration with matching plan SHA; no worker,
approval receipt or QA account was created. Its temporary private download was
removed after receipt. Separate start authorization remains pending. The failed attempt
and its fixed 05:32:30 deadline are preserved. Its short startup measurements do
not supply the missing AI peak-resource or crash-recovery evidence. See the
[current trial procedure and actual results](reliability-trial.md).

**05:50 UTC authorized follow-up:** corrected trial
`f3fc3665-76e9-4cc5-b6e6-2c437873a6a4` is active under the fixed
**05:34:44–06:04:44 UTC** approval. The operator confirmed actual startup,
one automatic worker-only crash restart, two independently passing kernel and
network proofs, 118.672-second reclaim and stale-token rejection. The 180-second
gaming job completed on attempt two; the normal website then saved/refreshed an
edit, queued Export and privately downloaded a decoded MP4. A sequential cached
repeat also passed (43.574 s total; zero new inference tokens), as did live
auth/storage, duplicate prevention, invalid-input and protected-row checks.
All four QA jobs completed with no active unfinished leases. Provisional peak
RAM was 2.53 GiB and sampled CPU 205.439%, with an independently proved 2 vCPU
quota. The 05:54 host snapshot confirms completed-job `recovery_verified=true`
and exactly one restart. Final deadline exit and complete resource snapshots
still await the waiting read-only collector. Continuous/global mode
remains disabled. [Actual follow-up evidence and limits](reliability-trial.md#actual-authorized-follow-up-results).

The normal browser workflow already passed on three distinct authorized videos
and a cached repeat. [Workflow results and quality limits](ec2-live-qa.md) remain
valid. This review adds actual shutdown/host evidence; it does not rerun the
worker or imply that a continuously running service was enabled.

## Final post-trial evidence

The operator ran the hash-verified read-only collector at **03:29:39 UTC**. The
agent has no direct EC2/SSM execution connection; host observations below come
from that pasted JSON, with selected fields preserved in
[the host evidence](evidence/ec2-qa-shutdown-host.json).

| Check | Actual result |
| --- | --- |
| Container | `noetharaclipz-isolated-worker-1`, ID `fbe3d4f4d9b1c95cb3cae77278a40a5cf5d52c77435eccdc3d14c60d17c06f99` |
| Image | Reviewed manifest `sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759` |
| Started | 00:22:12.562 UTC |
| Finished | **00:50:37.710 UTC**, before the 00:52:12 deadline |
| Docker state | `exited`, running/restarting false, PID 0, exit code **0** |
| Crash/OOM/restarts | No OOM kill, empty Docker error, restart count **0** |
| Shutdown log | `qa_window_stopped=true`, logged at 00:50:37.701 UTC, original deadline unchanged |
| Actual startup kernel controls | 8,589,934,592 memory bytes; CPU quota 200000/100000; no extra swap; PID cap 256; all checks passed |
| Existing applications | All six running; five healthy; REST has no configured Docker health check, as in the baseline |
| Original upload | Full-row digest unchanged; queued, zero attempts, no cancellation or lease |
| Active unfinished leases / unfinished QA jobs | **0 / 0** at the agent's 03:29:13 UTC REST check |

All existing service start times remain before the QA trial. Noethara staging's
restart count is zero. Supabase Auth's count of two was already present in the
operator's pre-trial report; its start time remains 8 November, 16:14:46 UTC.
The collector did not restart services, enter containers, read credential files,
change firewall rules or alter Docker settings.

The stopped QA container reports health `unhealthy`. This label alone does not
show a runtime crash: upstream [Moby closes its health monitor with an unhealthy
compatibility state](https://github.com/moby/moby/blob/v28.5.2/container/health.go#L70-L81).
That reference explains why stopped health labels need care; it is not an audit
of this host's exact Docker build. The actual exit code, PID, no-OOM state and
deadline log establish this clean stop. Do not restart a stopped QA container to
clear its health label. Retained Docker lifecycle events were empty and may be
incomplete; zero restarts comes from Docker inspect, not the empty event list.

The agent's retained monitor independently observed a fresh scoped
`Worker stopped` heartbeat at 00:50:41 UTC. The user's independent private-table
check at 00:59 UTC found the last heartbeat at 00:50:37, no recent scoped
heartbeats and no active leases. The later REST check confirmed the protected
job and zero active leases without calling a claim or heartbeat function.
[Database and monitor evidence](evidence/ec2-post-trial-supabase.json) distinguishes
those sources; the agent did not query the private table directly.

## Restart safeguards now verified

Docker's actual policy is `on-failure` with three maximum retries. A normal exit
code of zero does not trigger that policy. The container has not restarted.

The installed entrypoint is the reviewed deadline wrapper. Its SHA256 matches,
it is root-owned mode 0440, and its environment retains the original deadline,
QA owner/trial, explicit local provider, Gemini false and global approval false.
After expiry the unchanged wrapper exits zero **before** loading a credential,
model or supervisor. The startup controller also refuses an existing trial
receipt rather than resetting it. Unit tests exercised expiry and rejected
changed scope/deadline settings; the EC2 container was never started to test this.

These safeguards prevent automatic resumption of processing under the verified
configuration. A root administrator can deliberately replace the configuration;
this review does not claim to make privileged manual changes impossible. No new
deadline, Compose override, scheduled start or restart policy was installed.

## Actual CPU/RAM consumption

Historical peaks are **unavailable from the retained Docker/cgroup evidence**.
The stopped container's inspected cgroup paths no longer retain `memory.peak`
or `cpu.stat`; no earlier sampling record was supplied. Docker's stopped stats
cannot reconstruct usage. The proven 8 GiB / 2 vCPU limits are not measurements
of consumption, and no OOM event does not establish a peak.

For the next separately authorized trial, start a small host-side sampler before
the worker. Record `memory.current`, `memory.peak`, `memory.events`, `cpu.stat`,
time and container start generation every two seconds into a bounded private
file. Preserve samples before container stop/removal and across crash restart,
handling counter resets explicitly. CPU usage deltas divided by elapsed time
measure average cores over an interval; cumulative `cpu.stat` is not peak CPU.
This can use existing tools and disk, without CloudWatch agents or paid services.
No monitoring service was installed in this review.

## Reviewed future crash-restart procedure — not executed

This is a plan for a **new, separately authorized bounded QA trial**, not
permission to start one now. Do not use the expired container or rewrite/delete
its receipt to reopen the old window. The current controller intentionally
rejects reuse; prepare and review a new trial configuration/receipt first.

1. Preserve the old exit/log evidence. Prepare a fresh trial UUID, immutable
   deadline and dedicated writable paths. Reuse only the reviewed image and
   pinned read-only assets. Keep the same one temporary QA owner, 8 GiB / 2 vCPU,
   one active job, no ports, Gemini false and global approval false. Confirm no
   other AI worker is active and retain the original upload's complete row hash.
2. After renewed authorization, recheck host headroom, exact image, kernel quotas,
   owned network/firewall policy and current service start/restart/health state.
   Start metrics collection first. No daemon/host restart or other service change
   belongs in this test.
3. Start only the newly approved owner-scoped worker. Wait for real model-ready
   scoped heartbeat and at least ten seconds of container uptime so Docker's
   restart-policy monitoring has become active.
4. Upload authorized footage through the normal UI. Use a new prompt if necessary
   to require fresh inference. Wait for its actual analysis job and live lease.
   Record job ID, attempts and a hash of the lease token; do not publish tokens.
5. Verify the **new** container ID, project/trial labels, image and deadline. Read
   its own local health file to identify the exact runner PID. Inject one failure
   only into that runner child. Do not kill Docker's PID 1, the host, other Python
   processes or the daemon. `docker kill` is not the desired fault injection:
   explicit Docker stops/kills can suppress automatic policy restart.
6. Observe the supervisor and wrapper exit nonzero, Docker automatically restart
   the same new container, and its restart count increase to one. Model readiness
   must recover with the same immutable deadline and owner. Docker health status
   alone does not restart anything; the supervisor must actually exit.
7. Allow the abandoned lease/queue visibility to expire naturally. The real
   worker must reclaim the same QA job with a new token and next attempt, reject
   stale updates, and create one final highlight/provenance result. Do not edit
   leases, shorten database timeouts or claim the global queue for the test.
8. Finish normal Edit/Save/Export/private Download. Recheck original-row hash,
   one-active-job behavior, other services and retained resource samples. Verify
   the new trial also exits zero at its own deadline and stays stopped.

The prior 123.138-second abandoned-lease test already verified real queue
recovery, stale-token rejection, invalid-media failure and retry limits. It did
not inject a Docker/worker process crash; that distinction remains explicit.
The existing local standby smoke script must not be redirected at this expired
EC2 trial or substituted for the reviewed active-worker test.

## Remaining gates before continuous processing

1. **Final measured lifecycle evidence:** the newly authorized 180-second trial
   has demonstrated automatic restart/reclaim and the real browser workflow;
   retain the final deadline exit and both generations' final resource snapshots.
   The intermediate kernel peak is measured, but final coverage is still open.
   One longer gaming source is not a continuous-load or 300-second maximum-input
   capacity benchmark.
2. **Safe boot and recovery ordering:** review and implement worker-specific
   firewall/network persistence and startup preflights before queue access. The
   present QA approval does not authorize unattended host/daemon reboot startup.
   Docker alone will not restore the reviewed isolation policy in the required
   order. Do not reboot this shared host to test it without separate approval.
3. **Explicit queue scope:** keep global consumption off. The current claim API
   scopes by owner; global claiming would make the protected queued upload
   eligible. Continuous operation should begin with the dedicated QA/opt-in owner
   scope. A global rollout needs an explicitly approved release/hold/exclusion
   policy for the old upload; no database resource was changed to create one.
4. **Operational readiness:** retain logs/metrics, alert on stale readiness and
   resource pressure, preserve temporary-file cleanup, define recovery/rollback
   and review storage/egress allowances under expected traffic. Do not enable
   paid monitoring or providers as a side effect.

### Startup-order review of the existing configuration

- `compose.yaml` starts in standby and its supervisor loads no credential or
  queue in that mode. Its `unless-stopped` policy can resume a container after
  a Docker/host restart. Active continuous rollout therefore needs a dedicated
  host controller that verifies isolation before permitting model/credential
  loading; the base Compose profile is not yet approved for that rollout.
- The active QA controller uses `on-failure:3`, a fixed expiry and a separate
  transient monitor with `Restart=no`. Every generation must obtain a fresh
  root-owned, short-lived nonce grant after kernel and live network proofs.
  Revocation/staleness stops processing. The crash trial proved the new-generation
  path; host/daemon reboot ordering was not tested or authorized.
- A future worker-specific boot service should require Docker, dedicated mounts
  and a reviewed worker-isolation unit before startup. It must check bridge
  ownership/collisions, restore only its approved hooks/rules if authorized,
  verify their actual order and rejection counters, then issue fresh grants.
  Periodic verification must remain active after startup. Do not flush shared
  chains, alter host-wide Docker settings or reuse another app's network.
- The current trial's hard 1,800-second policy and receipt are retained intact.
  A continuous rollout needs a newly reviewed controller, scope/revocation
  configuration, bounded restart/backoff and durable log/metric retention. It
  cannot be obtained by disabling this trial's deadline or reusing its receipt.
- Rollback revokes the dedicated grant and gracefully stops only the matching
  worker container/controller, leaving model assets, evidence, queued work and
  existing services in place. Global consumption and existing-owner backlog
  release remain blocked until their separate atomic server-side opt-in policy
  is reviewed and authorized. No boot unit, firewall restoration or database
  policy was installed during this review.

Model quality is also limited: unverified narration can hallucinate, rank scores
are not calibrated accuracy, and a quiet derivative showed a small media-tool
duration discrepancy. Those findings remain in the workflow report; they were
not concealed by installing a larger model or changing the reviewed image.

The existing **m6i.2xlarge** remains the best hosting candidate for SmolVLM2-500M
with one job, 8 GiB and 2 vCPU. No resize or new paid compute is justified by the
current evidence. A limited continuous owner-scoped pilot is appropriate only
after the new monitored restart trial and startup-isolation review pass. Global
production processing is **not ready to enable now**. This is a readiness
recommendation, not a request or authorization to restart the expired worker.

Validation for this review: **178 worker tests passed, one optional sample
skipped; 43 targeted inspector/deadline checks and Ruff passed.** Application and
worker runtime sources/image were unchanged; the previously passing frontend,
TypeScript, build and lint results remain applicable. The only staged handoff was
a 10,864-byte private read-only inspector, deleted after its receipt. No QA
restart, global processing, migration, merge, publication or paid-service
activation occurred.
