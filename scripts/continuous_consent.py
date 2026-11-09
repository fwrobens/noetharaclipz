"""Future pilot administration only; no command runs during preparation.

Owner request/revoke uses an existing private login file. Operator approval uses
the existing bound service credential, never a credential in an argument/output.
Requires separately reviewed/deployed SQL; it never applies SQL or starts workers.
"""

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy/worker"))
from credential_envelope import server_headers  # noqa: E402

BASE = "https://zxdnjnsghdnviflahvry.supabase.co"
PUBLIC = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=(
            "request",
            "status",
            "revoke",
            "approve",
            "operator-revoke",
            "exclude",
        ),
    )
    p.add_argument("--account", type=Path)
    p.add_argument("--owner")
    p.add_argument("--consent")
    p.add_argument("--job")
    p.add_argument("--expires-at")
    p.add_argument("--authorization-reference")
    args = p.parse_args()
    with httpx.Client(timeout=30) as client:
        if args.action in ("request", "status", "revoke"):
            if (
                not args.account
                or args.account.is_symlink()
                or args.account.stat().st_mode & 0o077
            ):
                raise ValueError(
                    "Existing owner login file must be private; never paste credentials"
                )
            account = json.loads(args.account.read_text())
            login = client.post(
                BASE + "/auth/v1/token?grant_type=password",
                headers={"apikey": PUBLIC},
                json={"email": account["email"], "password": account["password"]},
            )
            login.raise_for_status()
            headers = {
                "apikey": PUBLIC,
                "Authorization": "Bearer " + login.json()["access_token"],
            }
            route, body = {
                "request": (
                    "request_processing_consent",
                    {"request_id": str(uuid4()), "terms_version": "local-video-v1"},
                ),
                "status": ("processing_consent", {}),
                "revoke": ("revoke_processing_consent", {"consent": args.consent}),
            }[args.action]
        else:
            if not args.authorization_reference:
                raise ValueError(
                    "Separate explicit operator approval/audit reference required"
                )
            if os.environ.get("SUPABASE_URL", "").rstrip("/") != BASE:
                raise ValueError("Wrong project")
            headers = server_headers(os.environ["SUPABASE_SERVICE_ROLE_KEY"].encode())
            route, body = {
                "approve": (
                    "approve_processing_consent",
                    {
                        "owner": args.owner,
                        "consent": args.consent,
                        "expires_at": args.expires_at,
                        "reason": args.authorization_reference,
                    },
                ),
                "operator-revoke": (
                    "revoke_owner_processing",
                    {
                        "owner": args.owner,
                        "consent": args.consent,
                        "reason": args.authorization_reference,
                    },
                ),
                "exclude": (
                    "exclude_processing_job",
                    {"jid": args.job, "reason": args.authorization_reference},
                ),
            }[args.action]
        response = client.post(
            BASE + "/rest/v1/rpc/" + route, headers=headers, json=body
        )
        if response.is_error:
            raise RuntimeError(
                "Consent operation rejected: HTTP "
                + str(response.status_code)
                + "; no automatic fallback/retry"
            )
        print(
            json.dumps(
                {
                    "operation": route,
                    "result": response.json(),
                    "worker_started": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
