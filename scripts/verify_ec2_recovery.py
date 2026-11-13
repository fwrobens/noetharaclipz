"""Abandon one scoped QA lease, then let the real EC2 worker recover it.

The one authenticated QA owner uploads deliberately invalid test media through
the normal upload API. The test claims ONLY that owner's new job once, performs
no processing/heartbeat, and never renews or edits the lease. The real deployed
worker must reclaim it after 120 seconds and reject the malformed input. This
tests lease recovery, not a simulated Docker/host crash or AI highlight quality.
"""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx

from verify_ec2_security import BASE, PUBLIC, PROTECTED_JOB, PROTECTED_HASH


def check_attempt_limit(user, jid):
    """Retry the same malformed QA job once; the actual worker must exhaust it."""
    def current():
        r = user.get(BASE + "/rest/v1/processing_jobs", params={"id": "eq." + jid})
        r.raise_for_status()
        return r.json()[0]
    before = current()
    assert before["status"] == "failed" and before["attempts"] == 2
    r = user.post(BASE + "/rest/v1/rpc/retry_job", json={"jid": jid})
    r.raise_for_status()
    assert r.json() == jid
    until = time.monotonic() + 30
    while time.monotonic() < until:
        after = current()
        if after["status"] == "failed" and after["attempts"] == 3:
            break
        time.sleep(1)
    else:
        raise AssertionError("Real worker did not finish the permitted third attempt")
    denied = user.post(BASE + "/rest/v1/rpc/retry_job", json={"jid": jid})
    assert not denied.is_success
    assert current() == after
    return {"third_attempt_processed_by_ec2": True, "fourth_attempt_retry_denied": True,
            "final_status": after["status"], "final_attempts": after["attempts"]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account", type=Path, required=True)
    p.add_argument("--trial", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    account = json.loads(args.account.read_text())
    trial = json.loads(args.trial.read_text())
    assert account["id"] == trial["owner_id"] and trial["started"] and trial["ready"]
    assert time.time() + 240 < trial["stop_at"], "Insufficient approved trial time; do not extend it"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    report = {"passed": False, "checks": {}, "global_claim_used": False, "docker_or_host_crash_tested": False,
              "scenario": "one abandoned QA lease; real EC2 reclaim; malformed test media rejected"}
    args.report.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.report.write_text(json.dumps(report, indent=2) + "\n")

    save()
    with httpx.Client(timeout=30, headers={"apikey": PUBLIC}) as user, \
            httpx.Client(timeout=30, headers={"apikey": key, "Authorization": "Bearer " + key}) as admin:
        def rpc(client, name, **body):
            r = client.post(BASE + "/rest/v1/rpc/" + name, json=body)
            r.raise_for_status()
            return r.json() if r.content else None

        def rows(client, table, **params):
            r = client.get(BASE + "/rest/v1/" + table, params=params)
            r.raise_for_status()
            return r.json()

        def protected():
            row = rows(admin, "processing_jobs", id="eq." + PROTECTED_JOB)[0]
            hashes = [hashlib.sha256(json.dumps(row, sort_keys=True, **kw).encode()).hexdigest()
                      for kw in ({}, {"separators": (",", ":")})]
            assert PROTECTED_HASH in hashes and row["attempts"] == 0 and row["status"] == "queued"

        protected()
        r = user.post(BASE + "/auth/v1/token?grant_type=password",
                      json={"email": account["email"], "password": account["password"]})
        r.raise_for_status()
        user.headers["Authorization"] = "Bearer " + r.json()["access_token"]
        active = rows(user, "processing_jobs", status="not.in.(completed,failed,cancelled)")
        assert not active, "Other QA work is active; do not interfere"
        assert rpc(user, "pipeline_health")["ai_ready"]
        assert rpc(admin, "worker_protocol")["scoped_claim"]
        invalid = b"NoetharaClipz isolated authorized QA: this is deliberately not a valid MP4."
        reservation = rpc(user, "prepare_upload", request_id=str(uuid4()), filename="EC2 lease recovery invalid-media QA.mp4",
                          mime_type="video/mp4", byte_size=len(invalid), instructions="QA malformed media must fail validation; no inference requested")
        pid = reservation["project_id"]
        assert reservation["path"].startswith(account["id"] + "/" + pid + "/")
        upload = user.post(BASE + "/storage/v1/object/source-videos/" + reservation["path"],
                           content=invalid, headers={"Content-Type": "video/mp4"})
        upload.raise_for_status()
        jid = rpc(user, "finalize_upload", pid=pid)
        report.update(project_id=pid, job_id=jid)
        # Explicit owner is mandatory. Never call the global worker_claim RPC.
        claimed = rpc(admin, "worker_claim_scoped", owner=account["id"])
        if claimed is None:
            report["result"] = "EC2 won the claim race; no abandoned lease injected; recovery not verified"
            save()
            raise AssertionError(report["result"])
        assert claimed["id"] == jid and claimed["project_id"] == pid and claimed["attempts"] == 1
        old_token = claimed["lease_token"]
        report.update(initial_attempts=1, initial_lease_until=claimed["lease_until"])
        report["checks"]["only_new_qa_job_claimed_once_then_abandoned"] = True
        save()
        began = time.monotonic()
        print("QA lease abandoned; waiting for actual 120-second expiry and EC2 recovery", flush=True)
        while time.monotonic() - began < 165:
            job = rows(user, "processing_jobs", id="eq." + jid)[0]
            if job["attempts"] >= 2:
                break
            time.sleep(1)
        else:
            raise AssertionError("Real EC2 worker did not reclaim the expired QA lease")
        assert job["attempts"] == 2 and job["lease_token"] != old_token
        report["checks"]["ec2_reclaimed_with_new_token_and_second_attempt"] = True
        report["reclaim_wait_seconds"] = round(time.monotonic() - began, 3)
        # Even if invalid media has already failed, the old token must never
        # revive or update it. The function rejects stale/finished work first.
        denied = admin.post(BASE + "/rest/v1/rpc/worker_tick", json={"jid": jid, "token": old_token,
            "state": "analyzing", "pct": 1, "detail": "QA stale lease must be rejected"})
        assert not denied.is_success
        report["checks"]["stale_lease_cannot_update_or_revive_job"] = True
        until = time.monotonic() + 60
        while time.monotonic() < until:
            job = rows(user, "processing_jobs", id="eq." + jid)[0]
            if job["status"] == "failed":
                break
            time.sleep(1)
        else:
            raise AssertionError("Malformed QA media was not rejected by the deployed worker")
        assert job["attempts"] == 2 and job.get("error")
        assert rows(user, "highlights", project_id="eq." + pid) == []
        assert rows(user, "provider_usage", project_id="eq." + pid) == []
        report["checks"].update(invalid_media_rejected_without_highlights_or_inference_usage=True,
                                 protected_original_unchanged=True)
        report.update(final_status=job["status"], final_attempts=job["attempts"], worker_error=job["error"])
        report["attempt_limit"] = check_attempt_limit(user, jid)
        report["recovered_failure_attempts"] = job["attempts"]
        report["final_attempts"] = report["attempt_limit"]["final_attempts"]
        protected()
        report["passed"] = True
        save()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
