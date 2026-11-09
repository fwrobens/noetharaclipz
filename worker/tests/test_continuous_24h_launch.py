"""No deployment: real filesystem handover with inert API/systemd doubles."""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
from types import SimpleNamespace
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "pilot24h_launch", ROOT / "scripts/launch_continuous_24h_pilot.py"
)
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


def plan():
    value = json.loads(
        (ROOT / "docs/evidence/continuous-pilot-2100-manifest-candidate.json").read_text()
    )
    value.update(
        deployment_id="70000000-0000-0000-0000-000000000001",
        consent_id="70000000-0000-0000-0000-000000000002",
        not_before=int(time.time()) - 10,
        valid_until=int(time.time()) - 10 + 86400,
    )
    ref = "Inert unit fixture; not operator approval"
    return {
        "format": "nccz-24h-reviewed-plan-v1",
        "manifest_candidate": value,
        "candidate_sha256": launch.sha(launch.canonical(value)),
        "activation_manifest_sha256": launch.sha(
            launch.canonical(dict(value, operator_approved=True, approval_reference=ref))
        ),
        "approval_reference": ref,
        "boot_start_authorized": False,
        "systemd_only": True,
        "authorization_object": "_worker-transfer/10000000-0000-0000-0000-000000000001/24h-operator-authorization-"
        + value["deployment_id"]
        + ".json",
    }


def receipt(p):
    m = p["manifest_candidate"]
    return {
        "format": "nccz-24h-operator-authorization-v1",
        "deployment_id": m["deployment_id"],
        "owner_id": m["owner_id"],
        "consent_id": m["consent_id"],
        "candidate_sha256": p["candidate_sha256"],
        "manifest_sha256": p["activation_manifest_sha256"],
        "approval_reference": p["approval_reference"],
        "not_before": m["not_before"],
        "valid_until": m["valid_until"],
        "processing_approval_authorized": True,
        "installation_and_start_authorized": True,
        "boot_start_authorized": False,
        "global_processing": False,
        "explicit_user_reply": "Unit fixture; never a real approval",
        "authorized_at_utc": datetime.now(timezone.utc).isoformat(),
    }


@pytest.mark.parametrize(
    "change",
    [
        {"consent_id": launch.OLD_CONSENT},
        {"deployment_id": launch.PREVIOUS},
        {"operator_approved": True},
        {"cpus": 3},
        {"memory_bytes": 16 * 1024**3},
        {"active_jobs": 2},
        {"global_processing": True},
        {"gemini_enabled": True},
        {"restore_isolation": True},
        {"valid_until": 1},
    ],
)
def test_review_scope_cannot_reuse_or_expand_pilot(change):
    p = plan()
    p["manifest_candidate"].update(change)
    with pytest.raises(ValueError):
        launch.validate_plan(p)


@pytest.mark.parametrize(
    "change",
    [
        {"installation_and_start_authorized": False},
        {"processing_approval_authorized": False},
        {"boot_start_authorized": True},
        {"global_processing": True},
        {"explicit_user_reply": ""},
        {"manifest_sha256": "0" * 64},
        {"consent_id": launch.OLD_CONSENT},
        {"valid_until": 1},
    ],
)
def test_explicit_approval_must_bind_exact_manifest_owner_generation_and_window(change):
    p = plan()
    r = receipt(p)
    launch.validate_authorization(r, p)
    r.update(change)
    with pytest.raises(ValueError, match="Separate explicit"):
        launch.validate_authorization(r, p)


@pytest.mark.parametrize("offset", [-1, 300, 86400])
def test_early_late_and_expired_launch_never_waits_or_shifts_window(offset):
    m = plan()["manifest_candidate"]
    with pytest.raises(ValueError, match="first five minutes"):
        launch.require_window(m, m["not_before"] + offset)
    assert m["valid_until"] - m["not_before"] == 86400


