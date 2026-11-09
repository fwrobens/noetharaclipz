"""Live auth/storage/duplicate checks using the ONE existing EC2 QA owner.

No accounts, workers, schema changes, global claims or highlight fixtures.
Only the QA export's idempotent normal export RPC is allowed to enqueue work.
The protected original job is read-only and its complete digest must not change.
"""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx

BASE = "https://zxdnjnsghdnviflahvry.supabase.co"
PUBLIC = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"
PROTECTED_JOB = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"
PROTECTED_PROJECT = "e1cf543e-f206-4d6f-a2ef-e6c06de22abf"
PROTECTED_HASH = "deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    account = json.loads(args.account.read_text())
    accepted = json.loads(args.acceptance.read_text())
    assert accepted["passed"] and accepted["provider"] == "local-smolvlm2"
    report = {"passed": False, "checked_unix": int(time.time()), "checks": {},
              "one_existing_qa_owner": True, "new_accounts_or_workers": False}
    checks = report["checks"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    with httpx.Client(timeout=30, headers={"apikey": PUBLIC}) as anon, \
            httpx.Client(timeout=30, headers={"apikey": PUBLIC}) as user, \
            httpx.Client(timeout=30, headers={"apikey": key, "Authorization": "Bearer " + key}) as admin:
        def rows(client, table, **params):
            r = client.get(BASE + "/rest/v1/" + table, params=params)
            r.raise_for_status()
            return r.json()

        def invariant():
            row = rows(admin, "processing_jobs", id="eq." + PROTECTED_JOB)[0]
            hashes = [hashlib.sha256(json.dumps(row, sort_keys=True, **kw).encode()).hexdigest()
                      for kw in ({}, {"separators": (",", ":")})]
            assert PROTECTED_HASH in hashes and row["status"] == "queued" and row["attempts"] == 0

        invariant()
        r = user.post(BASE + "/auth/v1/token?grant_type=password",
                      json={"email": account["email"], "password": account["password"]})
        r.raise_for_status()
        user.headers["Authorization"] = "Bearer " + r.json()["access_token"]
        for client, label in ((anon, "anonymous"), (user, "authenticated_qa")):
            statuses = {}
            for operation, body in (("worker_protocol", {}), ("worker_claim_scoped", {"owner": account["id"]})):
                denied = client.post(BASE + "/rest/v1/rpc/" + operation, json=body)
                assert denied.status_code in (401, 403), (label, operation, denied.status_code)
                statuses[operation] = denied.status_code
            checks[label + "_privileged_operations_denied"] = statuses
        for table, params in (("projects", {"id": "eq." + PROTECTED_PROJECT}),
                              ("processing_jobs", {"id": "eq." + PROTECTED_JOB}),
                              ("videos", {"project_id": "eq." + PROTECTED_PROJECT}),
                              ("highlights", {"project_id": "eq." + PROTECTED_PROJECT})):
            assert rows(user, table, **params) == [], table
        checks["cross_owner_rows_hidden"] = True
        source = rows(admin, "videos", project_id="eq." + PROTECTED_PROJECT, select="source_path")[0]["source_path"]
        for endpoint, method in (("authenticated", "GET"), ("sign", "POST")):
            url = BASE + "/storage/v1/object/" + endpoint + "/source-videos/" + source
            denied = user.get(url, headers={"Range": "bytes=0-0"}) if method == "GET" else user.post(url, json={"expiresIn": 60})
            assert not denied.is_success, "Cross-owner source access unexpectedly succeeded"
        checks["cross_owner_private_source_download_and_signing_denied"] = True
        path = accepted["output_path"]
        assert path.startswith(account["id"] + "/" + accepted["project_id"] + "/")
        for endpoint in ("public", "authenticated"):
            denied = anon.get(BASE + "/storage/v1/object/" + endpoint + "/rendered-clips/" + path,
                              headers={"Range": "bytes=0-0"})
            assert not denied.is_success
        checks["anonymous_and_public_rendered_file_access_denied"] = True
        owned = user.get(BASE + "/storage/v1/object/authenticated/rendered-clips/" + path,
                         headers={"Range": "bytes=0-0"})
        assert owned.is_success and len(owned.content) > 0
        checks["authenticated_owner_private_download_permitted"] = True
        jobs_before = rows(user, "processing_jobs", project_id="eq." + accepted["project_id"], kind="eq.render")
        clip = rows(user, "clips", id="eq." + accepted["clip_id"])[0]
        duplicate = user.post(BASE + "/rest/v1/rpc/export_clip",
                              json={"cid": clip["id"], "expected_revision": clip["revision"]})
        duplicate.raise_for_status()
        assert duplicate.json() == accepted["render_job_id"]
        assert rows(user, "processing_jobs", project_id="eq." + accepted["project_id"], kind="eq.render") == jobs_before
        checks["duplicate_export_returns_existing_completed_job"] = True
        denied = user.patch(BASE + "/rest/v1/processing_jobs", params={"id": "eq." + accepted["render_job_id"]},
                            json={"status": "completed", "payload": {"output_path": "forged"}},
                            headers={"Prefer": "return=representation"})
        assert not denied.is_success or denied.json() == []
        assert rows(user, "processing_jobs", project_id="eq." + accepted["project_id"], kind="eq.render") == jobs_before
        checks["browser_cannot_forge_worker_completion"] = True
        count_before = len(rows(user, "projects", select="id"))
        for change in ({"byte_size": 0}, {"byte_size": 45000001}, {"mime_type": "text/plain"}, {"instructions": "x" * 4001}):
            body = {"request_id": str(uuid4()), "filename": "invalid-qa.mp4", "mime_type": "video/mp4",
                    "byte_size": 1, "instructions": "QA invalid input guard", **change}
            denied = user.post(BASE + "/rest/v1/rpc/prepare_upload", json=body)
            assert not denied.is_success
        assert len(rows(user, "projects", select="id")) == count_before
        checks["invalid_upload_size_mime_and_prompt_rejected_without_creating_projects"] = True
        usage = rows(user, "provider_usage", project_id="eq." + accepted["project_id"])
        assert usage and all(row["provider"] == "local-smolvlm2" and row["estimated_cost"] == 0 for row in usage)
        checks["actual_local_provenance_and_zero_recorded_provider_cost"] = True
        invariant()
        checks["protected_original_row_identical_queued_zero_attempts"] = True
        report["passed"] = True
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
