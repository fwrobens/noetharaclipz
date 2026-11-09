# Continuous local-worker pilot — implementation prepared, not deployed

## Current checkpoint — transfer and all read-only host preflights passed

The operator's SSM receiver completed at **2026-11-09 20:33:56 UTC** on the exact
existing instance `i-0be10e530045fc650`. All **25 source files and two unit files**
matched their pinned hashes. Verified source is privately staged at
`/tmp/nccz-continuous-pilot-0qkrd0gd`; nothing was installed or started.

The host collector completed at **20:33:58 UTC** with **all 13 checks true**:

- **8 host CPUs**, **28.77 GiB available RAM**, **45.67 GiB free disk**, low load.
- Docker **29.1.3**, cgroup **v2**, reviewed Linux amd64 image identity and pinned
  SmolVLM2-500M/Whisper asset manifest match.
- Dedicated network ownership, probe-target admission, required firewall rules
  and hook ordering passed; isolation was unchanged during collection. The
  fingerprint is `4489b256c620398c44a4d1c66a75ee60319444c27d072dc24e81a87d5d5b102b`.
- Existing secret **metadata** matches; its contents were not read.
- All six existing service start times/restart counts/health match the archived
  baseline. Five are healthy; REST remains running with no Docker health check.
- All three historical QA container start/finish times and restart counts match
  their archive; all remain exited. New deployment paths are absent, the
  continuous unit is inactive/not-found and no continuous worker is running.

[Full EC2 receipt and report](evidence/continuous-pilot-ec2-preflight-2033.json)
records operator-pasted provenance; Codex did not gain direct EC2 access. Hashes,
identity and archived service/trial states were checked locally. Fresh Supabase
reads at **20:37:51 UTC** confirm v2/global off, the pilot's processing approval
still false, and the original upload's exact unchanged queued/zero-attempt row.
[Post-host Supabase evidence](evidence/continuous-pilot-post-host-supabase.json).

### New candidate for separate authorization — 21:00–21:30 UTC

The expired 15:15 candidate remains unchanged. A **new unapproved proposal** covers
**2026-11-09 21:00:00–21:30:00 UTC**, exactly 30 minutes. It is not scheduled and
does not extend any old authorization. Candidate SHA256:
`a2974efc290782d52d16acef2b1814548b3756908af017247dec5450d7ad29ce`.

[New manifest candidate](evidence/continuous-pilot-2100-manifest-candidate.json)
and [exact authorization scope](evidence/continuous-pilot-2100-authorization-scope.json)
still have `operator_approved=false` and no approval reference. They cannot start
a worker. Required separate grants are:

1. Processing approval for owner `21b61ad1-bda4-4abd-ac35-7a0bf477ed69` and consent
   `4426bdad-bc7a-4972-ace2-ae65ac3f9fa4`, issued **no earlier than 21:00 UTC**
   and expiring at **21:30 UTC**. No account administrator/operator role is granted.
2. Install/start only deployment `11865b83-9836-4ff3-a99e-dfac4df71f34` on the
   existing instance within that window, subject to fresh startup checks. Keep
   the reviewed image/source, SmolVLM2-500M, **8 GiB / 2 vCPU / one job**, private
   volumes/secrets, no public ports, Gemini/global false and restore-isolation
   false. Test only fresh authorized pilot sample uploads through the normal
   website and stop this worker/controller by the fixed deadline.

Upload pilot footage only after processing approval is actually recorded;
pre-approval projects/jobs remain ineligible. Early installation/start commands
also fail the manifest's fixed `not_before` guard. Approval now would authorize
preparing the bounded handoff, not processing before 21:00 UTC.

No boot enablement, forced crash, existing-service restart, shared networking
change, original-upload/old-job release, paid infrastructure, merge or website
publication is included. Rollback revokes this deployment's grant and stops only
its matching controller/container, preserving existing services/assets/evidence.

**All read-only preparation checks passed.** Actual new-container cgroup limits,
per-generation live denial-counter proofs and consent-aware hosted website
acceptance still belong to the separately authorized gated startup/pilot. No
processing approval, active manifest, installed unit or running worker exists
yet. If this new window is missed, prepare another candidate for separate review.

