# Limited owner-scoped beta — preparation, November 11

**Prepared, not deployed.** The expired 24-hour deployment remains stopped.
This plan proposes an operator-attended **120-minute workload trial** of the
current website and reviewed worker, followed by automatic expiry. No new
consent, operator approval, UTC window or active manifest is issued here.
Draft PR #1 remains draft. Publication, installation, worker startup and the
single proposed fault injection require separate approval of concrete hashes.

## What is reused

The [24-hour operational result](continuous-24h-pilot.md) and earlier real
crash/lease recovery results stand. Do not repeat the 500M/2.2B benchmarks,
the long idle soak or restart any archived container. All **25 runtime source
files and both existing worker unit files** remain unchanged by beta preparation.

Use existing instance `i-0be10e530045fc650`, **m6i.2xlarge**, us-east-2, and image
`sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`.
Keep pinned SmolVLM2-500M/Whisper assets, **8 GiB RAM, two CPUs, no extra swap,
256 PIDs, one active job, no public ports**. Explicit local provider, Gemini
free-tier flag false, global claims false and boot startup disabled.

The original job `9c5c8869-ec2e-4a3e-927d-697615bb58a3` is permanently excluded.
The [November 11 read-only check](evidence/beta-live-read-only.json) confirms
v2/future-only consent, global claim denial and its unchanged complete-row hash
`deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb`:
**queued, zero attempts**. Never release, reset, cancel, claim or process it.
No SQL/migration, AI gateway, shared container or host-wide configuration changes
are part of this preparation.

## Hosted frontend candidate

The existing Lovable/TanStack design, Supabase project and Cloudflare build target
are preserved. Beta builds add:

- Account settings with an explicit consent checkbox, request/pending/expiry
  states and revocation using the **already deployed owner-only v2 RPCs**.
  Loading the page records no consent. It cannot grant operator approval.
- An upload admission check before storage reservation, requiring an active
  consent generation and ready scoped worker. Invitation-only login presentation;
  unverified Google/signup buttons are hidden in beta mode.
- `/api/release` with the public source commit/mode and no-store response,
  plus noindex headers. Neither is an access-control mechanism.
- A pinned, **local-only Cloudflare runtime** preview of the production artifact,
  separate from the application dependency lockfile. No Cloudflare login,
  deploy, remote preview, account token or new hosting resource is needed locally.

The browser admission check is UX; **server v2 claims, job bindings, consent
revocation and RLS enforce processing and ownership**. Existing legacy upload
RPCs can still reserve owner storage; hiding signup does not close Supabase
registration or enforce a server upload allowlist. Limit invitations, check
existing Auth settings/quotas, and treat abuse-resistant public registration as
outside this one-owner beta. Any stricter schema gate needs a separate reviewed
database change; none is silently added or applied here.

Prepare and check a candidate from committed source:

```sh
npm ci
npm run build:beta
npm run setup:beta-preview
npm run preview:beta
```

The preview is a **local verifier**, not the beta hosting service or EC2 worker.
In a second local terminal:

```sh
CHROMIUM_PATH=/usr/bin/chromium python scripts/check_beta_frontend.py \
  --origin http://127.0.0.1:8081 --build "$REVIEWED_FRONTEND_COMMIT" --allow-loopback
```

`test-results/beta/build.json` seals output hashes and scans for configured private
credentials. A dirty build is explicitly ineligible for transfer; `--allow-dirty`
exists for local development only. Hosting must execute `npm run build:beta` or
set the same reviewed **public** `VITE_NC_BETA_MODE=true` and exact
`VITE_NC_BUILD_SHA` for its existing production build. No service key belongs in
hosting public variables or this frontend artifact.

Read-only inspection of **https://noetharaclipz.lovable.app** on November 11
found `/auth/callback` and `/api/release` returning **404**. It is not the new
verified beta release. After publication is separately authorized, use the
existing hosting connection and production SSR build; do not serve `vite dev`,
create another hosting subscription or use Lovable generation credits.
Fail the deployment gate until these commands pass against the exact HTTPS site:

```sh
npm run check:beta-host -- https://noetharaclipz.lovable.app "$REVIEWED_FRONTEND_COMMIT"
CHROMIUM_PATH=/usr/bin/chromium python scripts/check_beta_frontend.py \
  --origin https://noetharaclipz.lovable.app --build "$REVIEWED_FRONTEND_COMMIT"
```

Also verify the production origin and `/auth/callback` in Supabase's allowed
redirect settings, secure SSR cookies and correct sign-in/sign-out after refresh.
Use an already confirmed dedicated QA owner through the secure auth workflow;
SMTP delivery and third-party OAuth are not assumed tested. Capture the current
hosting release/configuration before any approved change so it can be restored.

## Spaced workload and evidence

