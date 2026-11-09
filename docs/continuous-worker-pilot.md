# Continuous local-worker pilot — implementation prepared, not deployed

The implementation builds on `0195e13` and its completed EC2 reliability trial;
pilot preparation continues from `b883b01`. The consent migration is already
applied. A fresh dedicated pilot account now has explicit owner consent;
operator approval and worker startup remain pending. No completed AI/media
benchmark was repeated. The earlier QA containers/assets/evidence are unchanged.

## Current limited pilot proposal — 2026-11-09 UTC

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
