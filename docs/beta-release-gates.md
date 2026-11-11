# Owner-scoped beta release gates — November 11

This continues `56bc531`. **Preparation only:** no website publication, monitoring
installation, processing approval or EC2 startup. The expired deployment stays
stopped. The [workload plan](owner-scoped-beta.md) and its completed benchmarks
stand; this stage verifies the new access restrictions and seals a new frontend.

Fresh owner consent was explicitly authorized and recorded as generation
**`0e8f4eb3-53a9-4ad0-8aa0-d0b0a19dc2a2`**, then independently read back through
the normal authenticated owner RPC. Approval/expiry remain null. No processing
approval, new user, password reset, email delivery or worker start accompanied it.

## Alert proposal selected for review

Use the [operator-attended local-log-only proposal](../deploy/beta/alert-delivery-proposal.json)
on the existing host. No external webhook is configured in this session. This
fallback is a normal proposed option, subject to explicit approval and an assigned
operator; it is not represented as delivered external alerting.

The existing reviewed independent watchdog records deduplicated faults/recoveries
in private bounded files and the journal. Its own dedicated unit uses at most
64 MiB / 5% of one CPU, has bounded starts and remains disabled at boot. It
continues observing when the worker/controller fails and takes no worker actions.
No SNS, CloudWatch, SES, mail server or subscription is provisioned.

An assigned operator must inspect fresh controller status, watchdog state and
unacknowledged fault records **every two minutes**, before each sample, around
the one approved fault, and at expiry. Acknowledge a fault within two minutes.
Record observations with UTC times; do not invent acknowledgments. A visibility
gap over five minutes makes the attended trial inconclusive: pause submissions
and stop only the new beta through its scoped rollback when access is available.
The controller's autonomous deadline, expiring grant and resource/security checks
continue independently of SSM. A lost SSM session never owns the worker lifetime.
This option cannot notify an operator outside the host during a complete host or
network outage. It is unsuitable for an unattended beta.

If an existing HTTPS webhook is later selected, pin its host and private 0600
file hash, approve a metadata-only test notification and verify receipt before
switching delivery on. The current proposal sends no notification and asks for
no pasted token or webhook secret.

## Proposed existing hosting target

Use **https://noetharaclipz.lovable.app**, its existing Lovable/TanStack/Nitro
Cloudflare pipeline and `npm run build:beta`. No alternate hosting service,
Cloudflare account, public port, subscription or generation credit is introduced.
If the existing platform cannot use that command, it must supply the same exact
public beta/build settings and produce the reviewed release identity. Otherwise
publication must stop. Never substitute a development server or a different build.

The [hosting proposal](../deploy/beta/hosting-proposal.json) binds these controls:

- Requests are private by default, including newly added routes and server
  functions. The current public entry pages/build assets are explicitly exempt.
  Protected requests validate the cookie with **native Supabase GoTrue**.
  Only confirmed, non-anonymous authenticated owner
  `21b61ad1-bda4-4abd-ac35-7a0bf477ed69` is invited. Other signed-in identities
  receive **403**; invalid/missing sessions go to login; Auth outages fail closed.
  The identity server function applies the same policy, including client navigation.
- The gate is compiled on the server, not a browser allowlist. `/api/release`
  exposes the exact source commit and access-policy digest, without a credential
  or full owner list. Owner approval for processing is still a separate database
  control; an expired processing grant does not revoke private read/download access.
- Authenticated HTML is private/no-store, varies by Cookie and is noindex.
  HTTPS cookies are host-only/Secure/SameSite=Lax, with refresh propagated into
  both the downstream SSR request and response. Supabase's browser session cookies
  remain readable to its browser SDK; they are not claimed to be HttpOnly.
- Signed media caching now requires a session, is keyed by owner and clears on
  identity changes/sign-out. Download signing and private objects still use native
  Storage RLS. A signed URL is a temporary bearer capability until expiry; logout
  does not retroactively revoke a URL that was already issued.

This proposed publication temporarily restricts workspace pages on the existing
hostname to the dedicated QA owner. Other users' data and queued uploads are
preserved. Direct Supabase APIs retain their existing ownership/consent/RLS rules;
the HTTP gate is not presented as a database upload allowlist.

### Auth configuration review

Native non-sending probes accepted the explicit production callback. Untrusted
`.invalid` and unapproved Lovable-host redirects were rejected and fell back to
**`http://localhost:3000`**. Public Auth settings show email confirmation required,
Google/anonymous sign-in disabled, but public signup still enabled.

Prepare this narrow Auth change for approval:

1. Snapshot the actual Site URL and entire Redirect URLs list through the existing
   dashboard/management integration. This session has no such reader; a project
   server key cannot substitute for management access. Functional probes do not
   establish the complete configured list.
