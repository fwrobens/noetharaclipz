# Proposed 24-hour owner-scoped EC2 pilot — preparation only

Status: **PREPARATION ONLY; NOT STARTED; NO NEW OPERATOR APPROVAL**.
The 2026-11-09 21:00–21:30 UTC pilot ended safely at 21:29:46 UTC.
Do not restart, edit, extend, renew, or reuse its expired deployment receipt,
owner consent generation or signed active manifest. This document is a plan,
not an authorization to activate processing or to enable boot startup.

## Current preparation (November 9, after commit 6a3c63b)

New deployment ID: `c25d8492-56fb-4c56-a519-e9a9e4246525`.
Intended pilot owner: `21b61ad1-bda4-4abd-ac35-7a0bf477ed69`.
The existing identity was authenticated successfully; its previous consent
generation is expired and will not be reused. **Fresh explicit owner consent
was authenticated and recorded at 22:24:37 UTC**, generation
`6b13bb7a-5b9b-4564-80d8-3904872d8c01`. Operator approval and expiry remain
null; processing authorization is false. See [owner consent](evidence/continuous-24h-owner-consent.json).
All **23 fresh EC2 preflights passed at 22:28:58 UTC** after the collector fix.
The immutable review plan is prepared; operator approval, installation and
startup are still **not authorized or performed**.

| Review item | Exact proposed value |
| --- | --- |
| UTC window | **2026-11-09 23:00:00 → 2026-11-10 23:00:00** (86,400 seconds) |
| Launch permitted | 23:00:00–23:04:59 UTC November 9; no waiting/extension |
| Disabled candidate SHA256 | `0d3dd0f3e1ce7a74712bb555f85104e4c661543e20677a652882bc47bd277bb8` |
| Activation manifest SHA256, only after approval | `3918b9eb1dee06597852c016a7098a873eea914bbac8afa151557cda2c34dda0` |
| Immutable review plan SHA256 (canonical JSON) | `1b0e2436c5a93b65ce73e4cfabfd8625ad87c4c5019458605ada6e85f2875912` |
| Kernel limits required at startup | 8 GiB, 2 CPU, no extra swap, 256 PIDs, one job |
| Owner/provider | This fresh pilot consent only; pinned local SmolVLM2-500M |
| Boot/global/Gemini | Disabled; no reboot test or general-user processing |

[Disabled candidate](evidence/continuous-24h-manifest-candidate.json) and
[review plan](evidence/continuous-24h-review-plan.json) are the exact review
artifacts. The activation digest is precomputed from only the candidate's
approval flag/reference change; it does not assert approval exists. No active
manifest or authorization object has been installed/issued. The launcher also
requires a separately issued private receipt, not just a true flag in a JSON.

The proposed installation scope is restricted to this new deployment's
configuration/data/report paths, the dedicated `continuous/current` symlink,
stopping the old isolation oneshot and starting the existing reviewed worker
unit without enabling it. It reuses the existing image, models, key file and
identical installed units. Failure rollback may revoke only the new consent
and stop only these dedicated worker units. No host-wide Docker/network
configuration, existing services, old trial files, queued-job release or
database schema changes are authorized. The existing instance adds no new
infrastructure; storage/egress remain subject to existing allowances.

Read-only Supabase checks at 22:06:27 UTC confirmed protocol v2,
`future-jobs-only-v1`, revocation/exclusions/audit enabled and global claims
disabled. The original upload is still queued with zero attempts and the exact
previous whole-row hash. No migration was applied.
At 22:23:01 UTC, a further hosted read verified **zero active leases** and the
original row again. It exercised the launcher's active-lease query against the
actual `lease_until` column; a prior read-only query typo was corrected before
any deployment. See [live preparation evidence](evidence/continuous-24h-supabase-preparation.json).

The new private preparation handoff reuses the **unchanged** reviewed 25-file
worker/controller overlay and both unchanged systemd units. It does not rebuild
the image or rerun model benchmarks. Source bundle SHA256:

`564a5b6a5de0664448737e0c5291c30a4d1ff2074be096b08711dce11fb381d8`

