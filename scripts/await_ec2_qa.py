"""Wait for the one QA worker, then test the normal website. NEVER start a worker.

Credentials come from a mode-0600 local file and remain in child process memory.
This monitor cannot deploy or consume any queue itself. acceptance.py submits
only ordinary authenticated UI work for the one temporary QA account.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROJECT = "https://zxdnjnsghdnviflahvry.supabase.co"
PUBLIC_KEY = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"
PROTECTED = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account", type=Path, required=True)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--wait-seconds", type=int, default=7200)
    args = p.parse_args()
    info = args.account.stat()
    if args.account.is_symlink() or info.st_mode & 0o077:
        raise ValueError("QA login file must be private")
    account = json.loads(args.account.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / "monitor.json"
    state = {"stage": "waiting_for_ec2_scoped_worker", "passed": False,
             "owner_id": account["id"], "trial_id": account["trial_id"], "worker_spawned_here": False}

    def save():
        state_path.write_text(json.dumps(state, indent=2) + "\n")

    save()
    # READ ONLY original job invariant. No worker/admin job operation is used.
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": "Bearer " + key}
    with httpx.Client(timeout=30) as client:
        def protected():
            r = client.get(PROJECT + "/rest/v1/processing_jobs", headers=headers,
                           params={"id": "eq." + PROTECTED})
            r.raise_for_status()
            row = r.json()[0]
            # Historical evidence stores the protected full-row digest.
            expected_hash = "deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb"
            hashes = [hashlib.sha256(json.dumps(row, sort_keys=True, **kw).encode()).hexdigest()
                      for kw in ({}, {"separators": (",", ":")})]
            if expected_hash not in hashes or row["status"] != "queued" or row["attempts"] != 0:
                raise ValueError("Protected job invariant changed; acceptance stopped")
            return {"queued": True, "attempts": 0, "row_identical": True}

        state["protected_before"] = protected()
        login = client.post(PROJECT + "/auth/v1/token?grant_type=password", headers={"apikey": PUBLIC_KEY},
                            json={"email": account["email"], "password": account["password"]})
        login.raise_for_status()
        auth = {"apikey": PUBLIC_KEY, "Authorization": "Bearer " + login.json()["access_token"]}
        logged_in = time.monotonic()
        until = time.monotonic() + args.wait_seconds
        while time.monotonic() < until:
            if time.monotonic() - logged_in > 1800:
                login = client.post(PROJECT + "/auth/v1/token?grant_type=password", headers={"apikey": PUBLIC_KEY},
                                    json={"email": account["email"], "password": account["password"]})
                login.raise_for_status()
                auth["Authorization"] = "Bearer " + login.json()["access_token"]
                logged_in = time.monotonic()
            r = client.post(PROJECT + "/rest/v1/rpc/pipeline_health", headers=auth, json={})
            r.raise_for_status()
            health = r.json()
            if (health.get("online") and health.get("ai_ready")
                    and "SmolVLM2-500M" in (health.get("detail") or "")):
                break
            time.sleep(5)
        else:
            raise ValueError("No scoped EC2 readiness arrived within the monitor window")
        state.update(stage="normal_browser_acceptance_running", ready_health=health)
        save()
        print("EC2 scoped worker is ready; starting the real browser upload and Export workflow", flush=True)
        env = {k: v for k, v in os.environ.items() if not any(
            marker in k for marker in ("SERVICE_ROLE", "SECRET_KEY", "GEMINI_API_KEY", "NVIDIA_API_KEY", "ANYMODEL_API_KEY"))}
        env.update(NC_AI_PROVIDER="local", NC_TEST_EMAIL=account["email"], NC_TEST_PASSWORD=account["password"],
                   NC_SAMPLE_VIDEO=str(args.sample.resolve()), NC_BASE_URL="http://127.0.0.1:8080",
                   NC_ACCEPTANCE_OUTPUT_DIR=str(args.output.resolve()), CHROMIUM_PATH="/usr/bin/chromium")
        result = subprocess.run([sys.executable, "scripts/acceptance.py"], env=env, timeout=1500)
        state["protected_after"] = protected()
        state.update(stage="completed" if result.returncode == 0 else "browser_acceptance_failed", passed=result.returncode == 0)
        save()
        if result.returncode:
            raise ValueError("EC2 browser acceptance failed; inspect the private QA evidence")
        print("PASS: EC2-backed website MP4 workflow; protected original job unchanged", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"failed": True, "error_type": type(error).__name__, "worker_spawned_here": False}), flush=True)
        raise SystemExit(1) from None