2. Set Site URL to **`https://noetharaclipz.lovable.app`**. Require the exact
   **`https://noetharaclipz.lovable.app/auth/callback`** entry. Preserve legitimate
   reviewed exact entries and narrow unapproved wildcards only after inventory;
   never overwrite an unread list.
3. Propose **disable public signup for this limited beta**, preserving existing
   accounts, passwords, confirmation requirements and disabled Google/anonymous
   providers. No email is sent and no provider/subscription is enabled here.

The API-level consent/RLS policy is already deployed; no migration is needed or
reapplied. Native authentication tests use existing dedicated QA identities,
non-sending admin-generated links and normal authenticated sessions. They do
not create users, reset passwords or turn those identities into service operators.
Fresh consent may be recorded only following the owner's explicit new response.

### Publication and rollback gate

Before authorization, capture the **current Lovable published revision/deployment
ID**, previous source/configuration and complete Auth URL/signup settings. GitHub
deployment records were unavailable to this connection. A public HTML snapshot cannot reconstruct the
old SSR worker and is not an adequate rollback artifact.

The identified Lovable project is
**`40ff324d-5ed8-4890-ac90-cff43cfb1144`** and source edit
`0714528508a7f835a4d4f4455087c6e234d52569`. That edit remains **unverified as a
published revision** and is not a rollback target. Only the actual History entry
marked Published plus the Auth inventory completes this gate.

The user selected **the latest design committed to `main`**, confirmed as
`0714528508a7f835a4d4f4455087c6e234d52569`. That lineage is integrated into
`feat/real-video-pipeline` without rewriting either history or merging Draft PR #1.
The current candidate preserves its landing page, branded auth, dashboard,
projects/activity pages, onboarding, fonts and styles. It connects those screens
to the reviewed real pipeline:

- One cookie-based native session supports both the new dashboard and existing
  project/editor routes, including refresh, owner verification and cache clearing.
- Creator server functions enforce the verified identity and RLS. Beta upload
  reservation/finalization additionally require the matching active consent and
  ready scoped worker on the server. The browser cannot approve an owner.
- The new composer uses the tested private resumable upload transport, existing
  `prepare_upload`/`finalize_upload` RPCs, owner/path-scoped resume fingerprints
  and actual progress. It opens the real queued project after upload.
- Saved dashboard projects link into the real workspace and highlight editor;
  active analysis/render jobs poll for progress. The normal Export dialog remains
  connected to queued MP4 rendering and authenticated private downloads.
- Beta auth retains the main design while hiding unenabled signup/OAuth flows.
  Main's "Clean" onboarding choice maps to the real renderer's "Minimal" style.
- The exact existing logo is bundled without visual edits; its original
  project asset, byte length and digest are recorded in the
  [logo provenance](evidence/beta-main-logo-provenance.json). This makes local
  and hosted artifacts independent of Lovable's injected asset route.

The initial [divergence record](evidence/beta-lovable-source-divergence.json)
remains an unchanged historical comparison. The
[resolution record](evidence/beta-main-source-integration.json) records the user's
choice. The previous PR-only artifact is superseded; the combined frontend must
be resealed from its new clean commit. **Source alignment is complete; publication
and exact hosted rollback verification remain separate gates.**

Publication approval must name the sealed frontend commit, artifact-map digest,
access-policy digest, same hostname and exact Auth diff. On failure, restore the
captured existing hosting revision and exact prior Auth values; retain database,
private media, original queue and worker evidence. No worker starts as part of
hosting rollback. **No exact rollback revision has been fabricated.**

After an approved publication, verify `/api/release` matches all three identities,
the callback exists, allowed-owner pages succeed, uninvited/forged sessions are
denied, refresh/sign-out behave correctly, old saved edits persist and native
private downloads deny anonymous/cross-owner access. Fail before creating a
workload job if the published build or access digest differs.

## Two-hour workload packet

[Disabled workload proposal](../deploy/beta/workload-proposal.json) preserves the
existing m6i.2xlarge, 500M image, 8 GiB / 2 CPU / one-job limits and the six
verified input hashes. Proposed UTC window: **November 12, 09:00–11:00**.
This is not a reservation or start approval. If the operator cannot attend,
prepare a new disabled window for review; do not extend an old approval.

After fresh authenticated owner consent, `scripts/prepare_beta_pilot.py` seals
the candidate and computes prospective activation digests without writing an
active manifest or issuing approval. It checks the clean frontend build, native
unapproved consent generation, unchanged 25 runtime files/two worker units,
six actual sample files and future two-hour window. Example preparation only:

```sh
python scripts/prepare_beta_pilot.py --build test-results/beta/build.json \
  --owner-consent "$FRESH_CONSENT_RECEIPT" \
  --start-utc 2026-11-12T09:00:00Z --access-sha256 "$REVIEWED_ACCESS_SHA256" \
  --deployment-id "$NEW_BETA_DEPLOYMENT_ID" \
  --media test-results/beta/corpus --output "$NEW_PRIVATE_REVIEW_DIRECTORY"
```

