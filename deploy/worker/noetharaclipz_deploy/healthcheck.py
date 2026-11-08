"""Local probe only: never loads models, sends heartbeats or claims queue work."""

import json
import os
import time
from pathlib import Path


def healthy(state, now=None):
    now = time.time() if now is None else now
    if not 0 <= now - state.get("at", 0) < 90:
        return False
    if state.get("mode") == "standby":
        return state.get("ai_ready") is False
    return state.get("ai_ready") is True and state.get("main_age_seconds", 9999) < 1300


def main():
    try:
        state = json.loads(
            Path(
                os.environ.get("NC_HEALTH_FILE", "/run/worker/health.json")
            ).read_text()
        )
        return 0 if healthy(state) else 1
    except (OSError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
