"""Bound the real QA worker to one fixed <=30-minute window, across restarts.

Runs inside the existing image. Probe actual kernel limits before loading any
credential/model. A process-group shutdown starts before the fixed deadline;
the container exits normally at timeout so on-failure cannot extend the trial.
"""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import UUID

MAX_SECONDS = 1800
GRACE_SECONDS = 90


def remaining_window(env, now):
    if (env.get("NC_AI_PROVIDER") != "local" or env.get("NC_DEPLOY_MODE") != "qa"
            or env.get("GEMINI_FREE_TIER_VERIFIED") != "false"
            or env.get("NC_GLOBAL_QUEUE_APPROVED") != "false"):
        raise ValueError("QA requires local mode, disabled Gemini and no global approval")
    UUID(env.get("NC_WORKER_OWNER_ID", ""))
    UUID(env.get("NC_QA_TRIAL_ID", ""))
    remaining = int(env["NC_QA_STOP_AT"]) - now
    if remaining > MAX_SECONDS:
        raise ValueError("QA deadline exceeds the approved 30-minute window")
    return max(0.0, remaining)


def signal_group(child, signum):
    try:
        os.killpg(child.pid, signum)
    except ProcessLookupError:
        pass


def main():
    remaining = remaining_window(os.environ, time.time())
    if remaining <= GRACE_SECONDS + 5:
        print(json.dumps({"qa_window_expired": True, "worker_started": False}), flush=True)
        return 0
    hard_stop = time.monotonic() + remaining
    probe = Path("/run/qa-limits.py")
    spec = importlib.util.spec_from_file_location("actual_limits", probe)
    limits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(limits)
    proof = limits.evaluate(limits.read_limits())
    print(json.dumps({"qa_kernel_preflight": proof}), flush=True)
    if proof.get("passed") is not True:
        raise ValueError("Actual worker cgroup limits failed; no model/credential loaded")
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    child = subprocess.Popen([sys.executable, "-m", "noetharaclipz_deploy.supervisor"], start_new_session=True)
    timed_out = False
    try:
        while child.poll() is None and not stopping.wait(0.25):
            if time.monotonic() >= hard_stop - GRACE_SECONDS - 5:
                timed_out = True
                break
    finally:
        signal_group(child, signal.SIGTERM)
        if child.poll() is None:
            try:
                child.wait(timeout=max(0, min(GRACE_SECONDS, hard_stop - time.monotonic() - 5)))
            except subprocess.TimeoutExpired:
                signal_group(child, signal.SIGKILL)
                child.wait(timeout=2)
        # Also remove any orphaned descendants before PID 1 ends this container.
        signal_group(child, signal.SIGKILL)
    if timed_out or stopping.is_set() or time.monotonic() >= hard_stop - GRACE_SECONDS - 5:
        print(json.dumps({"qa_window_stopped": True, "deadline": int(os.environ["NC_QA_STOP_AT"])}), flush=True)
        return 0
    return child.returncode if child.returncode and child.returncode > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