## Earlier preparation and recovery history

The implementation builds on `0195e13` and its completed EC2 reliability trial;
pilot preparation continues from `b883b01`. The consent migration is already
applied. A fresh dedicated pilot account now has explicit owner consent;
operator approval and worker startup remain pending. No completed AI/media
benchmark was repeated. The earlier QA containers/assets/evidence are unchanged.

**Recovery status at 2026-11-09 20:30 UTC:** the previous signed download
failed before the receiver/host collector ran. Supabase returned HTTP 400,
`InvalidJWT`, `"exp" claim timestamp check failed`; the link had expired at
15:41 UTC. The secondary Apport exception comes from reporting a Python stdin
failure and is not evidence that any worker executed. Both nested downloads are
now refreshed for about one day, with the outer link expiring **2026-11-10
20:29 UTC** and the source link one minute later. Private readback returned 200
with matching hashes; unsigned public access remains denied. No source/collector
code, bucket visibility, owner approval or job was changed.

The proposed **15:15–15:45 UTC window has expired, unapproved**. Its immutable
candidate and scope remain historical evidence; do not activate them or silently
extend them. After a successful SSM receipt/host report, prepare a new fixed
30-minute candidate for separate review. At 20:30 the host preflight status was
**not run**, operator authorization false, and the original upload's exact row
remains queued with zero attempts. The refreshed copy-paste block handles
download failures cleanly and creates only private preparation files.
[Expired-link diagnosis and verified recovery](evidence/continuous-pilot-expired-link-recovery.json).

## Original pilot identity and proposal record — 2026-11-09 UTC

- Deployment: `11865b83-9836-4ff3-a99e-dfac4df71f34`.
- Fresh owner: `21b61ad1-bda4-4abd-ac35-7a0bf477ed69`; password login and identity
  verification passed. Credentials stay in a private mode-0600 local record,
  outside Git, chat output and the EC2 handoff.
- Owner explicitly answered **“I consent for this pilot account”** to local
  processing of separately authorized sample footage for a proposed 30-minute
  pilot. The authenticated owner request was recorded at 13:13:29 UTC as consent
  `4426bdad-bc7a-4972-ace2-ae65ac3f9fa4`, terms `local-video-v1`.
- Server processing authorization is **false**: no operator approval or expiry
  has been issued. No upload/job was created and no worker was started.
- Proposed duration: **1,800 seconds**, with fixed UTC start/expiry chosen only
  after review. No automatic renewal or boot enablement is proposed.
- [Immutable disabled manifest proposal](evidence/continuous-pilot-manifest-proposal.json)
  SHA256: `736b72c902eae0b65d251db69d15dedfe38e5e5b105b71849b3469c702d90d73`.
  `operator_approved=false`; activation timestamps are zero. It deliberately
  fails startup validation. This is **not** an activation authorization; a new
  final hash is required after explicit operator approval/window selection.
- [Operator approval proposal](evidence/continuous-pilot-operator-approval-proposal.json)
  is inert: no reason/reference, start or expiry is fabricated and no approval
  RPC is invoked during preparation.
- Reuse the exact 184,274-byte source bundle from `4f78781`, SHA256
  `564a5b6a5de0664448737e0c5291c30a4d1ff2074be096b08711dce11fb381d8`.
  All 25 overlay sources and both units still match the reviewed artifact;
  documentation/preparation changes do not rebuild the image or model.

Live REST verification at 13:09 UTC returned the exact v2 contract with all
four consent protections true, `global_claim=false` and `local-smolvlm2`.
Anonymous privileged protocol access was denied (401), and the fresh regular
authenticated owner was denied (403). The original upload retained its exact
whole-row SHA256, queued with zero attempts. No migration was reapplied.