@pytest.mark.parametrize(
    "args",
    [
        ("enable", launch.UNIT),
        ("restart", launch.UNIT),
        ("start", "docker.service"),
        ("stop", "noethara-ec2-staging-worker-1"),
        ("start", launch.UNIT),
    ],
)
def test_only_nonblocking_start_of_pilot_and_scoped_stop_are_executable(monkeypatch, args):
    monkeypatch.setattr(
        launch.subprocess, "run", lambda *a, **k: pytest.fail("Forbidden systemd command executed")
    )
    with pytest.raises(ValueError, match="dedicated pilot"):
        launch.unit_action(*args)


def test_systemd_start_is_detached_and_has_no_terminal_wait(monkeypatch):
    seen = []
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda command, **kwargs: seen.append(command) or SimpleNamespace(returncode=0),
    )
    launch.unit_action("start", "--no-block", launch.UNIT)
    assert seen == [["systemctl", "start", "--no-block", launch.UNIT]]


def test_missing_private_approval_cannot_be_treated_as_approval():
    def missing(path):
        raise urllib.error.HTTPError(path, 404, "not found", {}, None)

    assert launch.read_authorization(SimpleNamespace(call=missing), plan()) is None


def test_changed_current_pointer_is_never_overwritten(tmp_path):
    old, new, foreign = (tmp_path / n for n in ("old", "new", "foreign"))
    for path in (old, new, foreign):
        path.mkdir()
    current = tmp_path / "current"
    current.symlink_to(foreign)
    with pytest.raises(ValueError, match="refuse handover"):
        launch.select_current(current, old, new, "new-id")
    assert current.resolve() == foreign


def activation_fixture(monkeypatch, tmp_path, fail=False):
    p = plan()
    m = launch.validate_plan(p)
    r = receipt(p)
    root, etc, data = (tmp_path / n for n in ("received", "etc", "data"))
    for path in (root, etc, data):
        path.mkdir()
    old = etc / launch.PREVIOUS
    old.mkdir()
    (old / "evidence").write_bytes(b"immutable old evidence")
    (etc / "current").symlink_to(old)
    events = []

    def install(bundle, active):
        events.append("install")
        assert json.loads(active.read_text()) == m
        (etc / m["deployment_id"] / "gates").mkdir(parents=True)
        (data / m["deployment_id"] / "reports").mkdir(parents=True)
        return {"installed": True, "worker_started": False}

    def rpc(name, **params):
        events.append(name)
        if name == "approve_processing_consent":
            return {
                "owner_id": launch.OWNER,
                "consent_id": m["consent_id"],
                "expires_at": params["expires_at"],
            }
        assert name == "revoke_owner_processing"
        return True

    def unit(*args):
        events.append(args)
        if args == ("start", "--no-block", launch.UNIT) and fail:
            raise RuntimeError("inert simulated start failure")

    monkeypatch.setattr(launch, "unit_action", unit)
    host = SimpleNamespace(
        ETC=etc,
        DATA=data,
        install=install,
        atomic=lambda path, value: path.write_bytes(launch.canonical(value)),
    )
    api = SimpleNamespace(rpc=rpc)
    return root, p, r, m, host, api, events, old


def test_handover_preserves_old_files_and_only_starts_via_systemd_after_approval(
    monkeypatch, tmp_path
):
    root, p, r, m, host, api, events, old = activation_fixture(monkeypatch, tmp_path)
    result = launch.activate(root, p, r, m, host, api, {"read_only": True})
    assert events == [
        "install",
        ("stop", launch.ISOLATION),
        "approve_processing_consent",
        ("start", "--no-block", launch.UNIT),
    ]
    assert (old / "evidence").read_bytes() == b"immutable old evidence"
    assert (host.ETC / "current").resolve() == host.ETC / m["deployment_id"]
    assert result["systemd_detached"] and result["boot_enabled"] is False
    assert result["readiness_verified"] is False
    with pytest.raises(FileExistsError):
        launch.activate(root, p, r, m, host, api, {})


