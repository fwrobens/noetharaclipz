"""Standby by default. Guarded normal-worker subprocess with restart supervision."""

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import UUID
from .healthcheck import healthy

log = logging.getLogger(__name__)


def gate(env):
    if (
        env.get("NC_AI_PROVIDER") != "local"
        or env.get("GEMINI_FREE_TIER_VERIFIED", "false").lower() != "false"
    ):
        raise ValueError(
            "Deployment requires explicit local provider and disabled Gemini"
        )
    mode = env.get("NC_DEPLOY_MODE", "standby")
    owner = env.get("NC_WORKER_OWNER_ID", "")
    if mode == "standby":
        return mode
    if mode == "qa" and owner:
        UUID(owner)
        return mode
    if mode == "global" and not owner and env.get("NC_GLOBAL_QUEUE_APPROVED") == "true":
        return mode
    raise ValueError(
        "Use standby, an explicit QA UUID, or separately approved global mode"
    )


def write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.chmod(0o600)
    temporary.replace(path)


def cleanup_temp(directory, now=None):
    """Dedicated worker volume only; never inspect another service's /tmp."""
    now = time.time() if now is None else now
    for path in directory.glob("noetharaclipz-*"):
        if (
            path.is_dir()
            and not path.is_symlink()
            and now - path.stat().st_mtime > 86400
        ):
            shutil.rmtree(path)


def main():
    logging.basicConfig(level=logging.INFO)
    mode = gate(os.environ)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    path = Path(os.environ.get("NC_HEALTH_FILE", "/run/worker/health.json"))
    if mode == "standby":
        log.info("Standby: no credentials loaded and no queue access")
        while not stop.is_set():
            write_state(path, {"mode": mode, "ai_ready": False, "at": time.time()})
            stop.wait(15)
        return 0
    # File secret only; never put the key in Docker build args/Compose environment.
    key = Path(os.environ["NC_SUPABASE_KEY_FILE"]).read_text().strip()
    from noetharaclipz.config import server_key_headers

    server_key_headers(key)
    env = dict(os.environ, SUPABASE_SECRET_KEY=key)
    # Do not forward irrelevant provider keys into the worker process.
    for name in (
        "GEMINI_API_KEY",
        "ANYMODEL_API_KEY",
        "NVIDIA_API_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        env.pop(name, None)
    path.unlink(missing_ok=True)
    cleanup_temp(Path(os.environ["TMPDIR"]))
    code = "import logging; logging.getLogger('httpx').setLevel(logging.WARNING); from noetharaclipz.runner import main; main()"
    child = subprocess.Popen([sys.executable, "-c", code], env=env)
    began = time.monotonic()
    last_cleanup = began
    failed = False
    try:
        while child.poll() is None and not stop.wait(10):
            try:
                state = json.loads(path.read_text())
                valid = state.get("pid") == child.pid and healthy(state)
            except (OSError, ValueError):
                valid = False
            if time.monotonic() - began > 240 and not valid:
                log.error("Local worker readiness/heartbeat/main-loop watchdog failed")
                failed = True
                break
            if time.monotonic() - last_cleanup > 3600:
                cleanup_temp(Path(os.environ["TMPDIR"]))
                last_cleanup = time.monotonic()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=90)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        write_state(path, {"mode": mode, "ai_ready": False, "at": time.time()})
    return 1 if failed or not stop.is_set() else 0


if __name__ == "__main__":
    raise SystemExit(main())
