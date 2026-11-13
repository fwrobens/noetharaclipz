# Production smoke test

Manual checks after approval A publishes the reviewed Draft PR #1 head to
`https://noetharaclipz.lovable.app`. This document does not publish, merge, change
Auth, enqueue a job, or start EC2.

The reviewed SHA is `git rev-parse HEAD` on the pull-request branch that
contains [deployment-checklist.md](deployment-checklist.md). Call that value
`REVIEWED_SHA` below. Rollback SHA stays
`e70ca9fd8f8156e22e3e450ae4095be35cfec47e`.

Invited pilots: `21b61ad1-bda4-4abd-ac35-7a0bf477ed69` and `f0235878-e130-45a9-a031-f21cd91da7b9`.
Uninvited confirmed QA identity: `c7ade7f9-2003-4a38-ae19-393fffae8452`.
Do not record email addresses, passwords, links, or tokens in the results.

Step 7 is expected to fail closed only after approval B (signup OFF). Before B,
mark that row blocked, not failed.

## Steps

1. **Live revision.** Open `https://noetharaclipz.lovable.app/` and read `data-commit-sha` on the homepage.
   - Expected: the attribute equals `REVIEWED_SHA`.
   - Abort if it still equals `e70ca9fd8f8156e22e3e450ae4095be35cfec47e` or any other SHA.

2. **Release identity.** `GET https://noetharaclipz.lovable.app/api/release` with no cookies and no Authorization header. Also send `HEAD` and `POST`.
   - Expected: GET returns 200, `Cache-Control: no-store`, and JSON `build` equal to `REVIEWED_SHA` and to the homepage `data-commit-sha`. `build` is not `development` and not `unknown`. `app` is `NoetharaClipz`, `mode` is `owner-scoped-beta`, and `access.mode` is `authenticated-owner-allowlist-v1`. `access.owners` is 2 and `access.sha256` is `8366d22defa4f3bf3ee9e944845aa8cde6b9567242db042040ffac2ddc427651`. `access` has nothing else. The body does not contain a user id, email, access token, refresh token, service key, or cookie. HEAD returns 200 with an empty body. POST returns 405.

3. **Callback route.** Open `https://noetharaclipz.lovable.app/auth/callback` with no `code`.
   - Expected: not 404. The page status text says the sign-in link is missing its code, and a Sign in link is present.

4. **Invited pilot login.** Sign in as the invited pilot with email magic link or password. Do not create a user.
   - Expected: the provider returns to `https://noetharaclipz.lovable.app/auth/callback` on that production origin, then the app lands on `/dashboard`. The session belongs to `21b61ad1-bda4-4abd-ac35-7a0bf477ed69`.

5. **Logged-out gate.** In a fresh session with no cookies, open `/dashboard`. Then sign out the invited pilot and open `/dashboard`, `/library`, and `/project/<existing-id>`.
   - Expected: the no-cookie `/dashboard` request redirects to `/login`. After logout the session is cleared and each protected route redirects to `/login`. `/auth/callback` without a code still loads (step 3) and does not restore a session.

6. **Uninvited confirmed account.** Sign in as `c7ade7f9-2003-4a38-ae19-393fffae8452` through the same production callback.
   - Expected: the account is denied. The app signs that session out locally and/or the server responds 403 for a private page, including a private download. The account does not remain on `/dashboard`. No user is created, banned, or deleted.

7. **New signup, only after approval B.** Attempt a new email signup on the production origin. Use an address that is not one of the existing accounts. Do not record the address.
   - Expected after B: the signup is rejected. Confirm email stays ON, anonymous sign-in stays OFF, and the redirect list is still the eight snapshotted entries.
   - Before B: do not run this step. Leave the row blocked. Hosted signup is still ON in the pre-change snapshot.

8. **Authenticated download.** As the invited pilot, open an existing completed clip and use the website Download button. Do not render a new export.
   - Expected: the browser saves the existing private MP4. The request is a signed `rendered-clips` URL for that owner's object, not a public object URL. No new `processing_jobs` row appears.

9. **Private storage authorization.** Using the same existing object, and without starting a worker:
   - Expected: an unauthenticated or anonymous request returns 400 or 403. A request as the other confirmed user is denied. A signed URL that previously worked returns 400 after it expires. The object bytes are unchanged.

10. **Credits meter.** On the signed-in dashboard, read the credits meter.
    - Expected: the published meter is still visible, including the sample 120/150 figures, and it shows the **Demo** label and the text “Sample balance, not your account.” It does not claim those numbers are the account balance.

11. **No processing.** Read the queue and the EC2 instance state. Do not call a start, approve, or enqueue action.
    - Expected: no new job was enqueued by this smoke test. The original queued upload is still untouched. EC2 remains stopped. Global processing remains off.

## Pass / fail

| # | Check | Result | Notes |
| --- | --- | --- | --- |
| 1 | `data-commit-sha` equals `REVIEWED_SHA` | | |
| 2 | `/api/release` `build` equals `REVIEWED_SHA` and `data-commit-sha`; mode is `owner-scoped-beta`; access mode is `authenticated-owner-allowlist-v1`; `access.owners` is 2; digest is `8366d22defa4f3bf3ee9e944845aa8cde6b9567242db042040ffac2ddc427651`; POST is 405 | | |
| 3 | `/auth/callback` is not 404 | | |
| 4 | Invited pilot login returns through production `/auth/callback` | | |
| 5 | No-cookie `/dashboard` redirects to `/login`; logout does the same for protected routes | | |
| 6 | Non-allowlisted confirmed account is denied (signed out or 403) | | |
| 7 | New email signup is rejected after approval B | blocked until B | |
| 8 | Authenticated Download of an existing private clip succeeds | | |
| 9 | Anon/unauthenticated object request is 400/403; other user denied; signed URL expires | | |
| 10 | Credits meter shows the Demo label | | |
| 11 | No jobs enqueued; EC2 remains stopped | | |

Mark each row pass or fail. Do not invent a pass.

## Abort and rollback

If any row is fail, stop. Do not enqueue a job, start EC2, enable global
processing, merge the PR, or edit storage, jobs, or consent.

Roll back the site: Lovable History, hover the newest Published row created by
the publish, and use Revert (circular arrow) to
`e70ca9fd8f8156e22e3e450ae4095be35cfec47e`. If approval B was already applied,
restore “Allow new users to sign up” to ON. Leave the Site URL and the eight
redirect URLs as snapshotted. Revert stays disabled on the currently published
row, so this rollback exists only after a newer publish.

Then re-check row 1 against the rollback SHA and row 11. Stop when both match.