Only the scoped runner submits A at T+0, B/C at T+20, D cancellation/retry at
T+50, E's one separately approved worker-only fault at T+75, F at T+100 and
read-only security/expiry checks afterward. No ad-hoc uploads. The sample hashes
are enforced by the reviewed runner; the deployed queue policy remains
owner/future-job scoped, not a server-side media-hash allowlist. Original job
`9c5c8869-ec2e-4a3e-927d-697615bb58a3` stays permanently excluded.

Fresh SSM admission reuses the reviewed read-only collectors against the stopped
24-hour predecessor. It verifies RAM/disk/Docker, exact image/model/unit/source
hashes, existing service states, old evidence, disabled boot startup and unchanged
network/firewall ordering. A private preparation receiver writes only a **new
`/var/tmp/nccz-beta-…`** staging area and a read-only receipt/report. It cannot
install monitoring, read worker secrets, approve an owner, load models, start a
container or alter network rules. Runtime quotas and active denial probes remain
mandatory before queue access in every subsequently authorized generation.

## Minimum approvals

Fresh owner consent is complete. **Two operational approvals remain**, after
the dashboard inventory and fresh SSM preflights:

1. **Hosting/Auth release approval**, after the current publish revision and Auth
   inventory are read: exact new frontend identities/hostname, narrow Auth diff
   and restoration of the captured prior release/configuration if needed.
2. **One bounded EC2 trial approval**, after fresh preflights and consent: exact
   new manifest/digests/window; named attended operator/local-log-only mode;
   dedicated monitor files/unit installation; only this owner's processing approval;
   detached systemd start; six samples, cancellation/retry and at most one new-worker
   fault; expiry/rollback. No boot enable, global processing, Gemini, paid service,
   host-wide Docker/network change or action on an old trial is included.

Dashboard/SSM reads are preparation evidence, not additional deployment approvals.
The worker stays stopped while any required evidence or approval is missing.

## Verification performed in this stage

- 41 frontend tests and TypeScript pass, including main dashboard routing,
  server-side consent/readiness admission, resumable upload integration,
  native-user policy checks,
  forged/missing sessions, private-by-default/encoded paths, Auth outages,
  cookie refresh propagation and cross-owner signed URL cache isolation. Lint
  retains 18 fast-refresh warnings and no errors. Imported design files were
  formatted to the repository rules; generated files were selected from an
  existing side or regenerated by the route plugin, never hand-edited.
- 41 focused beta worker-policy/preparation/watchdog tests pass. No full model
  benchmark, new inference, upload, export or queue consumer was run.
- The redesigned production runtime passed invited/uninvited owner checks on
  mobile and desktop using native QA sessions. Saved real projects open in the
  workspace/editor, trim settings survive refresh, pending consent remains
  unapproved, and the normal Export dialog downloads the existing private MP4
  with its original SHA-256. No new render job or saved edit was created. This
  is read-only integration verification; a fresh redesigned hosted workload
  remains gated on publication and bounded processing authorization.
- [Native Supabase reads](evidence/beta-release-live-security.json) show the
  worker offline/unready, zero active leases, privileged RPC denied to the
  ordinary user (403), and the original upload queued/zero attempts/exact original
  row hash. The existing MP4 downloads authenticated with its exact original
  bytes/hash; anonymous, public and cross-owner access/signing fail. A temporary
  signed URL returned 206 then 400 after its actual expiry.
- The initial new production artifact passed anonymous mobile/desktop checks
  under stock Wrangler. Authenticated workerd fetch hit this task's direct-TLS
  restriction and failed closed (503). A separate pinned **Miniflare/workerd
  outboundService** verifier forwards real TLS requests through the inherited
  proxy to this Supabase project only; it supplies no identity or mock response
  and does not alter artifact bytes. Real native sessions then returned 200 for
  the invited owner, 403 for the other QA identity and 302 for forged/missing
  sessions. The owner's pending consent rendered and persisted through refresh
  without browser exceptions or mobile overflow. These are local production-runtime
  checks; final HTTPS hosted acceptance remains pending publication authorization.
- [Auth probes](evidence/beta-release-auth-redirects.json) and
  [public settings](evidence/beta-release-auth-settings.json) are recorded without
  credentials or unused one-time links. They do not substitute for the full
  dashboard inventory. No Auth configuration was changed.

For this managed proxy environment, the optional local production verifier is:

```sh
NODE_USE_ENV_PROXY=1 node scripts/preview-beta-proxy.mjs
```

It binds loopback port 8082 only and is never an EC2 worker or hosting deployment.
The final clean build, source identity and disabled manifest are sealed after
this documentation commit and attached to the PR/private review handoff; no
later source is treated as byte-identical without resealing.
