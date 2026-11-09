# Proposed 24-hour owner-scoped EC2 pilot — preparation only

Status: **NOT STARTED; NOT APPROVED BY AN ACTIVE CONSENT RECORD**.
The 2026-11-09 21:00–21:30 UTC pilot ended safely at 21:29:46 UTC.
Do not restart, edit, extend, renew, or reuse its expired deployment receipt,
owner consent generation or signed active manifest. This document is a plan,
not an authorization to activate processing or to enable boot startup.

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