This session has no AWS identity/CLI or direct EC2 execution connection. The
private preparation handoff transfers source into a new temporary directory and
runs `scripts/inspect_continuous_pilot_host.py` using only read-only commands.
It checks resources, service health, reviewed image/assets, secret **metadata**,
network ownership/rule order and stopped historical containers. It cannot read
the secret contents, install a unit, alter rules, execute a container or access
the queue. Live per-generation denial counters and actual new-worker cgroup
limits remain mandatory after a separately authorized gated startup.

[Owner consent receipt](evidence/continuous-pilot-owner-consent.json) and
[preparation summary](evidence/continuous-pilot-preparation.json).

The private preparation handoff is **214,665 bytes**, SHA256
`0a30367d6040d53dceec7632000a0b1b48caa5d2178e75f52f098955c06a700e`.
It is staged in the existing private `processing-artifacts` bucket, with signed
readback matching the hash and unsigned public access denied. Existing object
usage was 228,530,645 bytes; conservative application reservations were
258,206,953 bytes, well below the existing 800 MB cap while preserving 100 MB
of user headroom. No bucket setting or paid service changed. Signed URLs remain
only in the private handoff/chat, never in Git. EC2 receipt and fresh host results
are pending the SSM collector response.

The collector only stages `manifest-proposal.json`; **do not install or start
from it**. A future approved active manifest must have its own reviewed hash.
Source is not activated by downloading it. No rollback action is currently
necessary because no continuous unit/container has been installed or started.
Owner revocation remains available through the existing authenticated helper.

Local preparation checks: **54 control tests passed**, including 11 new cases
that deny mutation/secret-reading commands and reject changed staged source;
Ruff passed. All 60 earlier evidence files, 37 deployment files, ten worker modules
and eight migrations match `b883b01`. No completed benchmark was repeated.
[Private transfer evidence](evidence/continuous-pilot-private-transfer.json) and
[local verification](evidence/continuous-pilot-local-verification.json).

## Final preparation handoff and proposed UTC scope

The original 13:21 handoff link expired. At **14:42 UTC** a new one-hour signed
download was issued for the **same unchanged object**. A separately hash-verified
8,262-byte receiver wrapper reduces the SSM command to one short Python block.
The wrapper expires at **15:41:04 UTC**; neither object was made public. No
credential or signed URL is stored in Git.

[Receiver source](../scripts/receive_continuous_pilot_preparation.py) verifies the
original handoff/source/collector/proposal and every source/unit hash, writes only
new private temporary files, and runs the unchanged reviewed collector. It saves
`transfer-receipt.json` and `host-preflight.json` in the reported EC2 directory and
prints both as one JSON result. No operator approval, installation, model/queue
access or container execution is possible through this receiver. **16 targeted
receiver/collector tests passed; Ruff passed.** Completed media benchmarks were
not repeated. The EC2 result is still pending; do not mark the host checks passed
from local receiver tests or signed Storage readback.

Proposed final pilot window: **2026-11-09 15:15:00–15:45:00 UTC**, exactly 1,800
seconds. [Fixed-window manifest candidate](evidence/continuous-pilot-1515-manifest-candidate.json)
SHA256: `1cb8e39cfdd9d5f4485c05bab9837a87a1e2cc6d3e55078bb1d833c14ce34ae3`.
It remains **unapproved**, with `operator_approved=false` and no approval reference,
and rejects startup even inside its proposed window. The older zero-timestamp
proposal remains unchanged as historical preparation evidence.

[Exact authorization scope](evidence/continuous-pilot-final-authorization-scope.json)
requires **two separate grants**, neither issued:

1. Service-side processing approval for owner
   `21b61ad1-bda4-4abd-ac35-7a0bf477ed69` and consent
   `4426bdad-bc7a-4972-ace2-ae65ac3f9fa4`, expiring at 15:45 UTC. This grants no
   administrator/operator role to the account.
2. Installation/start of deployment `11865b83-9836-4ff3-a99e-dfac4df71f34` only
   on the existing `i-0be10e530045fc650` m6i.2xlarge: reviewed image/source/500M
   assets, 8 GiB / 2 vCPU / one job, no public ports, Gemini/global off. Verify the
   normal website workflow using fresh authorized sample uploads only and stop
   this worker/controller before the fixed expiry. No boot enablement, forced
   crash, existing-service restart, shared firewall change, old-job release,
   infrastructure purchase, merge or publication is included.