The [private handoff receipt](evidence/continuous-24h-private-preparation.json)
records its hashes and verified public-access denial, without a signed URL or
credentials. The temporary private download was read back and verified; the
operator received and verified all files at 22:23:20 UTC in SSM. The
receiver creates only a new private preparation directory under `/var/tmp`,
leaving all previous deployment/configuration/evidence paths unchanged.

The new [read-only collector](../scripts/inspect_continuous_24h_host.py) extends
the previously reviewed admission checks for the now-installed, disabled units:

- Pinned Docker image, actual SmolVLM2 and Whisper weight-file SHA256 values,
  source hashes, available RAM/disk, cgroup support, existing workloads and
  scoped firewall ordering. It loads no models and runs no containers.
- All four older containers stopped, closed/expired previous continuous
  manifest, removed grant and unchanged old evidence.
- Exact installed unit hashes, no loaded drop-ins or pending daemon reload,
  both units disabled at boot and no continuous worker running.
- All six expected Noethara/Supabase containers present and healthy according
  to their existing checks; the REST container has no Docker healthcheck.

The preparation receiver cannot read the credential file, issue approval,
install a systemd unit, change firewall rules or execute a container. The
separate [24h launcher](../scripts/launch_continuous_24h_pilot.py) is prepared
and tested locally but has not run on EC2.

The [initial EC2 check](evidence/continuous-24h-ec2-initial-preflight.json)
passed 22 of 23 checks at 22:23:24 UTC: 28.78 GiB available RAM, 45.64 GiB
free disk, low CPU, correct image/model-weight hashes, unchanged services and
old evidence, isolation and both units disabled. The remaining check refused
to assume that a missing `DropInPaths` property meant no drop-ins: systemd
omits empty properties without `--all`. The corrected collector explicitly
requests all properties; it does not relax the empty-value check. The original
source/report are retained; a [preparation-only recheck](../scripts/recheck_continuous_24h_host.py)
writes new diagnostic files alongside them. No unit or firewall fix is needed
or attempted. The [corrected live check](evidence/continuous-24h-ec2-preflight.json)
then passed all 23 gates with explicitly empty drop-in paths, no daemon reload
needed, 28.80 GiB available RAM and 45.64 GiB free disk. Its canonical report
SHA256 is `ebbad19cc4658d682b6248f473f496208574830cf619be41d7e151913d4b66c5`.
Both the failed and passing reports remain on EC2. The final launch repeats
admission and checks the passing report/helper hashes before credential access.

## Exact launch gating and SSM disconnection

The final review plan will bind the fresh consent generation, disabled candidate
manifest hash, prospective activation-manifest hash, exact UTC start/expiry,
private source receipt and explicit installation scope. Computing a prospective
activation hash is not approval: no active manifest is installed or processing
approval requested without the separately issued authorization record.

After explicit user approval, an immutable authorization JSON may be created
once in the existing private bucket. It binds both hashes, owner, consent,
deployment and UTC window. The single signed SSM launch command verifies its
own code/payload, repeats fresh host checks, then reads that exact private
authorization using the existing EC2 file credential. Missing authorization
returns without installation, processing approval or startup. No new credential,
public object or paid resource is needed.

The approved installer may only:

1. Install the new immutable configuration and dedicated data/report directories.
2. Stop the old worker's `RemainAfterExit` isolation oneshot while its worker is
   already inactive. It must not restart the expired worker.
3. Atomically move the dedicated `continuous/current` symlink from the verified
   expired deployment to the new one. It reuses the identical installed unit
   files and does not rewrite the old configuration or evidence.
4. Request operator approval for this fresh owner/consent until the exact expiry.
5. Submit **`systemctl start --no-block noetharaclipz-continuous.service`**.
   Systemd orders isolation before the controller; the controller verifies live
   quotas and denial counters before granting queue access. It owns all worker
   execution, sampling, restart/backoff, logs and final shutdown.

