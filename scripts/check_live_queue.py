"""Live HTTP queue recovery and authorization controls, without hosted inference.

Requires the existing server credential, NC_SAMPLE_VIDEO authorized footage,
worker dependencies, and an otherwise idle queue. Test objects are temporary.
"""

import json
import os
import secrets
import sys
import threading
import time
import uuid
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))


def main():
    from noetharaclipz.backend import Backend
    from noetharaclipz.config import Settings
    from noetharaclipz.runner import Worker

    s = Settings()
    assert not s.free_verified, "Keep hosted inference disabled"
    b = Backend(s)
    uid = None
    pid = None
    r = {
        "checks": {},
        "hosted_generation_requested": False,
        "scope": "Live HTTP queue control tests; not video or AI acceptance",
    }
    start = time.monotonic()

    def rpc(api, name, **params):
        response = api.post(b.base + "/rest/v1/rpc/" + name, json=params)
        response.raise_for_status()
        return response.json() if response.content else None

    try:
        assert not b.rows(
            "processing_jobs", select="id", status="not.in.(completed,failed,cancelled)"
        ), "Unrelated active jobs"
        email = "nc-recovery-" + uuid.uuid4().hex + "@example.com"
        password = secrets.token_urlsafe(32)
        response = b.client.post(
            b.base + "/auth/v1/admin/users",
            json={"email": email, "password": password, "email_confirm": True},
        )
        response.raise_for_status()
        uid = response.json()["id"]
        user = httpx.Client(
            timeout=60,
            headers={"apikey": "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"},
        )
        response = user.post(
            b.base + "/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        user.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        sample = Path(os.environ["NC_SAMPLE_VIDEO"]).resolve(strict=True)
        reservation = rpc(
            user,
            "prepare_upload",
            request_id=str(uuid.uuid4()),
            filename="Queue recovery QA Sintel.mp4",
            mime_type="video/mp4",
            byte_size=sample.stat().st_size,
            instructions="Queue recovery transport QA; no inference authorized",
        )
        pid = reservation["project_id"]
        response = user.post(
            b.base + "/storage/v1/object/source-videos/" + reservation["path"],
            content=sample.read_bytes(),
            headers={"Content-Type": "video/mp4"},
        )
        response.raise_for_status()
        jid = rpc(user, "finalize_upload", pid=pid)
        stop = threading.Event()
        stop.set()
        w = Worker(s, backend=b, stop_event=stop)
        for _ in range(100):
            if w.once():
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Unable to claim QA message")
        job = b.rows("processing_jobs", id="eq." + jid)[0]
        assert job["status"] == "queued" and job["attempts"] == 1 and job["lease_token"]
        old_token = job["lease_token"]
        r["checks"]["shutdown_preserves_live_recoverable_lease"] = True
        assert b.rpc("worker_claim") is None
        r["checks"]["global_concurrency_guard"] = True
        print(
            "Waiting for real 120-second queue visibility and lease expiry", flush=True
        )
        deadline = time.monotonic() + 155
        while time.monotonic() < deadline:
            current = b.rows(
                "processing_jobs",
                select="id",
                status="not.in.(completed,failed,cancelled)",
            )
            assert all(j["id"] == jid for j in current), (
                "Unrelated job arrived; refusing consumption"
            )
            reclaimed = b.rpc("worker_claim")
            if reclaimed:
                break
            time.sleep(2)
        else:
            raise AssertionError("Expired lease was not reclaimed")
        assert (
            reclaimed["id"] == jid
            and reclaimed["attempts"] == 2
            and reclaimed["lease_token"] != old_token
        )
        r["checks"]["expired_job_reclaimed_with_new_token"] = True
        try:
            b.rpc(
                "worker_tick",
                jid=jid,
                token=old_token,
                state="analyzing",
                pct=20,
                detail="QA stale worker",
            )
        except RuntimeError as e:
            assert "lease expired" in str(e)
        else:
            raise AssertionError("Old token accepted")
        r["checks"]["stale_token_rejected"] = True
        b.rpc(
            "worker_tick",
            jid=jid,
            token=reclaimed["lease_token"],
            state="analyzing",
            pct=25,
            detail="QA live cancellation boundary",
        )
        rpc(user, "cancel_job", jid=jid)
        assert not b.rpc(
            "worker_tick",
            jid=jid,
            token=reclaimed["lease_token"],
            state="analyzing",
            pct=26,
            detail="QA cancellation acknowledgement",
        )
        assert b.rows("processing_jobs", id="eq." + jid)[0]["status"] == "cancelled"
        r["checks"]["claimed_job_cancellation_acknowledged"] = True
        assert rpc(user, "retry_job", jid=jid) == jid
        retried = b.rpc("worker_claim")
        assert retried["id"] == jid and retried["attempts"] == 3
        b.rpc(
            "worker_tick",
            jid=jid,
            token=retried["lease_token"],
            state="failed",
            pct=0,
            detail="Independent QA complete",
            error_message="QA cleanup; no inference requested",
        )
        try:
            b.rpc(
                "worker_tick",
                jid=jid,
                token=retried["lease_token"],
                state="analyzing",
                pct=30,
                detail="QA finished-job guard",
            )
        except RuntimeError as e:
            assert "already finished" in str(e)
        else:
            raise AssertionError("Finished job resurrected")
        r["checks"]["retry_and_finished_job_guard"] = True
        r["status"] = "passed"
    finally:
        try:
            if uid and pid:
                for bucket in (
                    "source-videos",
                    "thumbnails",
                    "processing-artifacts",
                    "rendered-clips",
                ):
                    b.remove_prefix(bucket, uid + "/" + pid + "/")
                response = b.client.delete(
                    b.base + "/rest/v1/projects", params={"id": "eq." + pid}
                )
                response.raise_for_status()
            if uid:
                response = b.client.delete(b.base + "/auth/v1/admin/users/" + uid)
                response.raise_for_status()
            r["cleanup"] = "all test objects/projects/accounts removed"
        except Exception as e:
            r["cleanup"] = "FAILED: " + type(e).__name__
        r.setdefault("status", "failed")
        r["elapsed_seconds"] = round(time.monotonic() - start, 2)
        (ROOT / "test-results/live-queue-recovery.json").write_text(
            json.dumps(r, indent=2) + "\n"
        )
        print(json.dumps(r, indent=2), flush=True)


if __name__ == "__main__":
    main()
