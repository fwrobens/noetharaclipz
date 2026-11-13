"""No deployment: enforce exact authorization, time bounds and unit scope."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "pilot_launch", ROOT / "scripts/launch_continuous_pilot_2100.py"
)
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


def payload():
    manifest = json.loads(
        (ROOT / "docs/evidence/continuous-pilot-2100-manifest-candidate.json").read_text()
    )
    manifest.update(operator_approved=True, approval_reference="Unit fixture only")
    return {
        "authorization": {
            "user_reply": "yes",
            "candidate_sha256": launch.CANDIDATE,
            "processing_approval_authorized": True,
            "installation_and_start_authorized": True,
            "approval_reference": "Unit fixture only",
        },
        "manifest": manifest,
        "manifest_sha256": launch.sha(launch.canonical(manifest)),
    }


def test_both_explicit_grants_and_exact_candidate_are_required():
    value = payload()
    launch.validate_authorization(value)
    value["authorization"]["installation_and_start_authorized"] = False
    with pytest.raises(ValueError, match="Missing exact"):
        launch.validate_authorization(value)


@pytest.mark.parametrize(
    "key,value", [("cpus", 4), ("global_processing", True), ("restore_isolation", True)]
)
def test_approval_cannot_expand_reviewed_scope(key, value):
    request = payload()
    request["manifest"][key] = value
    request["manifest_sha256"] = launch.sha(launch.canonical(request["manifest"]))
    with pytest.raises(ValueError, match="scope changed"):
        launch.validate_authorization(request)


@pytest.mark.parametrize("now", [launch.START - 1, launch.STOP - 600, launch.STOP + 1])
def test_no_early_late_or_expired_launch(now):
    with pytest.raises(ValueError, match="approved launch window"):
        launch.require_window(now)


@pytest.mark.parametrize(
    "args",
    [
        ("restart", "docker.service"),
        ("enable", launch.UNIT),
        ("stop", "noethara-ec2-staging-worker.service"),
    ],
)
def test_launcher_cannot_restart_or_enable_unrelated_services(monkeypatch, args):
    def forbidden(*_a, **_kw):
        pytest.fail("Out-of-scope operation reached systemd")

    monkeypatch.setattr(launch.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="Unrelated"):
        launch.systemctl(*args)