Both grants depend on a verified EC2 receipt and passing fresh read-only host
checks. Actual new-generation cgroup and live network-denial proofs must pass
before model/queue access during any later authorized gated startup. After
authorization, only approval metadata may change in the activation manifest;
record its resulting hash. A missed window must be replaced by a separately
reviewed candidate, never silently extended or rescheduled.

[Refreshed private-link evidence](evidence/continuous-pilot-handoff-refresh.json)
and [fresh live pending-approval/upload checks](evidence/continuous-pilot-final-preparation-supabase.json).

## Live Supabase consent migration checkpoint — 2026-11-09 UTC

**Applied and verified; pilot still inactive.** The repository's exact
`docs/proposals/continuous-worker-consent.sql` from commit `fa414ce`
(blob SHA `7b546ae3511f2e84aa35fd2c28fb1b41af9940da`) was
separately authorized by the owner and applied through the connected Supabase
migration API to project `zxdnjnsghdnviflahvry` as version
`20261109124958_continuous_worker_consent`. The live migration ledger confirms
the new version; all older versions remained unchanged.

Read-only post-apply checks at 2026-11-09 12:50 UTC verified:

- Six new private consent tables have RLS enabled. Three historical QA owners
  are excluded; the protected upload is explicitly excluded.
- Exactly **zero** owner consents, pre-existing consent-bound jobs or leases,
  active job leases, and audit entries. No pilot owner has requested or received
  approval, and no worker has been started.
- Service role can claim opt-in jobs and approve consent; anonymous and regular
  authenticated callers cannot. Regular authenticated owners may request their
  own consent. The service role no longer has global-claim EXECUTE.
- `public.worker_continuous_protocol()` exists (v2 contract function).
- The protected upload `9c5c8869-ec2e-4a3e-927d-697615bb58a3` remains
  queued with zero attempts, no lease and no cancellation. Its full-row JSON
  MD5 was `7820c45dca35993cb90f5b3fec2105f1` before and after applying.

Security advisor informational findings for default-deny private RLS tables
remain; leaked-password protection is separately disabled and was not changed.
**Do not reapply this SQL or create another copy of the migration.** The
review-only SQL source stays under `docs/proposals/`; no Lovable-managed
migration file was edited. This checkpoint is a database verification, **not**
an EC2 pilot authorization or an end-to-end hosted v2 test.

**Remaining sequence:** create or select a fresh eligible pilot identity;
obtain that identity's explicit opt-in request; separately approve the owner and
time-bounded immutable manifest; verify private source bundle transfer and
fresh EC2 startup isolation; then seek the separate authorization to start the
owner-scoped continuous worker. Keep global processing disabled and the old
upload permanently excluded.

## Startup and recovery

`deploy/worker/continuous_host.py` is a dedicated controller for the existing
`i-0be10e530045fc650` m6i.2xlarge in us-east-2. It uses new configuration/data
directories under `noetharaclipz-isolated/continuous/<deployment-id>`, separate
from every historical `trials/` directory. Pinned 500M/Whisper model volumes are
shared read-only. The existing private file secret remains outside the image,
manifest, Docker environment and reports.

Startup verifies the immutable source bundle, approved window/owner/consent,
Docker image and architecture, pinned assets, dedicated volume permissions,
host RAM/disk headroom, existing service baseline, network ownership, rule order,
and the protected upload's whole-row hash. Missing consent protocol v2, expired
or revoked consent, unsafe files, changed isolation or another active worker
prevents queue access. No legacy/global claim fallback is available.

Each container generation starts with **no model or credential loading**. It
proves its actual kernel limits, creates a fresh nonce and waits for a root-owned
read-only grant. The controller verifies public DNS/TLS and all seven scoped
private/IMDS/host/gateway/non-HTTPS rejection counters before issuing that grant.
It rechecks consent/protection, isolation and resource monitoring while active.
Grant expiry, local revocation, security drift or lost monitoring stops work.

