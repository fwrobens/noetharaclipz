# Running 24-hour owner-scoped EC2 pilot

Status: **RUNNING; INITIAL WEBSITE WORKFLOW PASSED; 24H ENDURANCE/EXPIRY PENDING**.
The 2026-11-09 21:00–21:30 UTC pilot ended safely at 21:29:46 UTC.
Do not restart, edit, extend, renew, or reuse its expired deployment receipt,
owner consent generation or signed active manifest. Authorization covers only
the new deployment and fixed window below. Boot startup remains unauthorized.

## Current preparation (November 9, after commit 6a3c63b)

New deployment ID: `c25d8492-56fb-4c56-a519-e9a9e4246525`.
Intended pilot owner: `21b61ad1-bda4-4abd-ac35-7a0bf477ed69`.
The existing identity was authenticated successfully; its previous consent
generation is expired and will not be reused. **Fresh explicit owner consent
was authenticated and recorded at 22:24:37 UTC**, generation
`6b13bb7a-5b9b-4564-80d8-3904872d8c01`. Operator approval and expiry remain
null in that preparation snapshot. The EC2 launcher subsequently obtained
processing approval at **23:00:23.586181 UTC**, expiring exactly **November 10
at 23:00 UTC**. See [owner consent](evidence/continuous-24h-owner-consent.json)
and [live startup verification](evidence/continuous-24h-startup-supabase.json).
All **23 fresh EC2 preflights passed at 22:28:58 UTC** after the collector fix.
The user subsequently replied **yes** to the exact manifest/window and
installation/start scope. The separate private authorization receipt was issued
and verified at **22:47:13 UTC**. Database processing approval is deferred to
the EC2 launcher inside the approved start window. The operator executed the
sealed command; Docker started the new container at **23:00:24.319486246 UTC**.
The initial dispatcher reported `launch_requested`, not readiness. Independent
Supabase reads at 23:01:17 UTC confirmed online/AI-ready with the exact pinned
500M model; the subsequent read-only host snapshot confirmed actual startup.

[User authorization](evidence/continuous-24h-user-authorization.json) ·
[Private readback/access verification](evidence/continuous-24h-authorization-verification.json).
Authorization-record SHA256:
`9e8fab60a71ae088be5b3b3dc966d357ff61222b6418880df1a9fda24910964f`.

| Review item | Exact approved value |
| --- | --- |
| UTC window | **2026-11-09 23:00:00 → 2026-11-10 23:00:00** (86,400 seconds) |
| Launch permitted | 23:00:00–23:04:59 UTC November 9; no waiting/extension |
| Disabled candidate SHA256 | `0d3dd0f3e1ce7a74712bb555f85104e4c661543e20677a652882bc47bd277bb8` |
| Approved activation manifest SHA256 | `3918b9eb1dee06597852c016a7098a873eea914bbac8afa151557cda2c34dda0` |
| Immutable review plan SHA256 (canonical JSON) | `1b0e2436c5a93b65ce73e4cfabfd8625ad87c4c5019458605ada6e85f2875912` |
| Kernel limits required at startup | 8 GiB, 2 CPU, no extra swap, 256 PIDs, one job |
| Owner/provider | This fresh pilot consent only; pinned local SmolVLM2-500M |
| Boot/global/Gemini | Disabled; no reboot test or general-user processing |

[Disabled candidate](evidence/continuous-24h-manifest-candidate.json) and
[review plan](evidence/continuous-24h-review-plan.json) are the exact review
artifacts. The activation digest is precomputed from only the candidate's
approval flag/reference change. The candidate and review plan remain unchanged
historical preparation artifacts; the separate receipt records the later user
approval. The installed active manifest matches the approved digest. All manifest/plan
digests use canonical JSON with sorted keys and comma/colon separators. The
launcher requires the private receipt, not just a true flag in a JSON.

The approved installation scope is restricted to this new deployment's
configuration/data/report paths, the dedicated `continuous/current` symlink,
stopping the old isolation oneshot and starting the existing reviewed worker
unit without enabling it. It reuses the existing image, models, key file and
identical installed units. Failure rollback may revoke only the new consent
and stop only these dedicated worker units. No host-wide Docker/network
configuration, existing services, old trial files, queued-job release or
database schema changes are authorized. The existing instance adds no new
infrastructure; storage/egress remain subject to existing allowances.

## Initial live result (23:00–23:13 UTC November 9)

**Initial startup and functional acceptance passed. This is not a completed
24-hour reliability result.** The service remains active until the fixed expiry
unless safety/consent monitoring stops it earlier. SSM can disconnect; the
existing systemd controller owns the worker, logs, cgroup sampling and shutdown.

[Read-only host snapshot](evidence/continuous-24h-initial-host.json), collected
by the operator at **23:13:47 UTC**, verifies:

- Container `abb2252ebb8bf3665db5e7310d2e594e563401fa8bc85214126d862ffb9c51f9`
  is running/healthy, with **zero restarts and no OOM**. Docker restart policy
  remains `no`; bounded recovery is controlled by the reviewed controller.
- Both dedicated systemd units are **active and disabled at boot**, with
  unchanged loaded hashes, empty drop-ins and no pending daemon reload.
- Actual cgroup files prove **8 GiB, 2 CPU quota, no extra swap and 256 PIDs**.
  All seven private/VPC/IMDS/host/gateway/non-HTTPS denial counters increased by
  one; public TLS and IPv6-disabled checks passed before the queue grant.