The SSM command returns a launch-request receipt promptly. That receipt does
**not** assert AI readiness or completed processing. Closing SSM afterward does
not stop the service or monitoring. No foreground worker, `nohup`, shell
background job, terminal wait loop, keepalive, timer or boot enable is used.
Launch is allowed only within the first five minutes of the reviewed window;
an early/late command fails without waiting or extending the expiry. If review
or transfer takes longer, prepare a new disabled manifest for review.

On an observed installation/start failure, rollback removes the new grant,
latches that deployment, stops only the two dedicated worker units, revokes any
new processing approval and restores the old symlink only after a successful
stop. It never restarts the expired deployment or deletes either evidence set.
Cleanup still attempts service stop/server revocation if the disk cannot write
the local failure latch. A launch-attempt receipt prevents automatic retries.
If SSM disconnects midway through installation, inspect retained receipts and
service state on reconnect; do not rerun the installer or clear latches blindly.

Both units must remain **disabled at boot**. An EC2 reboot ends this trial's
availability; boot enable/reboot recovery testing requires separate approval.

## Persistent evidence and local verification

The reviewed controller retains `reports/status.json`, `controller.log`,
`metrics-summary.json`, rotating raw cgroup samples, generation network proofs,
installation/approval receipts and Docker logs under the new deployment ID.
These files and their monitor survive an SSM disconnect. Lifetime peak RAM,
sampled peak CPU, CPU totals and sample counts persist across controller and
container restarts. Raw cgroup samples are bounded to **20 MiB** and can rotate
during 24 hours; do not claim every original sample remains available. Controller
transition logs, lifetime summaries and independent start/interim/end snapshots
must support the complete-window assessment. No external alert destination has
been configured.

Local verification: **353 worker tests passed, one optional sample test
skipped**; **56 focused 24h tests passed** after the read-only collector fix.
Ruff and diff checks passed. Tests exercise refusal of expired/reused consent,
scope/hash/time changes, missing approval, boot/global enable attempts,
nonblocking systemd startup, preservation/rollback and cleanup disk failures.
They do not start an EC2 worker or substitute for fresh live preflights.

## The AWS SSM shell may disconnect — deployment must not depend on it

Use a root-managed `systemd` service for the pre-reviewed
`noetharaclipz-continuous.service` and its ordered
`noetharaclipz-isolation.service`, **not** a foreground Python process,
background `&`, `nohup`, `tmux`, or a hanging SSM session. Once an
authorized service is started via `systemctl start`, the service runs
independently of the SSM session and continues when SSM disconnects or becomes
idle. The controller and monitor own worker execution, restarts, resource
sampling and durable logs, not the terminal.

A session disconnect is **not** an EC2 reboot. For this 24-hour trial keep
the new worker service **disabled at boot** unless separately authorized
for reboot-resilient operation and full isolation-before-queue boot ordering
has been demonstrated. If the host reboots with the service disabled, the
pilot must remain stopped rather than start unsafely. A new authorization is
needed for a reboot test or enabling unattended boot startup.

After reconnecting in a new SSM terminal, check only the pilot-owned unit:

```sh
sudo systemctl is-active noetharaclipz-continuous.service
sudo systemctl is-enabled noetharaclipz-continuous.service
sudo systemctl status noetharaclipz-continuous.service --no-pager
sudo journalctl -u noetharaclipz-continuous.service -n 100 --no-pager
```

These are **status commands**, not startup authorization. The controller's
own `status` action and durable metrics summary should also be inspected
using the installed, manifest-matched paths from the next handoff.
No shell session, periodic terminal ping, or external keep-alive is required.

## Fixed scope for proposed 24-hour test

- Existing EC2 only: `i-0be10e530045fc650` / m6i.2xlarge / us-east-2.
- Model: pinned **SmolVLM2-500M** and pinned Whisper assets; no Gemini
  or paid AI provider.
- Container: **8 GiB memory, 2 CPU quota, no extra swap, 256 PIDs,
  one active job, no public ports**; private file-mounted secrets,
  independent volumes and scoped egress.
- Only a **newly consented, separately operator-approved pilot owner**.
  Prefer the same approved testing identity after it completes a fresh,
  authenticated consent request; do not impersonate the owner or
  repurpose the expired consent generation.
