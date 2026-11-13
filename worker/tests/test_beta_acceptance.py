"""Fail-closed hosted workload gates; no network, login, media or jobs."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "beta_acceptance", ROOT / "scripts/beta_acceptance.py"
)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
ID = "11111111-1111-4111-8111-111111111111"


def approval():
    return {
        "deployment_id": ID,
        "owner_id": ID,
        "consent_id": ID,
        "operator_approved": True,
        "workload_trial_authorized": True,
        "cancellation_authorized": True,
        "global_processing": False,
        "gemini_enabled": False,
        "boot_start": False,
        "provider": "local-smolvlm2",
        "memory_bytes": 8 * 1024**3,
        "cpus": 2,
        "active_jobs": 1,
        "not_before": 1000,
        "valid_until": 8200,
        "frontend_origin": "https://noetharaclipz.lovable.app",
        "frontend_build": "a" * 40,
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("operator_approved", False),
        ("global_processing", True),
        ("gemini_enabled", True),
        ("boot_start", True),
        ("provider", "gemini"),
        ("frontend_origin", "http://127.0.0.1:8080"),
        ("frontend_origin", "https://unreviewed.example"),
        ("frontend_build", "development"),
        ("active_jobs", 2),
        ("cpus", 4),
        ("valid_until", 86400),
    ],
)
def test_refuses_unapproved_provider_host_or_scope(key, value):
    with pytest.raises(ValueError):
        b.validate_approval({**approval(), key: value}, "A", 2000)


def test_schedule_expiry_and_old_deployments_cannot_start_a_workload():
    b.validate_approval(approval(), "A", 1000)
    b.validate_approval(approval(), "B", 2200)
    for sample, now in (("B", 2000), ("F", 7300), ("A", 900), ("A", 8200)):
        with pytest.raises(ValueError):
            b.validate_approval(approval(), sample, now)
    for old in b.EXPIRED:
        with pytest.raises(ValueError):
            b.validate_approval({**approval(), "deployment_id": old}, "A", 2000)


def test_owner_consent_generation_and_readiness_must_match():
    a = approval()
    login = {"user": {"id": ID}}
    consent = {
        "owner_id": ID,
        "consent_id": ID,
        "approved_at": "1970-01-01T00:16:40Z",
        "expires_at": "1970-01-01T02:16:40Z",
        "revoked_at": None,
    }
    health = {"online": True, "ai_ready": True}
    b.verify_owner(a, login, consent, health)
    for kwargs in (
        {"login": {"user": {"id": "other-user"}}},
        {"consent": {**consent, "consent_id": "expired-consent"}},
        {"consent": {**consent, "revoked_at": "1970-01-01T00:20:00Z"}},
        {"consent": {**consent, "expires_at": "1970-01-01T03:00:00Z"}},
        {"health": {"online": True, "ai_ready": False}},
    ):
        args = {"login": login, "consent": consent, "health": health, **kwargs}
        with pytest.raises(ValueError):
            b.verify_owner(a, **args)
