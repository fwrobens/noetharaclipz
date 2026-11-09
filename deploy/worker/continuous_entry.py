"""No model or secret import until a fresh per-generation host grant exists."""

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
from continuous_policy import grant_valid, validate_manifest

ROOT = Path("/run/continuous")
STATE = Path("/run/worker/continuous-state.json")


def read(path):
    try:
        info = path.lstat()
        if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            return {}
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def state(value):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(value))
    temp.chmod(0o600)
    temp.replace(STATE)


def signal_group(child, sig):
    try:
        os.killpg(child.pid, sig)
    except ProcessLookupError:
        pass


def main():
    m = read(ROOT / "public/manifest.json")
    validate_manifest(m, time.time())
    if (
        os.environ.get("NC_QUEUE_MODE") != "consented"
        or os.environ.get("NC_AI_PROVIDER") != "local"
        or os.environ.get("NC_DEPLOY_MODE") != "continuous"
        or os.environ.get("GEMINI_FREE_TIER_VERIFIED") != "false"
        or os.environ.get("NC_GLOBAL_QUEUE_APPROVED") != "false"
        or os.environ.get("NC_WORKER_OWNER_ID") != m["owner_id"]
        or os.environ.get("NC_OWNER_CONSENT_ID") != m["consent_id"]
    ):
        raise ValueError("Unsafe continuous environment")
    if not evaluate(read_limits())["passed"]:
        raise ValueError("Actual kernel limits failed")
    nonce = str(uuid4())
    current = {
        "nonce": nonce,
        "deployment_id": m["deployment_id"],
        "phase": "awaiting_grant",
    }
    state(current)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    until = time.monotonic() + 60
    while not grant_valid(read(ROOT / "gates/grant.json"), m, nonce, time.time()):
        if (
            stopping.wait(0.2)
            or time.monotonic() >= until
            or time.time() >= m["valid_until"]
        ):
            return 0
    # This is the first credential access. No irrelevant provider key is passed.
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(
            x in k
            for x in (
                "GEMINI_API_KEY",
                "NVIDIA_API_KEY",
                "ANYMODEL_API_KEY",
                "SUPABASE_SERVICE_ROLE_KEY",
            )
        )
    }
    env["SUPABASE_SECRET_KEY"] = Path("/run/secrets/supabase_key").read_text().strip()
    code = "import logging; logging.getLogger('httpx').setLevel(logging.WARNING); from noetharaclipz.runner import main; main()"
    child = subprocess.Popen(
        [sys.executable, "-c", code], env=env, start_new_session=True
    )
    current.update(phase="running")
    state(current)
    began = time.monotonic()
    reason = "child_exit"
    try:
        while child.poll() is None:
            if stopping.wait(0.2):
                reason = "operator_stop"
                break
            if time.time() >= m["valid_until"] - 15:
                reason = "approval_expired"
                break
            if not grant_valid(read(ROOT / "gates/grant.json"), m, nonce, time.time()):
                reason = "grant_revoked_or_stale"
                break
            if time.monotonic() - began > 240:
                try:
                    health = json.loads(Path("/run/worker/health.json").read_text())
                except (OSError, ValueError):
                    health = {}
                if (
                    health.get("pid") != child.pid
                    or not health.get("ai_ready")
                    or not 0 <= time.time() - health.get("at", 0) < 90
                    or health.get("main_age_seconds", 9999) >= 1300
                ):
                    reason = "health_timeout"
                    break
    finally:
        signal_group(child, signal.SIGTERM)
        try:
            fast = read(ROOT / "gates/stop.json").get("fast") is True
            child.wait(timeout=90 if reason == "operator_stop" and not fast else 10)
        except subprocess.TimeoutExpired:
            signal_group(child, signal.SIGKILL)
            child.wait(timeout=2)
        signal_group(child, signal.SIGKILL)
    current.update(phase="finalizing", reason=reason)
    state(current)
    until = time.monotonic() + 4
    while time.monotonic() < until:
        if read(ROOT / "gates/finalized.json").get("nonce") == nonce:
            break
        time.sleep(0.1)
    print(
        json.dumps({"continuous_generation_stopped": True, "reason": reason}),
        flush=True,
    )
    return 1 if reason in ("child_exit", "health_timeout") else 0


if __name__ == "__main__":
    raise SystemExit(main())