Limits remain **8 GiB, 2 vCPU, no extra swap, 256 PIDs, one active job**, explicit
local SmolVLM2-500M, Gemini/global false, no public ports and private volumes.
Docker restart is **disabled**. Only the controller may restart a generation,
after repeating preflights. It backs off 5/15/45 seconds, with at most three
failures in fifteen minutes and a durable blocked latch. Restarting the controller
does not erase the budget. A host-wide lock prevents competing pilot controllers.
The systemd unit additionally bounds its own restarts.

The new units order Docker, existing mounts and worker isolation before the
controller. The isolation action is read-only unless the separately reviewed
manifest explicitly authorizes restoration. Restoration only appends the exact
approved reserved chain/rules and missing worker-interface hooks; foreign,
reordered or conflicting state fails closed. It never flushes shared chains,
changes global policies, restarts Docker, changes security groups or touches
Noethara/Supabase containers. No unit has been installed or enabled here.

Approval windows are fixed and limited to seven days; an initial pilot should
use a short explicitly approved window. A fifteen-second shutdown reserve allows
the entrypoint to stop before its hard expiry. Routine operator shutdown permits
graceful completion of cleanup; security/consent loss uses the short termination
path. There is no automatic approval renewal or old-trial receipt reuse.

## Retention and health

Host-side sampling derives the actual cgroup from the container PID, checks live
quotas and records kernel RAM peak, sampled CPU, cumulative CPU and per-generation
final snapshots. Counters and peaks persist across controller/container restarts.
The last 64 generations are retained with cumulative retired CPU accounting;
samples rotate at 5 MiB with three backups. Missing counters remain gaps, never
fake zero measurements. The final-snapshot acknowledgement happens after the
host saves counters. Network proof retention is bounded to 64 files.

Controller logs rotate at 5 MiB with three backups. Docker logs remain 10 MiB
with five compressed files. No paid monitoring agent is installed. `status.json`
records readiness, stage and metrics; systemd failure/blocked status plus stale
readiness can feed the operator's existing monitoring. A live alert destination
and its notification delivery still need selection for a production rollout.

The worker reports actual selected-provider readiness only after model preflight
and a successful consent-aware heartbeat. Revocation makes server health false
immediately, including while an old heartbeat is fresh. Only dedicated temporary
directories older than a day are removed; active jobs are capped at twenty minutes.
Cache pruning remains the existing local provider's bounded policy. No global
project/storage cleanup or cross-owner file deletion runs in consented mode.

## Server-side opt-in SQL contract — applied; no pilot consent yet

[continuous-worker-consent.sql](proposals/continuous-worker-consent.sql) is the
original review-only transactional migration source, outside
`supabase/migrations/` as required by `AGENTS.md`. The exact approved SQL was
applied as new live migration version `20261109124958` on 2026-11-09; no existing
migration was edited or reapplied. Keep this source as the reviewed record.

The contract adds private RLS-enabled consent, exclusions, job bindings, lease
bindings and append-only audit tables. Authenticated owners can request/revoke
only their own consent. Operator approval is a separate service-role operation,
requires an audit reason and has an expiry; an owner request alone grants nothing.
Existing QA owners cannot opt in. The original protected job is permanently
seeded in the exclusion table; there is no release/backfill RPC.

Eligibility is captured only on **new job INSERT** while the current consent is
approved, and only for projects/jobs created after approval. It binds the exact
owner, consent generation, source identity, instructions and saved render input.
Existing jobs/projects receive no binding. Retries retain their original binding.
Revocation/re-consent cannot rebind old queued or active jobs. New exports of an
old project also remain held; initial pilot footage must be uploaded after approval.

Consent-aware claim/tick/checkpoint/completion RPCs validate ownership, input
revision, exclusion, active consent and exact lease token. Claims retain the
global advisory one-job lock, natural lease recovery, cancellation and retry cap.
Visible result-write triggers also guard legacy finish/checkpoint paths, so
revocation cannot be bypassed by switching to v1. Global claim execution is
revoked from the service role in the proposal. Frontend RLS is not weakened.

