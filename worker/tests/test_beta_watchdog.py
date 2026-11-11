"""No EC2, Docker, webhook delivery, processing or consent mutations."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("beta_watchdog", ROOT / "deploy/beta/watchdog.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
ID = "11111111-1111-4111-8111-111111111111"
MANIFEST = {
    "deployment_id": ID,
    "operator_approved": True,
    "global_processing": False,
    "gemini_enabled": False,
    "memory_bytes": 8 * 1024**3,
    "cpus": 2,
    "active_jobs": 1,
    "model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
    "not_before": 1000,
    "valid_until": 8200,
}


def config():
    return {
        "schema": 1,
        "deployment_id": ID,
        "operator_approved": True,
        "manifest_sha256": w.sha(w.canonical(MANIFEST)),
        "delivery_enabled": False,
    }


def snapshot(now=2000):
    return {
        "status": {"stage": "monitoring", "at": now, "ai_ready": True},
        "state": {"Running": True},
        "unit": "active",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("operator_approved", False),
        ("global_processing", True),
        ("gemini_enabled", True),
        ("cpus", 4),
        ("memory_bytes", 16 * 1024**3),
        ("active_jobs", 2),
        ("valid_until", 9000),
    ],
)
def test_unsafe_manifest_refused(field, value):
    m = {**MANIFEST, field: value}
    c = {**config(), "manifest_sha256": w.sha(w.canonical(m))}
    with pytest.raises(ValueError):
        w.validate(c, m, 1500)


def test_expired_or_unapproved_config_is_inert():
    template = json.loads((ROOT / "deploy/beta/watchdog.example.json").read_text())
    with pytest.raises((ValueError, TypeError)):
        w.validate(template, MANIFEST, 1500)
    with pytest.raises(ValueError):
        w.validate(config(), MANIFEST, 8200)
    for old in w.EXPIRED:
        with pytest.raises(ValueError):
            w.validate({**config(), "deployment_id": old}, MANIFEST, 1500)


@pytest.mark.parametrize(
    "command",
    [
        w.DOCKER + ["start", ID],
        w.DOCKER + ["exec", ID, "true"],
        w.DOCKER + ["inspect", ID],
        ["systemctl", "restart", w.UNIT],
        ["iptables", "-F"],
    ],
)
def test_read_interface_denies_mutations_and_full_inspect(monkeypatch, command):
    monkeypatch.setattr(w.subprocess, "run", lambda *a, **k: pytest.fail("Mutation executed"))
    with pytest.raises(ValueError):
        w.command_read(command)


def test_exit_zero_security_halt_and_stale_or_inactive_controller_are_alerted():
    s = snapshot(1900)
    s["status"]["stage"] = "blocked_security_or_consent"
    s["state"] = {"Running": False, "ExitCode": 0}
    s["unit"] = "inactive"
    current = w.faults(s, MANIFEST, 2000)
    assert current["security_or_consent_halt"] == "critical"
    assert "controller_status_stale" in current and "controller_inactive" in current
    assert "worker_not_running" in current


def test_restart_backoff_startup_grace_and_deadline_overrun():
    s = snapshot()
    s["status"]["stage"] = "backoff"
    s["state"]["Running"] = False
    assert w.faults(s, MANIFEST, 2000) == {"worker_recovery": "warning"}
    assert w.faults(None, MANIFEST, 1100) == {}
    assert w.faults(None, MANIFEST, 1300) == {"observer_unavailable": "critical"}
    assert w.faults(snapshot(), MANIFEST, 8231) == {"deadline_overrun": "critical"}
    s = snapshot()
    s["status"].update(stage="closed", reason="approval_expired")
    s["state"]["Running"] = False
    assert w.faults(s, MANIFEST, 8190) == {}


def test_persistent_dedup_recovery_and_disabled_delivery():
    state = {}
    events = w.reconcile(state, {"worker_recovery": "warning"}, ID, 2000)
    assert len(events) == 1
    state = json.loads(json.dumps(state))  # simulated watchdog restart
    assert not w.reconcile(state, {"worker_recovery": "warning"}, ID, 2015)
    assert w.reconcile(state, {}, ID, 2030)[0]["event"]["event"] == "recovered"
    w.deliver(state, config(), 2045, sender=lambda *_: pytest.fail("Unapproved notification"))
    assert state["outbox"] == []


def test_delivery_retry_budget_and_redacted_errors(caplog):
    state = {}
    w.reconcile(state, {"observer_unavailable": "critical"}, ID, 2000)
    calls = []

    def fail(*args):
        calls.append(1)
        raise RuntimeError("https://private-webhook.example/secret-token")

    for now in (2000, 2015, 2060, 2120, 2180):
        w.deliver(state, {"delivery_enabled": True}, now, sender=fail)
    assert len(calls) == 3
    assert "secret-token" not in caplog.text


def test_private_dns_or_redirect_never_receives_a_webhook(monkeypatch):
    endpoint = b"https://alerts.example/secret"
    c = {
        "destination_file": "/not-read",
        "destination_sha256": w.sha(endpoint),
        "destination_host": "alerts.example",
        "payload_format": "generic",
    }
    monkeypatch.setattr(w, "secure_read", lambda *a, **k: endpoint)
    monkeypatch.setattr(
        w.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("169.254.169.254", 443))]
    )
    monkeypatch.setattr(
        w.http.client, "HTTPSConnection", lambda *a, **k: pytest.fail("Private network accessed")
    )
    with pytest.raises(ValueError, match="public HTTPS"):
        w.send_webhook(c, {})


def test_https_delivery_checks_tls_and_does_not_follow_redirects(monkeypatch):
    endpoint = b"https://alerts.example/secret"
    c = {
        "destination_file": "/not-read",
        "destination_sha256": w.sha(endpoint),
        "destination_host": "alerts.example",
        "payload_format": "slack",
    }
    monkeypatch.setattr(w, "secure_read", lambda *a, **k: endpoint)
    monkeypatch.setattr(
        w.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 443))]
    )
    calls = []

    class Fake:
        def __init__(self, host, port, timeout, context):
            assert context.check_hostname and context.verify_mode == w.ssl.CERT_REQUIRED
            assert (host, port) == ("alerts.example", 443)

        def request(self, method, path, body, headers):
            calls.append((method, path, json.loads(body)))

        def getresponse(self):
            return SimpleNamespace(status=302)

        def close(self):
            pass

    monkeypatch.setattr(w.http.client, "HTTPSConnection", Fake)
    event = {
        "event": "fault",
        "code": "observer_unavailable",
        "severity": "critical",
        "deployment_id": ID,
        "utc": "2026-11-11T00:00:00Z",
    }
    with pytest.raises(RuntimeError):
        w.send_webhook(c, event)
    assert len(calls) == 1 and set(calls[0][2]) == {"text"}


def test_alert_unit_survives_worker_failure_and_has_bounded_resources():
    unit = (ROOT / "deploy/beta/noetharaclipz-beta-alerts@.service").read_text()
    assert "BindsTo=" not in unit and "[Install]" not in unit
    for line in ("MemoryMax=64M", "CPUQuota=5%", "RuntimeMaxSec=7500", "StartLimitBurst=3"):
        assert line in unit
    assert not any(x in unit for x in ("docker start", "docker exec", "systemctl restart"))
