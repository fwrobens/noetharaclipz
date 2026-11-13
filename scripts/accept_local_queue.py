"""Run the normal browser flow with a real local worker scoped to a new QA owner.

Requires the reviewed SQL proposal to be deployed first. Refuses to start any
worker or create accounts when the protocol is absent. Never starts a global
consumer, inserts highlights, or substitutes isolated rendering for Export.
"""

import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
PROTECTED_JOB = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"
PUBLIC_KEY = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"


def main():
    from noetharaclipz.backend import Backend
    from noetharaclipz.config import Settings
    from noetharaclipz.runner import Worker

    settings = replace(Settings(), provider="local")
    assert not settings.free_verified, "Gemini must stay disabled"
    Path(os.environ["NC_SAMPLE_VIDEO"]).resolve(strict=True)
    backend = Backend(settings)
    report = {
        "passed": False,
        "hosted_generation": False,
        "global_worker_started": False,
        "checks": {},
    }
    report_path = ROOT / "test-results/local-queue-browser.json"
    users, apis = [], []
    process = None
    before = backend.rows("processing_jobs", id="eq." + PROTECTED_JOB)
    try:
        # This is read-only; never downgrade to the global claim RPC.
        Worker(settings, backend=backend, provider=object()).check_protocol()
        report["checks"]["compatible_scoped_queue_protocol"] = True
        for _ in range(2):
            user = {
                "email": "nc-local-queue-" + uuid.uuid4().hex + "@example.com",
                "password": secrets.token_urlsafe(32),
            }
            response = backend.client.post(
                backend.base + "/auth/v1/admin/users",
                json={**user, "email_confirm": True},
            )
            response.raise_for_status()
            user["id"] = response.json()["id"]
            users.append(user)
            api = httpx.Client(timeout=60, headers={"apikey": PUBLIC_KEY})
            response = api.post(
                backend.base + "/auth/v1/token?grant_type=password",
                json={"email": user["email"], "password": user["password"]},
            )
            response.raise_for_status()
            api.headers["Authorization"] = "Bearer " + response.json()["access_token"]
            apis.append(api)
        env = dict(
            os.environ,
            NC_AI_PROVIDER="local",
            GEMINI_FREE_TIER_VERIFIED="false",
            NC_WORKER_OWNER_ID=users[0]["id"],
            PYTHONPATH=str(ROOT / "worker"),
        )
        python = os.environ["NC_LOCAL_PYTHON"]
        with (ROOT / "test-results/local-queue-worker.log").open("w") as log:
            process = subprocess.Popen(
                [python, "-m", "noetharaclipz.runner"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
        deadline = time.monotonic() + 180
        while True:
            health = apis[0].post(
                backend.base + "/rest/v1/rpc/pipeline_health", json={}
            )
            health.raise_for_status()
            if health.json().get("online") and health.json().get("ai_ready"):
                break
            assert process.poll() is None and time.monotonic() < deadline, (
                "Scoped local worker did not become ready"
            )
            time.sleep(1)
        # Browser credentials are process environment only, never logs or repo files.
        env.update(
            NC_TEST_EMAIL=users[0]["email"], NC_TEST_PASSWORD=users[0]["password"]
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/acceptance.py")],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=1800,
        )
        proof = json.loads((ROOT / "test-results/acceptance.json").read_text())
        assert proof["passed"] and proof["provider"] == "local-smolvlm2"
        pid = proof["project_id"]
        for table in (
            "projects",
            "videos",
            "highlights",
            "clips",
            "processing_jobs",
            "analysis_artifacts",
            "provider_usage",
        ):
            response = apis[1].get(
                backend.base + "/rest/v1/" + table,
                params={"id" if table == "projects" else "project_id": "eq." + pid},
            )
            response.raise_for_status()
            assert response.json() == [], "Cross-user row access: " + table
        denied = apis[1].get(
            backend.base
            + "/storage/v1/object/authenticated/rendered-clips/"
            + proof["output_path"]
        )
        assert denied.status_code in (400, 401, 403, 404), (
            "Cross-user private output access"
        )
        video = backend.rows("videos", project_id="eq." + pid)[0]
        source_path = video["source_path"]
        denied = apis[1].post(
            backend.base + "/storage/v1/object/sign/source-videos/" + source_path,
            json={"expiresIn": 60},
        )
        assert denied.status_code in (400, 401, 403, 404), (
            "Cross-user source signing allowed"
        )
        for bucket, path in (
            ("source-videos", source_path),
            ("rendered-clips", proof["output_path"]),
        ):
            with httpx.Client(timeout=60, headers={"apikey": PUBLIC_KEY}) as anonymous:
                denied = anonymous.get(
                    backend.base
                    + "/storage/v1/object/authenticated/"
                    + bucket
                    + "/"
                    + path
                )
                assert denied.status_code in (400, 401, 403, 404), (
                    "Anonymous private media allowed"
                )
        # Owner browsers cannot overwrite a reserved source or forge rendered output.
        for bucket, path in (
            ("source-videos", source_path),
            ("rendered-clips", proof["output_path"]),
        ):
            denied = apis[0].post(
                backend.base + "/storage/v1/object/" + bucket + "/" + path,
                content=b"DENIED QA overwrite probe",
                headers={"Content-Type": "video/mp4", "x-upsert": "true"},
            )
            assert denied.status_code in (400, 401, 403), (
                "Owner browser media overwrite allowed"
            )
        forged = apis[0].patch(
            backend.base + "/rest/v1/processing_jobs",
            params={"id": "eq." + proof["analysis_job_id"]},
            json={"status": "completed", "attempts": 99},
        )
        assert forged.status_code in (401, 403), "Browser job-state write allowed"
        with httpx.Client(timeout=60, headers={"apikey": PUBLIC_KEY}) as anonymous:
            for operation, params in (
                ("worker_protocol", {}),
                ("worker_claim_scoped", {"owner": users[0]["id"]}),
                (
                    "worker_heartbeat_scoped",
                    {"owner": users[0]["id"], "ai_ready": True, "detail": "forged"},
                ),
            ):
                denied = anonymous.post(
                    backend.base + "/rest/v1/rpc/" + operation, json=params
                )
                assert denied.status_code in (401, 403), (
                    "Anonymous worker operation allowed"
                )
        for api in apis:
            for operation in (
                "worker_claim",
                "worker_claim_scoped",
                "worker_heartbeat_scoped",
                "worker_protocol",
            ):
                params = (
                    {"owner": users[0]["id"]}
                    if operation == "worker_claim_scoped"
                    else {}
                )
                if operation == "worker_heartbeat_scoped":
                    params = {
                        "owner": users[0]["id"],
                        "ai_ready": True,
                        "detail": "forged",
                    }
                denied = api.post(
                    backend.base + "/rest/v1/rpc/" + operation, json=params
                )
                assert denied.status_code in (401, 403), (
                    "Browser privileged operation allowed"
                )
        bad = apis[0].post(
            backend.base + "/rest/v1/rpc/prepare_upload",
            json={
                "request_id": str(uuid.uuid4()),
                "filename": "invalid.mp4",
                "mime_type": "video/mp4",
                "byte_size": 0,
                "instructions": "Reject invalid input",
            },
        )
        assert bad.status_code >= 400
        report["checks"].update(
            normal_ui_acceptance=True,
            cross_user_rows_denied=True,
            cross_user_private_download_denied=True,
            browser_privileged_operations_denied=True,
            invalid_upload_denied=True,
            cross_user_source_signing_denied=True,
            anonymous_private_media_denied=True,
            owner_browser_media_overwrite_denied=True,
            browser_job_state_forgery_denied=True,
            anonymous_worker_operations_denied=True,
        )
        report["acceptance"] = proof
        report["passed"] = True
    except Exception as exc:
        # Never serialize HTTP headers or account passwords.
        report["error_type"] = type(exc).__name__
        report["blocked_before_accounts_or_worker"] = not users and process is None
        raise
    finally:
        if process:
            process.terminate()
            process.wait(timeout=90)
            if report["passed"]:
                health = apis[0].post(
                    backend.base + "/rest/v1/rpc/pipeline_health", json={}
                )
                health.raise_for_status()
                report["checks"]["shutdown_clears_provider_readiness"] = (
                    health.json().get("ai_ready") is False
                )
        for api in apis:
            api.close()
        cleanup = []
        for user in users:
            try:
                projects = backend.rows("projects", owner_id="eq." + user["id"])
                for project in projects:
                    active = backend.rows(
                        "processing_jobs",
                        project_id="eq." + project["id"],
                        status="not.in.(completed,failed,cancelled)",
                    )
                    if active:
                        raise RuntimeError(
                            "Own QA work still active; retain for scoped cancellation/recovery"
                        )
                    for bucket in (
                        "source-videos",
                        "thumbnails",
                        "processing-artifacts",
                        "rendered-clips",
                    ):
                        backend.remove_prefix(
                            bucket, user["id"] + "/" + project["id"] + "/"
                        )
                    response = backend.client.delete(
                        backend.base + "/rest/v1/projects",
                        params={"id": "eq." + project["id"]},
                    )
                    response.raise_for_status()
                response = backend.client.delete(
                    backend.base + "/auth/v1/admin/users/" + user["id"]
                )
                response.raise_for_status()
                cleanup.append({"user_id": user["id"], "removed": True})
            except Exception as exc:
                cleanup.append(
                    {
                        "user_id": user["id"],
                        "removed": False,
                        "error_type": type(exc).__name__,
                    }
                )
        report["cleanup"] = cleanup
        report["checks"]["protected_job_unchanged"] = before == backend.rows(
            "processing_jobs", id="eq." + PROTECTED_JOB
        )
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        assert report["checks"]["protected_job_unchanged"], "Protected job changed"
        assert all(item["removed"] for item in cleanup), (
            "Scoped QA cleanup incomplete; see report"
        )
        if report["passed"]:
            assert report["checks"].get("shutdown_clears_provider_readiness"), (
                "Stopped worker still AI ready"
            )


if __name__ == "__main__":
    main()
