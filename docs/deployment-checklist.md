# Deployment checklist — Draft PR #1

Docs only. This file does not publish the site, merge the pull request, change
hosted Supabase Auth, start EC2, or enable global processing.

## Reviewed commit

Publish the head of `feat/real-video-pipeline` (Draft PR
[#1](https://github.com/fwrobens/noetharaclipz/pull/1)) that contains this
checklist. That head is the reviewed commit. It sits directly on pipeline commit
`8bdbc55fcda09ed00f97dd1176f2d252b8c03726` plus this documentation. Do not publish
`8bdbc55` by itself, and do not publish the rollback commit as the new app.

| Role | Full SHA |
| --- | --- |
| Currently published / GitHub `main` / PR base / rollback | `e70ca9fd8f8156e22e3e450ae4095be35cfec47e` |
| Previous pipeline head (code freeze before these docs) | `8bdbc55fcda09ed00f97dd1176f2d252b8c03726` |
| Reviewed commit to publish | `git rev-parse HEAD` on `feat/real-video-pipeline` after this checklist is on the branch. That value is Draft PR #1's head. |

Confirm the reviewed SHA before publishing:

1. On the branch, `git rev-parse HEAD` prints one 40-character SHA.
2. In Lovable, open the project `40ff324d-5ed8-4890-ac90-cff43cfb1144` and select that same full SHA as the revision to publish. Do not publish whatever happens to be the current Published row.
3. After publication, view the source of `https://noetharaclipz.lovable.app/` and confirm the homepage `data-commit-sha` equals that same SHA.

Until that publish, the live homepage `data-commit-sha` remains
`e70ca9fd8f8156e22e3e450ae4095be35cfec47e`, and live `/auth/callback` and
`/api/release` return 404.

## Preconditions

Stop if any line is false.

- Draft PR #1's head is the reviewed commit above, and that head has been reviewed.
- The EC2 worker is stopped. Do not start it for this publish.
- Global processing stays off.
- The original queued upload is untouched, including job `9c5c8869-ec2e-4a3e-927d-697615bb58a3` (still excluded, not retried, not deleted).
- No storage objects, consent rows, or job rows will be edited.
- The credits-meter Demo label from the branch stays in the published UI.

## Pre-change Auth snapshot

Read-only dashboard inventory on 2026-11-13 for project `zxdnjnsghdnviflahvry`.
`changed` is false. Full copy:
[evidence/beta-auth-url-inventory.json](evidence/beta-auth-url-inventory.json).

- Site URL: `https://noetharaclipz.lovable.app`
- Redirect URLs, in order:
  1. `https://40ff324d-5ed8-4890-ac90-cff43cfb1144-thr_*.lovableproject.com/**`
  2. `https://40ff324d-5ed8-4890-ac90-cff43cfb1144.lovableproject.com/**`
  3. `https://id-preview*--40ff324d-5ed8-4890-ac90-cff43cfb1144.lovable.app/**`
  4. `https://noetharaclipz.lovable.app/**`
  5. `https://preview*--noetharaclipz.lovable.app/**`
  6. `https://project--40ff324d-5ed8-4890-ac90-cff43cfb1144-dev.lovable.app/**`
  7. `https://project--40ff324d-5ed8-4890-ac90-cff43cfb1144.lovable.app/**`
  8. `https://noetharaclipz.lovable.app/auth/callback`
- Allow new users to sign up: **ON** (`disable_signup=false`)
- Confirm email: ON
- Allow anonymous sign-ins: OFF
- Allow manual linking: OFF
- Email is the only enabled provider. Google, Phone, SAML, and every other OAuth provider are disabled.
- Accounts, with no email addresses recorded: 7 users, all confirmed, 0 anonymous, 2 banned (not pilots). Invited pilot `21b61ad1-bda4-4abd-ac35-7a0bf477ed69` and QA identity `c7ade7f9-2003-4a38-ae19-393fffae8452` are present and unbanned.

Entries 1–3 and 5–7 are preview/dev wildcards and are allowed redirect targets.
Recommend the owner consider trimming them after launch. Do not change them in
this deployment.

`supabase/config.toml` records the intended signup-off posture for review. It
does not change hosted Auth.

## Approvals required

These are three separate decisions. Do not combine them.

| ID | Approval | What it allows |
| --- | --- | --- |
| A | Publish the exact reviewed PR head in Lovable to `https://noetharaclipz.lovable.app` | One site publish only |
| B | Flip hosted “Allow new users to sign up” OFF (`disable_signup=true`) | Dashboard Auth toggle only. Existing confirmed users still sign in. New pilots are added by admin invite plus the app allowlist |
| C | Later, a separate bounded EC2 trial | Not part of A or B. Worker stays stopped until C exists on its own |

A does not authorize B or C. B does not authorize a publish or a worker. C does
not authorize changing the redirect list or turning global processing on.

## One-step deploy

Perform this only after approval A, and only this:

1. In Lovable, publish the reviewed commit identified above to the existing project so `https://noetharaclipz.lovable.app` serves that revision.

Do not merge the pull request. Do not mark it ready. Do not change Auth, storage,
jobs, consent, or EC2 in that step. Do not run a worker. Do not enable global
processing.

Approval B, if given, is a second manual action in the Supabase dashboard:
Authentication, Sign In / Providers, “Allow new users to sign up” OFF. Leave
Site URL, all eight redirect URLs, confirm-email, anonymous sign-in, manual
linking, and the email-only provider set as in the snapshot.

## Post-deploy verification

Run [production-smoke-test.md](production-smoke-test.md).

- After A, complete every smoke step except the new-signup rejection, which stays blocked until B.
- After B, complete the new-signup rejection step.
- Do not start step C. Confirm EC2 is still stopped and no job was enqueued.

Any failed smoke row aborts the release. Follow the rollback below. Do not
“fix forward” with another publish, an Auth experiment, or a worker start.

## Rollback

Use this if A was published and verification fails, or if B was applied and must
be undone. Do not practice it on the currently published row: Revert is disabled
there until a newer revision is published.

1. Lovable History. Hover the newest Published row (the one created by A). Choose Revert (circular arrow) back to `e70ca9fd8f8156e22e3e450ae4095be35cfec47e`.
2. Confirm the live homepage `data-commit-sha` is again `e70ca9fd8f8156e22e3e450ae4095be35cfec47e`. `/auth/callback` and `/api/release` return 404 again on that revision. That is the expected restored behavior.
3. If B was applied, restore “Allow new users to sign up” to ON (`disable_signup=false`). Leave the Site URL and the eight redirect URLs unchanged.
4. Do not touch storage, jobs, consent, or EC2. Do not delete users. Do not start the worker. Do not enable global processing.

Stop when the live SHA matches the rollback commit and the signup toggle matches
the pre-change snapshot if B had been flipped.