Worker writes hold the owner-consent row lock; revocation takes its exclusive
lock. A transaction already committing completes before revocation returns;
a transaction waiting behind revocation cannot publish afterward. Actual
PostgreSQL concurrency tests exercise both orders. An already in-flight private
Storage HTTP request may finish, but revoked work cannot publish its output
reference. Such private unreferenced files require scoped reviewed cleanup;
revocation does not delete uploaded footage or reset/cancel unrelated jobs.

Audit records cover requests, approvals, revocations, job bindings, claims and
exclusions. Clients cannot read or alter private tables directly, and audit
UPDATE/DELETE is blocked. No credentials, lease tokens or footage are placed in
audit reasons. Denied SQL transactions roll back; their failed attempts are not
claimed as durable application audit events.

## Exact limited-pilot procedure — future authorization required

1. **Completed 2026-11-09:** Separately authorized exact SQL applied as live
   migration `20261109124958_continuous_worker_consent` and verified for grants,
   RLS, function presence, no new consent/job bindings and protected upload.
   **Do not reapply** this migration, heartbeat, or v1 queue migrations.
   The controller still fails closed until separate owner/operator opt-ins.
2. **Completed: one new pilot owner and explicit owner consent.** Preserve all
   historical QA accounts and the original upload. The new owner and actual
   recorded consent appear above; do not create a duplicate or re-request it. The
   first pilot deliberately uses one owner per controller; server consent records
   support separately approved owners, with one active processing lease overall.
3. **Inspect the recorded consent, then obtain separate operator approval.**
   The current owner's explicit request is already recorded; do not request it
   again or create a replacement generation. Its existing private login record
   can read status:

   ```sh
   python scripts/continuous_consent.py status --account /secure/pilot-account.json
   ```

   The file is mode 0600 and stays private. No credentials are pasted into chat
   or command arguments. Record the returned owner/consent UUIDs, which are not
   credentials. The existing bound service key is used for operator approval:

   ```sh
   python scripts/continuous_consent.py approve --owner "$NC_PILOT_OWNER" --consent "$NC_PILOT_CONSENT" --expires-at "$NC_PILOT_EXPIRES_UTC" --authorization-reference "$NC_PILOT_APPROVAL_REFERENCE"
   ```

   Those variables must contain the separately approved owner, returned consent,
   actual UTC expiry and audit reference. The command cannot manufacture owner
   consent, extend an existing approval or release old jobs.
4. **Reuse the exact reviewed bundle for this pilot.** The hash/size and source
   commit appear above. No runtime source has changed, so no rebuild or repeated
   inference benchmark is needed. For a future changed source revision only,
   build a new immutable overlay from its reviewed clean commit into new paths:

   ```sh
   python scripts/build_continuous_bundle.py --output test-results/continuous-source.json --manifest-template test-results/continuous-manifest.json
   ```

   Fill a new deployment UUID, returned owner/consent, approved timestamps,
   operator approval/reference and any explicitly authorized isolation-restoration
   flag in the manifest. The generated default is **disabled and unapproved**.
   Keep the source-file hashes and base image intact. Approve the resulting exact
   manifest hash before deployment. Do not use an old trial UUID or archived owner.
5. **Transfer only the reviewed small JSON bundle/manifest** using the existing
   private, temporary signed-download method, with both hashes verified on EC2.
   Reuse the already installed reviewed image and offline model assets. No new
   PAT, GHCR/Actions job, image rebuild, image upload, public URL or paid resource
   is needed. A newly hash-pinned application overlay is a changed artifact;
   the base image being unchanged does not mean the application is identical.
6. **Preparation-only EC2 installation** after that private verified handoff:

   ```sh
   sudo -n python3 /tmp/nccz-continuous-approved/host/continuous_host.py install --bundle /tmp/nccz-continuous-approved/bundle.json --manifest /tmp/nccz-continuous-approved/manifest.json
   ```

   The handoff must supply those exact verified paths. Installation creates only
   new private deployment directories and cannot start a container or unit.
   It refuses path collisions, changed source, wrong host or unsafe isolation.
   Compare its manifest hash and review fresh RAM/disk, services and networking.