[Licensed corpus](../deploy/beta/corpus.json) and its
[actual local preparation receipt](evidence/beta-corpus-preparation.json) contain
**three distinct games**, six uniquely hashed 60-second samples and attribution:
SuperTuxKart (CC BY-SA 4.0), 0 A.D. (CC BY-SA 4.0), Minetest (CC BY-SA 3.0).
All six decoded successfully; combined upload bytes **29,151,206**, each below
15 MB. Only public 480p derivatives were downloaded. No footage is committed or
uploaded during preparation. Keep license/attribution with every shared derivative.

```sh
python scripts/prepare_beta_corpus.py --output test-results/beta/corpus-new
```

This verifies locked source hashes and prepares inputs; it runs no AI. The receipt
records sample hashes for the reviewed FFmpeg build; a different encoder build
can change output hashes. Compare output receipts and review/reseal any changed
media instead of claiming identical samples. B/D are silent video, so an empty
transcript/audio result is expected. A/F overlap in one original; D/E are distinct
intervals of B/C's originals. **Six samples are not six independent games**.
These samples do not establish spoken-reaction or funny-moment accuracy; add a
separately authorized commentary recording in a later scope if that is required.

| Relative time | Input/action | Required actual evidence |
| --- | --- | --- |
| T+00 | A, fresh racing input | Hosted sign-in → upload/instructions → actual local inference → evidence-backed highlight → edit/Save/refresh → normal Export → private MP4 download/decode |
| T+20 | B and C, both submitted before the first completes | Two outstanding owner jobs; at most one active lease/processing job; record wait times and independent provider provenance; normal edit/export for selections |
| T+50 | D, cancel in actual inference then UI Retry | Cancellation acknowledged, old attempt cannot commit results, bounded same-job retry, no duplicate highlights/exports |
| T+75 | E, one approved worker-only fault during its active lease | Exact new container/generation/job recorded; controller restarts only it, reruns isolation before grant, lease reclaimed, stale token denied, one successful completion; real alert received/acknowledged |
| T+100 | F, fresh late-window input | Fresh inference/result persistence, edit/Export/download still work after the earlier jobs; record any legitimate cache reuse separately |
| T+110 | Read-only data/security checks; optional specifically approved owner revocation | Cross-user and anonymous private-object denial, signed URL expiry, saved edits; if revoked, no new claim/result and readiness goes false |
| T+120 | Fixed expiry, no extension | Automatic stop, grant absent, inactive/boot-disabled units, no active leases, final peaks/logs, unchanged protected upload/six other services/archived evidence |

Timestamps are relative **only**; select an exact two-hour UTC window just before
review. Do not compress spacing if delayed, substitute fixtures or extend expiry.
If an earlier job exceeds its slot, record it and pause/abort later submissions
within the same deadline. No foreground SSM scheduler or keepalive is needed.
The operator/cloud test runner drives the website; **systemd owns the worker**.

Use the gated `scripts/beta_acceptance.py` wrapper around the existing genuine
browser acceptance for each sample. It refuses localhost, the wrong deployed
release, expired/old deployment, wrong owner/consent, unready provider, early/late
submission, changed sample hashes and reused local attempt directories. It
forces the existing path to local mode; it never issues consent/approval or
injects a crash. B and C may run in separate cloud test processes; the worker
still has one active job. Supply `NC_TEST_EMAIL`/`NC_TEST_PASSWORD` only through
the existing private QA credential workflow, never in Git, commands or chat.

```sh
python scripts/beta_acceptance.py --approval-file "$PRIVATE_BETA_APPROVAL" \
  --approval-sha256 "$REVIEWED_APPROVAL_SHA256" --sample-id A \
  --media-directory "$VERIFIED_SAMPLE_DIRECTORY" --output "$NEW_RESULT_DIRECTORY"
```

The separately issued private approval must bind the new deployment/owner/consent,
`not_before`, `valid_until`, exact frontend HTTPS origin/build, corpus receipt
SHA256 and explicit workload/cancellation scope. `provider=local-smolvlm2`,
resource caps, no boot/global/Gemini flags must match. A–F are run once each;
review any failed attempt rather than bypassing its local latch. For recovery,
the operator's separate crash scope must name the exact **new** container and
active QA job; do not restart Docker, SSM, a previous trial or another app.

Record per job: source/result hashes, timestamps and audio/transcript/visual
evidence separately, model/revision/token counts/cache hits, queue wait/inference/
render/download duration, attempt count, clip boundaries and human relevance
judgment. A model abstention is valid negative quality evidence; never manufacture
a highlight to make Export pass. Require at least one complete genuine MP4 flow
and report which other games produced usable selections. This is workload and
fault coverage, not a broad accuracy benchmark or max-input throughput claim.

## Independent alerts