def test_failed_start_revokes_only_new_scope_restores_pointer_and_retains_both_evidences(
    monkeypatch, tmp_path
):
    root, p, r, m, host, api, events, old = activation_fixture(monkeypatch, tmp_path, fail=True)
    with pytest.raises(RuntimeError, match="simulated"):
        launch.activate(root, p, r, m, host, api, {})
    assert "revoke_owner_processing" in events
    assert (host.ETC / "current").resolve() == old
    assert (old / "evidence").read_bytes() == b"immutable old evidence"
    assert (host.DATA / m["deployment_id"] / "revoked.json").exists()
    assert (root / "launch-failure.json").exists()
    assert ("start", "--no-block", launch.ISOLATION) not in events


def test_no_approval_has_no_installation_handover_or_systemd_side_effects(monkeypatch, tmp_path):
    root, p, r, m, host, api, events, old = activation_fixture(monkeypatch, tmp_path)
    r["installation_and_start_authorized"] = False
    with pytest.raises(ValueError, match="Separate explicit"):
        launch.activate(root, p, r, m, host, api, {})
    assert events == []
    assert (host.ETC / "current").resolve() == old
    assert not (root / "launch-attempt.json").exists()


def test_disk_failure_during_cleanup_cannot_skip_service_stop_or_server_revocation(
    monkeypatch, tmp_path
):
    root, p, r, m, host, api, events, old = activation_fixture(monkeypatch, tmp_path, fail=True)

    def full_disk(*args, **kwargs):
        raise OSError("inert full-disk fixture")

    host.atomic = full_disk
    with pytest.raises(RuntimeError, match="simulated"):
        launch.activate(root, p, r, m, host, api, {})
    assert ("stop", launch.UNIT) in events
    assert "revoke_owner_processing" in events
    assert (host.ETC / "current").resolve() == old


def test_received_supplemental_collector_and_report_must_match_reviewed_hashes(
    monkeypatch, tmp_path
):
    p = plan()
    root = tmp_path / "received"
    root.mkdir(mode=0o700)
    (root / "handoff").mkdir()
    base = root / "handoff/base.py"
    base.write_bytes(b"# original immutable helper\n")
    updated = root / "handoff/collector-v2.py"
    updated.write_bytes(b"# separately reviewed corrected helper\n")
    report = root / "report-v2.json"
    report.write_bytes(b'{"host_preparation_checks_passed":true}')
    m = p["manifest_candidate"]
    bundle = {
        "sha256": m["files"],
        "unit_sha256": m["unit_sha256"],
        "source_commit": m["source_commit"],
    }
    raw = launch.canonical(bundle)
    (root / "bundle.json").write_bytes(raw)
    monkeypatch.setattr(launch, "SOURCE_SHA", launch.sha(raw))
    payload = {
        "deployment_id": m["deployment_id"],
        "owner_id": m["owner_id"],
        "operator_approved": False,
        "helper_sha256": {base.name: launch.sha(base.read_bytes())},
    }
    raw = launch.canonical(payload)
    (root / "preparation.json").write_bytes(raw)
    p.update(
        preparation_sha256=launch.sha(raw),
        admission_helper_name=updated.name,
        admission_helper_sha256=launch.sha(updated.read_bytes()),
        admission_report_name=report.name,
        admission_report_sha256=launch.sha(report.read_bytes()),
    )
    # Metadata fixture only: the workspace test runner need not be root.
    original_stat = Path.stat

    def stat(path, *args, **kwargs):
        info = original_stat(path, *args, **kwargs)
        return SimpleNamespace(st_uid=0, st_mode=info.st_mode)

    monkeypatch.setattr(Path, "stat", stat)
    launch.verify_preparation(root, p)
    original = updated.read_bytes()
    updated.write_bytes(original + b"# changed")
    with pytest.raises(ValueError, match="supplemental admission"):
        launch.verify_preparation(root, p)
    updated.write_bytes(original)
    report.write_bytes(b"{}")
    with pytest.raises(ValueError, match="supplemental admission"):
        launch.verify_preparation(root, p)
