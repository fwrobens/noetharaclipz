"""The status observer cannot run container/service/network mutations."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "status24h", ROOT / "scripts/inspect_continuous_24h_status.py"
)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


@pytest.mark.parametrize(
    "command",
    [
        collector.DOCKER + ["exec", "pilot", "python"],
        collector.DOCKER + ["start", "pilot"],
        collector.DOCKER + ["stop", "pilot"],
        collector.DOCKER + ["logs", "unrelated"],
        ["systemctl", "restart", "noetharaclipz-continuous.service"],
        ["iptables", "--wait", "5", "-F"],
    ],
)
def test_read_only_status_denies_actions_before_execution(monkeypatch, command):
    monkeypatch.setattr(
        collector.subprocess, "run", lambda *a, **k: pytest.fail("Unsafe command executed")
    )
    with pytest.raises(ValueError, match="prohibits"):
        collector.read_command(command, lambda c: False, "pilot")


def test_state_output_never_includes_healthcheck_raw_output():
    raw = json.dumps(
        {
            "Status": "running",
            "Running": True,
            "Health": {"Status": "healthy", "Log": [{"Output": "private health output"}]},
        }
    )
    out = collector.safe_state(raw + '|0|{"Name":"no","MaximumRetryCount":0}')
    assert out["health"] == "healthy" and out["restart_policy"]["Name"] == "no"
    assert "private health output" not in json.dumps(out)