- Owner-scoped future projects/jobs only. No global claim path; no
  existing-job backfill or release. Permanently exclude original job
  `9c5c8869-ec2e-4a3e-927d-697615bb58a3`.
- Exactly **24 hours** between fresh immutable UTC start and expiry,
  selected near deployment after preflight, never from an already expired
  timestamp. Keep an automatic shutdown reserve and fail closed if expiry
  or approval cannot be verified. No automatic approval extension.
- No new instance, EBS volume, paid monitoring service, merge,
  public website publication or host-wide Docker/network modifications.

The existing consent migration `20261109124958_continuous_worker_consent`
is deployed. **Do not reapply** it or edit Lovable-managed migration history.
The prior owner's operator approval expired at 2026-11-09 21:30 UTC; the
new 24-hour run requires a **fresh authenticated owner consent**, a distinct
consent generation, a new deployment ID, a reviewed active manifest SHA256
and operator approval for precisely that owner/window. Approval duration
must respect the server's maximum seven-day bound.

## Preparation, launch and verification gates

1. Preserve the earlier 30-minute pilot evidence. Confirm its service is
   inactive/disabled, consent expired, no active leases, unchanged original
   upload, no other active worker, and archived QA containers untouched.
2. Gather a fresh **read-only** SSM host snapshot: available RAM/disk, all
   six existing services, image/model/source hashes, Docker/cgroup support,
   reserved paths/UID, network bridge, firewall chains and rule ordering.
3. Prepare a fresh private source handoff and a **new disabled** manifest
   proposal. Verify source/import/image hashes and approved sample footage.
   Do not put credentials or signed URLs in source control.
4. Obtain the pilot account's actual authenticated consent request, then
   review and separately authorize the operator's specific 24-hour UTC
   expiry, deployment ID, approval reference, and final active manifest
   digest. Confirm existing SQL allows new generation consent; no database
   migration or old-job release is required.
5. After specific authorization to **install/start** this new deployment,
   perform the controller's gated installation and use `systemctl start`
   only after the isolation unit and required preflights. Do not use
   `systemctl enable` by default, reboot the shared host, or restart Docker.
   The worker must prove actual kernel quotas and scoped egress denial
   counters before any credential/model access and before claiming QA jobs.
6. Retain host-side samples and bounded logs **on disk** throughout the
   test, independent of SSM. Sample cgroup memory current/peak, OOM events,
   CPU-stat deltas/usage, restarts/backoff, temp space and Docker health.
   Capture final snapshots before container cleanup, without claiming
   resource measurement from stopped-container stats.
7. At several points during the window, remotely inspect readiness and
   process fresh approved owner sample jobs through the normal website:
   upload → actual queued highlight → edit/save/refresh → Export → private
   MP4 download/decode. Validate expiration/revocation behavior, job
   ownership, no global claims, and unchanged legacy upload. A single
   complete test early in the window does not prove continuous 24h uptime.
8. Ensure **automatic final shutdown** at the fixed deadline, consent
   expiry/offline readiness, zero active leases after graceful completion,
   controller and Docker exit status, no unwanted startup at boot, retained
   peak metrics, and no changes to the other services or protected job.
   If any gate fails, stop only this pilot, revoke its processing grant,
   preserve logs/data and do not clear latches to force a pass.

## Operational risks and acceptance criteria

The preceding 30-minute pilot proved a successful real workflow, owner
consent, CPU/RAM quotas and a clean expiry. A 24-hour window adds exposure
to idle-time failure, host restarts and periods without an operator watching.
If no live notification route is available, document that limitation and
rely on durable local monitoring plus manual inspection; **do not claim
automated external alerts are configured**. Keep resource/latency observations
distinct from model quality. Exceeding Supabase/EC2 transfer/storage
allowances may create cost even with no new paid infrastructure.

Pass only with verified 24-hour service/controller state history, retained
resource coverage, at least one fresh complete normal hosted workflow, expiry
and shutoff proof, ownership/consent isolation, and unchanged older uploads/
existing services. Retain all failed-preflight evidence. A passed 24-hour
owner-scoped pilot does **not** authorize global/general-user processing or
public website deployment.
