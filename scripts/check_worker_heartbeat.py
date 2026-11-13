"""Live heartbeat and privileged-RPC access checks for NoetharaClipZ only.

Uses the existing bound server credential. Creates one temporary confirmed QA
account for browser-role denial checks and deletes it afterwards. Never invokes
AI, changes schema, or prints credentials. Run after applying the SQL repair.
"""

import json
import os
import secrets
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
PUBLIC_KEY = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"


def main():
    from noetharaclipz.backend import Backend
    from noetharaclipz.config import Settings

    settings = Settings()
    backend = Backend(settings)
    report = {"project": "zxdnjnsghdnviflahvry", "hosted_inference_requested": False}
    report_path = Path(
        os.getenv(
            "NC_HEARTBEAT_REPORT",
            str(ROOT / "test-results/heartbeat-verification.json"),
        )
    )
    uid = None
    try:
        response = backend.client.post(
            backend.base + "/rest/v1/rpc/worker_heartbeat",
            json={
                "ai_ready": False,
                "detail": "Authorized heartbeat repair verification " * 12,
            },
        )
        report["authorized_worker"] = {"http_status": response.status_code}
        if response.is_error:
            error = response.json()
            report["authorized_worker"].update(
                code=error.get("code"), message=error.get("message")
            )

        email = "nc-heartbeat-" + uuid.uuid4().hex + "@example.com"
        password = secrets.token_urlsafe(32)
        created = backend.client.post(
            backend.base + "/auth/v1/admin/users",
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
            },
        )
        created.raise_for_status()
        uid = created.json()["id"]
        with (
            httpx.Client(timeout=45, headers={"apikey": PUBLIC_KEY}) as anonymous,
            httpx.Client(timeout=45, headers={"apikey": PUBLIC_KEY}) as user,
        ):
            login = user.post(
                backend.base + "/auth/v1/token?grant_type=password",
                json={"email": email, "password": password},
            )
            login.raise_for_status()
            user.headers["Authorization"] = "Bearer " + login.json()["access_token"]
            # Only fabricated, nonexistent IDs are used for the negative tick
            # request; no other project/job is selected or modified.
            requests = {
                "worker_heartbeat": {
                    "ai_ready": False,
                    "detail": "Unauthorized call must be denied",
                },
                "worker_claim": {},
                "worker_tick": {
                    "jid": str(uuid.uuid4()),
                    "token": str(uuid.uuid4()),
                    "state": "preparing",
                    "pct": 1,
                    "detail": "Unauthorized call must be denied",
                },
            }
            denied = {}
            for name, client in (("anonymous", anonymous), ("authenticated", user)):
                denied[name] = {}
                for operation, body in requests.items():
                    result = client.post(
                        backend.base + "/rest/v1/rpc/" + operation, json=body
                    )
                    denied[name][operation] = result.status_code
                    assert result.status_code in (401, 403), (
                        f"{name} {operation} did not fail at the authorization boundary"
                    )
            report["unauthorized_rpc_statuses"] = denied
            health = user.post(backend.base + "/rest/v1/rpc/pipeline_health", json={})
            health.raise_for_status()
            report["pipeline_health"] = health.json()
        report["passed"] = (
            response.is_success
            and report["pipeline_health"].get("online") is True
            and report["pipeline_health"].get("ai_ready") is False
            and len(report["pipeline_health"].get("detail") or "") == 300
        )
    finally:
        if uid:
            removed = backend.client.delete(
                backend.base + "/auth/v1/admin/users/" + uid
            )
            removed.raise_for_status()
            report["temporary_account_removed"] = True
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
