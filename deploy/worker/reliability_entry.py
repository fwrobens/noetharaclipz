"""In-container restart gate. No credential/model import before fresh host grant.

Every container generation gets a new nonce. A read-only root-owned grant must
match it and remain fresh. Host monitoring samples final counters before this
entrypoint exits, including before abnormal exits that trigger Docker restart.
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from check_cgroup_limits import evaluate, read_limits

STATE = Path("/run/worker/trial-state.json")
GATE = Path("/run/trial-gate")


def grant_valid(grant, activation, nonce, now):
    return (grant.get("nonce") == nonce and grant.get("trial_id") == activation["trial_id"]
            and grant.get("owner_id") == activation["owner_id"] and grant.get("network_verified") is True
            and now < grant.get("expires_at_unix", 0) <= now + 30
            and grant.get("stop_at_unix") == activation["stop_at_unix"])


def write_state(value):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(value))
    temp.chmod(0o600)
    temp.replace(STATE)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def kill_group(child, signum):
    try:
        os.killpg(child.pid, signum)
    except ProcessLookupError:
        pass


def main():
    activation = json.loads(Path("/run/trial-config/activation.json").read_text())
    stop_at = activation["stop_at_unix"]
    now = time.time()
    if now < activation["approved_at_unix"]:
        raise ValueError("The fixed approval window has not opened")
    if (os.environ.get("NC_AI_PROVIDER") != "local" or os.environ.get("NC_DEPLOY_MODE") != "qa"
            or os.environ.get("GEMINI_FREE_TIER_VERIFIED") != "false"
            or os.environ.get("NC_GLOBAL_QUEUE_APPROVED") != "false"
            or os.environ.get("NC_WORKER_OWNER_ID") != activation["owner_id"]
            or os.environ.get("NC_QA_STOP_AT") != str(stop_at)
            or os.environ.get("NC_QA_TRIAL_ID") != activation["trial_id"]
            or stop_at - activation["approved_at_unix"] > 1800):
        raise ValueError("Unsafe trial environment")
    if now >= stop_at - 95:
        print(json.dumps({"trial_expired": True, "model_or_credential_loaded": False}), flush=True)
        return 0
    proof = evaluate(read_limits())
    if not proof["passed"]:
        raise ValueError("Actual kernel resource controls failed")
    nonce = str(uuid4())
    state = {"trial_id": activation["trial_id"], "nonce": nonce, "phase": "awaiting_network_grant", "kernel": proof}
    write_state(state)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    until = min(time.monotonic() + 60, time.monotonic() + stop_at - time.time() - 95)
    while not grant_valid(read_json(GATE / "grant.json"), activation, nonce, time.time()):
        if stopping.wait(0.2) or time.monotonic() >= until:
            return 0 if stopping.is_set() or time.time() >= stop_at - 95 else 1
    hard_stop = time.monotonic() + stop_at - time.time()
    child = subprocess.Popen([sys.executable, "-m", "noetharaclipz_deploy.supervisor"], start_new_session=True)
    state.update(phase="running", supervisor_pid=child.pid)
    write_state(state)
    reason = "child_failure"
    try:
        while child.poll() is None:
            if stopping.wait(0.2):
                reason = "operator_stop"
                break
            if time.monotonic() >= hard_stop - 95:
                reason = "deadline"
                break
            if not grant_valid(read_json(GATE / "grant.json"), activation, nonce, time.time()):
                reason = "network_grant_revoked_or_stale"
                break
    finally:
        kill_group(child, signal.SIGTERM)
        if child.poll() is None:
            try:
                child.wait(timeout=max(0, min(90, hard_stop - time.monotonic() - 5)))
            except subprocess.TimeoutExpired:
                kill_group(child, signal.SIGKILL)
                child.wait(timeout=2)
        kill_group(child, signal.SIGKILL)
    code = 0 if reason in ("operator_stop", "deadline") else 1
    state.update(phase="finalizing", reason=reason, exit_code=code)
    write_state(state)
    # Preserve the cgroup until the host has sampled its final high-water marks.
    until = min(time.monotonic() + 4, hard_stop - 1)
    while time.monotonic() < until:
        if read_json(GATE / "finalized.json").get("nonce") == nonce:
            break
        time.sleep(0.1)
    print(json.dumps({"trial_generation_stopped": True, "nonce": nonce, "reason": reason, "exit_code": code}), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