[Watchdog](../deploy/beta/watchdog.py), inert configuration and a new disabled
systemd template are prepared separately from the reviewed worker overlay.
The unit deliberately has **no dependency on the worker's lifetime**. It reads
only the new deployment's controller status and scoped Docker state, never
worker credentials, queue contents or mutating Docker/systemd commands.

It detects stale/inactive monitoring, exit-zero security/consent halts, worker
backoff/not-ready state, unexpected shutdown, memory pressure and deadline
overrun. Events/recoveries are deduplicated across monitor restarts, written to
private bounded files and journal; the delivery outbox uses stable event IDs,
three retries and redacts transport errors. Local records are not external alerts.

The user has **not selected an external alert destination**. Delivery therefore
defaults off. An existing HTTPS webhook can be configured later from a root-only
0600 file, pinned destination hash/host and separate notification approval.
Public DNS/IP checks, pinned connection with TLS hostname verification, no
redirects and a minimal metadata-only payload protect that route. No real
notification, credential request, SNS/CloudWatch/SES resource or subscription has
been created. **External delivery and a human acknowledgment remain beta blockers**;
a deliberately operator-attended local-log-only trial needs explicit exception.

Before approved installation, bind the watchdog/config/unit SHA256s alongside
the new worker manifest, verify root ownership/non-writable non-symlink parent
directories, precreate only `/var/lib/noetharaclipz-isolated/beta-alerts/NEW_ID`
(0700), and install only the new watchdog's files. Its separately approved env
file contains just `NC_APPROVED_WATCHDOG_SHA256`, not a credential. Start it for
that new ID immediately before the authorized worker. It has **64 MiB, 5% CPU,
16 tasks, at most three starts** and a bounded lifetime through two minutes after
expiry. Boot enable is absent. The main worker's tested caps are unchanged.

The independent monitor cannot diagnose its own complete failure or notify
during a host/network outage. Check its unit and durable `state.json` timestamp
at each workload checkpoint; an existing external dead-man service would need
separate selection/approval. Do not claim full host-outage alerting.

## Deployment gates, approval and rollback

1. Pass local tests/production artifact checks and retain code/build/corpus hashes.
   Review existing hosting/Auth configuration read-only and approve publication
   separately. Prove the exact hosted release before any workload job.
2. Obtain a **fresh authenticated owner consent request** in Account settings.
   The previous pilot identity may be reused with a new generation. Never reuse
   its expired consent or fabricate a request through an operator credential.
3. Stage a new private source/config handoff using the existing private Supabase
   transfer path. Fresh read-only SSM checks must show ≥10 GiB available RAM,
   ≥20 GiB disk, six healthy/unchanged other containers, old trials stopped,
   reviewed image/model/source/unit hashes, no active worker/grant, disabled boot
   units, expected bridge/DNS/firewall ordering and private secret-file metadata.
   Review the previously reported broad SSH ingress separately; no new beta ports
   or host-wide firewall/Docker changes are authorized here.
4. Seal a **new** deployment ID, consent generation, two-hour UTC window,
   operator approval reference and immutable manifest, plus frontend/corpus/
   watchdog digests. Review media/transfer/storage allowances; existing EC2 has
   no new provisioned compute cost if already running, but storage/egress are
   metered and not assumed free. This task activates no billable service/CI.
5. Separately approve exact publication (if still pending), private installation,
   that owner's server processing approval, detached systemd startup, external
   notification test/destination, and at most one scoped fault. No boot/global
   permission is included. The old five-minute launch gate remains: late commands
   fail; prepare a new reviewed window instead of extending an approval.
6. The reviewed installer moves only the dedicated `current` symlink after
   verification, preserves expired configuration/evidence, orders isolation first,
   then starts the dedicated controller with `systemctl start --no-block`.
   Every new generation must prove actual kernel quotas and live scoped denial
   counters before its processing grant. Retain metrics/logs on disk independent
   of SSM; no worker foreground shell, `nohup`, reboot or Docker restart.
7. Stop only this new deployment on security/baseline change, repeated failure,
   insufficient headroom or loss of authorization. Revoke its server consent/
   operator approval, remove its grant and latch it before scoped service stop.
   Preserve old/new logs, jobs, media and historical evidence; do not reset jobs
   to force a pass. Stop the new alert unit after its final snapshot. Restore the
   prior pointer only after the new worker is stopped; **never start the expired
   pointed-to deployment**. Revert the website to its captured release if the
   separately approved frontend rollout fails. Do not flush shared firewall
   chains, stop existing apps or delete the dedicated network under a live job.

**Remaining blockers:** external alert destination/real delivery acknowledgment;
production hosting publication and exact-release/auth checks; fresh owner
consent; fresh EC2 preflights/private transfer; final UTC window/manifest and
separate installation/start/fault approval; then the actual spaced hosted workload
and final security/expiry evidence. No completed EC2 benchmark is a prerequisite
to repeat. Nothing in this plan makes the service active for normal users.