7. **Only after separate pilot deployment authorization**, select the new root
   manifest without replacing an existing active `current` link, install the
   two reviewed unit files, reload systemd and start only the new service:

   ```sh
   sudo -n ln -s "/etc/noetharaclipz-isolated/continuous/$NC_PILOT_DEPLOYMENT" /etc/noetharaclipz-isolated/continuous/current
   sudo -n install -m 0644 /etc/noetharaclipz-isolated/continuous/current/systemd/noetharaclipz-isolation.service /etc/systemd/system/noetharaclipz-isolation.service
   sudo -n install -m 0644 /etc/noetharaclipz-isolated/continuous/current/systemd/noetharaclipz-continuous.service /etc/systemd/system/noetharaclipz-continuous.service
   sudo -n systemctl daemon-reload
   sudo -n systemctl start noetharaclipz-continuous.service
   ```

   Do not restart Docker or existing units. Boot enablement requires approval
   explicitly covering unattended startup; no shared-host reboot test is implied.
   Check only the new unit's journal and installed controller's `status` action.
8. **Verify the new v2 path on EC2** with a fresh post-approval upload through the
   normal website: genuine highlight, edit/save/refresh, queued Export and private
   Download. Check one-job enforcement, source/provenance, retained metrics,
   cancellation, one bounded recovery and consent revocation. Confirm the original
   upload's hash and existing service baseline. These hosted v2 results are still
   pending; prior v1 benchmarks and local contract tests do not substitute for them.

## Revocation and safe rollback

The owner can revoke through the same private login file:

```sh
python scripts/continuous_consent.py revoke --account /secure/pilot-account.json --consent "$NC_PILOT_CONSENT"
```

An operator can use `operator-revoke` with owner/consent and an authorization
reference, or `exclude --job ...` for one explicitly chosen pilot job. There is
no removal/release command for exclusions. Host-side durable revocation:

```sh
sudo -n python3 /etc/noetharaclipz-isolated/continuous/current/code/host/continuous_host.py revoke --manifest /etc/noetharaclipz-isolated/continuous/current/public/manifest.json
sudo -n systemctl stop noetharaclipz-continuous.service
```

The local marker survives reboot and prevents automatic resumption. The process
group stops on grant loss; server publication is denied transactionally once
revocation commits. `status` and `revoke` remain available after manifest expiry.
Leave the isolation rules, models, private evidence and queued data in place.
Disable only the new service if unattended restart was enabled. Never flush
firewall chains, delete existing volumes, reset original jobs, clear a blocked
latch/budget or reuse an expired manifest to recover. Review the cause and prepare
a new approved configuration instead.

## Verification and remaining blockers

Local verification includes worker tests, real PostgreSQL/PGMQ permission/consent
tests with two-session revocation races, systemd unit syntax/dependency checks,
and an import-only smoke in the existing image with the changed read-only source
overlay. That smoke has no network, model assets or credential mount and cannot
start a worker. All reports explicitly distinguish fixtures from actual inference.
The worker suite passed **272 tests with one optional sample skipped**, including
43 new control cases; Ruff passed. Both actual PostgreSQL revocation races and
the isolated unit-parser check passed. The import-only check uses the existing
image with no model/credential mount or network. The
[preparation evidence](evidence/continuous-worker-preparation.json) records hashes
and preservation checks for all 55 earlier evidence files, 30 existing deployment
files and eight migrations.

The SQL application and fresh pilot identity/owner-consent checkpoints are
complete. The remaining deployment blockers are separate operator approval of
an immutable pilot manifest/window, fresh EC2
installation/preflights, explicit startup authorization and live v2 pilot
verification. Production notification delivery and sustained-load/maximum-
input capacity remain future operational checks. No infrastructure upgrade or
paid service is required for preparation or recommended by the passed baseline.
