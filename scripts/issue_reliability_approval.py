"""FUTURE USE ONLY after separate explicit user authorization.

No operation without the exact approved canonical plan SHA. Uses existing bound
Supabase credentials; creates one fresh processing identity and one fixed-window
receipt, never a PAT/server key. Do not run as part of preparation.
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy/worker"))
from reliability_host import validate_plan  # noqa: E402
from credential_envelope import server_headers  # noqa: E402


def private_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--explicit-user-authorization", required=True, help="Exact canonical plan SHA, supplied only after separate user authorization")
    p.add_argument("--account-output", type=Path, required=True)
    p.add_argument("--approval-output", type=Path, required=True)
    args = p.parse_args()
    raw = args.plan.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != args.explicit_user_authorization or args.account_output.exists() or args.approval_output.exists():
        raise ValueError("Explicit approval of this exact plan and new private output paths are required")
    plan = json.loads(raw)
    validate_plan(plan)
    approved_at = int(time.time())
    account = {"email": "nc-reliability-" + uuid4().hex + "@example.com", "password": secrets.token_urlsafe(32),
               "trial_id": plan["trial_id"]}
    # Persist pending identity details before the request; never retry creation
    # automatically if the network outcome is uncertain.
    private_new(args.account_output, account)
    base = "https://zxdnjnsghdnviflahvry.supabase.co"
    if os.environ.get("SUPABASE_URL", "").rstrip("/") != base:
        raise ValueError("Wrong configured project; do not create or recreate credentials")
    headers = server_headers(os.environ["SUPABASE_SERVICE_ROLE_KEY"].encode())
    request = urllib.request.Request(base + "/auth/v1/admin/users", method="POST", data=json.dumps({
        "email": account["email"], "password": account["password"], "email_confirm": True,
        "app_metadata": {"nccz_qa_trial": plan["trial_id"]}}).encode(),
        headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        user = json.load(response)
    account["id"] = user["id"]
    # This private account record contains no server credential and is not handed to EC2.
    pending = args.account_output.with_suffix(".identified.json")
    private_new(pending, account)
    approval = {"trial_id": plan["trial_id"], "plan_sha256": sha, "separately_authorized": True,
        "provider": "local", "global_processing": False, "gemini_enabled": False,
        "crash_test": "runner_sigkill_once", "owner_id": user["id"], "approved_at_unix": approved_at,
        "stop_at_unix": approved_at + plan["maximum_seconds"]}
    private_new(args.approval_output, approval)
    print(json.dumps({"approval_created": True, "owner_id": user["id"], "trial_id": plan["trial_id"],
        "immutable_stop_at_unix": approval["stop_at_unix"], "account_record": str(pending),
        "approval_sha256": hashlib.sha256(args.approval_output.read_bytes()).hexdigest(), "worker_started": False}))


if __name__ == "__main__":
    main()