- **398 durable samples** at this snapshot; kernel peak RAM
  **3,011,940,352 bytes (2.805 GiB)**, sampled CPU peak **204.8667%** (one
  core=100%), cumulative CPU **289.518277 seconds**. The short-interval CPU
  peak is not instantaneous or clamped; the actual two-CPU quota is separately
  proved. These totals include startup, processing/rendering and idle time.
- Controller status was only 0.256 seconds old. Metrics JSONL, summary,
  controller log, source/approval/install receipts and network proof files are
  retained under the dedicated deployment. Final snapshots remain pending
  while the worker is running.
- Six existing Noethara/Supabase services, all four older container lifecycles,
  old evidence and isolation are unchanged. No other application was restarted.

### Fresh normal website upload/export

A new **180-second authorized SuperTuxKart** upload through the unchanged
development UI used real Supabase and this EC2 worker. It exercised sign-in,
upload/instructions, Generate, queued local video/audio/scene/transcript
analysis, automatic highlight, playback/select/edit/Save/refresh, normal Export,
queued rendering and authenticated MP4 download/full FFmpeg decode. No highlight
fixture, direct render shortcut, local queue consumer or worker restart was used.
The public website was not published.

| Actual result | Value |
| --- | --- |
| Upload plus analysis | **169.595 seconds** |
| Complete normal UI workflow | **195.117 seconds** |
| Analysis and render | Both completed on attempt one |
| Automatic highlight | **151.967–161.967 seconds**, model choice G among eight actual videos plus none |
| Fresh inference | **3,711 input / 12 output tokens**, all three caches missed, hosted inference false, estimated inference cost zero |
| Evidence distinction | No complete ASR words in selected interval; five measured audio events and one scene boundary; visual observations remain separate |
| Persisted edit | **152.1–161.967 seconds**, 9:16, verified after refresh |
| Private output | **9.9-second H.264/AAC MP4**, **2,044,140 bytes**, full decode passed |
| Output SHA256 | `cf4670c8baaa209384a207f63140db92aa0b936494b783449b1885af19db50e3` |

Project `94f1c4e5-e8c2-414c-93ee-28395035b0e5` was created after the current
processing approval. Analysis `5c42ac66-6b84-4527-932c-b24b719a9423` and render
`1918a086-2bc9-44fe-89c3-585f04c990c1` demonstrate real queue consumption for
the fresh consent generation. See [browser evidence](evidence/continuous-24h-initial-browser.json).
This repeats a functional acceptance path on the new deployment; it is not a
new controlled model benchmark or a broad accuracy claim. Footage attribution
remains in [the sample source record](reliability-trial.md).

At **23:11:54 UTC**, [hosted security checks](evidence/continuous-24h-initial-security.json)
verified owner private download (206, bytes match the actual browser file),
public/anonymous download denial (400), privileged protocol denial for anonymous
(401) and the authenticated pilot (403), cross-user project/job denial and
persisted edits. Both jobs remained completed, no active leases remained,
online/AI-ready was true and the original upload retained its identical whole-row
hash: **queued, zero attempts**. Processing approval did not grant the pilot
operator/admin permissions.

### Remaining 24-hour evidence

The [read-only reconnect collector](../scripts/inspect_continuous_24h_status.py)
has no wait loop or container/service/network mutation. Its private handoff is
valid through November 11, and can be rerun after reconnecting or after expiry;
it does not renew approval. Seven focused observer-boundary tests and Ruff pass.
The reviewed worker/controller source, manifests and units remain unchanged.

Suggested interim snapshots are **November 10 at 07:00 and 15:00 UTC**, plus a
late-window inspection and final proof after **23:00 UTC**. Process only fresh
authorized owner projects during the approved window. Record readiness,
resource/sample continuity, restarts, consent/ownership, private download and
original-upload/service invariants. Do not rerun the launch command, restart old
trials, clear failure latches or extend the deadline. The controller monitors on
EC2; no external notification route or automatic assistant follow-up is claimed.
Final expiry/shutdown, removed grant, offline readiness, leases and retained
final cgroup snapshots still need verification after the fixed stop. No merge,
website publication, global release, Gemini or boot enablement is authorized.

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
separate [24h launcher](../scripts/launch_continuous_24h_pilot.py) completed its
one approved execution inside the launch window. Earlier invocations stopped
at the time guard before installation/approval/start or a launch-attempt
marker. Use only the read-only status collector for subsequent snapshots.

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

The final review plan binds the fresh consent generation, disabled candidate
manifest hash, prospective activation-manifest hash, exact UTC start/expiry,
private source receipt and explicit installation scope. Computing a prospective
activation hash is not approval: no active manifest is installed or processing
approval requested without the separately issued authorization record.

The [sealed launch handoff](evidence/continuous-24h-launch-handoff.json) is
24,176 bytes, SHA256
`6148a90f924e0008fe0e5cfab7052029bf552df328a42912cc77c8339bd71b21`.
It was privately uploaded and read back byte-for-byte; its public endpoint is
denied. The one SSM command is retained privately in the preparation handoff,
with a download link expiring November 10 at 22:34 UTC. The exact manifest and
installation/start scope were approved and the command was executed once in
the reviewed launch window. Its independent authorization object was issued once
without overwriting any object, read back exactly, and denied to public and
anonymous clients. The command still refuses early/late launch or a missing,
changed or out-of-scope authorization record.
That download link is needed only for installation, not for continued service
execution or monitoring after SSM disconnects. No signed URL or credential is
committed to GitHub.

After explicit user approval, an authorization JSON was issued once in the
existing private bucket. It binds both hashes, owner, consent,
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

Local verification: **354 worker tests passed, one optional sample test
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
