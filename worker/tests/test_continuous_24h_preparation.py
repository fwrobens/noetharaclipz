"""24h preparation uses inert fixtures; never AWS, Supabase, Docker or models."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receiver = load("receive_continuous_24h_preparation")
collector = load("inspect_continuous_24h_host")


@pytest.mark.parametrize(
    "command",
    [
        collector.admission.DOCKER + ["run", "anything"],
        collector.admission.DOCKER + ["exec", "anything", "python"],
        collector.admission.DOCKER + ["start", collector.PREVIOUS_CID],
        collector.admission.DOCKER + ["network", "create", "new"],
        ["systemctl", "start", collector.UNITS[1]],
        ["systemctl", "enable", collector.UNITS[1]],
        ["systemctl", "stop", collector.UNITS[0]],
        ["systemctl", "show", "docker.service"],
        ["iptables", "--wait", "5", "-F"],
        ["cat", "/etc/noetharaclipz-isolated/supabase-key"],
    ],
)
def test_collector_never_executes_mutations_or_credentials(monkeypatch, command):
    monkeypatch.setattr(
        collector.subprocess, "run", lambda *a, **k: pytest.fail("OS command reached")
    )
    with pytest.raises(ValueError, match="prohibits"):
        collector.read_command(command)


def fixture(monkeypatch):
    bundle = {
        "base_image": receiver.IMAGE,
        "source_dirty": False,
        "files": {"host/inert.py": "# fixture\n"},
        "units": {},
        "sha256": {"host/inert.py": receiver.sha(b"# fixture\n")},
        "unit_sha256": {},
    }
    raw = json.dumps(bundle)
    monkeypatch.setattr(receiver, "SOURCE_SHA", receiver.sha(raw.encode()))
    helpers = {
        "inspect_continuous_pilot_host.py": "# base fixture\n",
        "inspect_continuous_24h_host.py": "# collector fixture\n",
    }
    return {
        "format": "nccz-24h-preparation-v1",
        "deployment_id": "70000000-0000-0000-0000-000000000001",
        "owner_id": receiver.OWNER,
        "operator_approved": False,
        "worker_start_authorized": False,
        "boot_start_authorized": False,
        "source_bundle_json": raw,
        "helpers": helpers,
        "helper_sha256": {k: receiver.sha(v.encode()) for k, v in helpers.items()},
    }


@pytest.mark.parametrize(
    "flag", ["operator_approved", "worker_start_authorized", "boot_start_authorized"]
)
def test_preparation_cannot_authorize_a_worker(monkeypatch, flag):
    payload = fixture(monkeypatch)
    receiver.validate(payload)
    payload[flag] = True
    with pytest.raises(ValueError, match="authorized preparation"):
        receiver.validate(payload)


def test_old_deployment_cannot_be_reused(monkeypatch):
    payload = fixture(monkeypatch)
    payload["deployment_id"] = collector.PREVIOUS
    with pytest.raises(ValueError):
        receiver.validate(payload)


@pytest.mark.parametrize("path", ["../escape.py", "/escape.py", "host\\escape.py"])
def test_source_paths_cannot_escape_preparation_directory(monkeypatch, path):
    payload = fixture(monkeypatch)
    payload["helpers"][path] = "# fixture"
    payload["helper_sha256"][path] = receiver.sha(b"# fixture")
    with pytest.raises(ValueError):
        receiver.validate(payload)


def test_receipts_are_never_overwritten_or_followed(tmp_path):
    path = tmp_path / "receipt.json"
    receiver.write_new(path, b"original")
    with pytest.raises(FileExistsError):
        receiver.write_new(path, b"replacement")
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(FileExistsError):
        receiver.write_new(link, b"replacement")
    assert path.read_bytes() == b"original"


def test_helper_hash_changes_are_detected(monkeypatch):
    payload = fixture(monkeypatch)
    payload["helpers"]["inspect_continuous_24h_host.py"] += "# tampered"
    with pytest.raises(ValueError, match="changed private source"):
        receiver.validate(payload)


def test_model_file_integrity_is_checked_without_loading_or_following_external_links(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    blob = models / "blob"
    blob.write_bytes(b"pinned model fixture")
    link = models / "snapshot"
    link.symlink_to(blob)
    assert collector.file_digest(link, models) == hashlib.sha256(blob.read_bytes()).hexdigest()
    other = tmp_path / "outside"
    other.write_bytes(b"foreign")
    link.unlink()
    link.symlink_to(other)
    with pytest.raises(ValueError, match="outside its dedicated directory"):
        collector.file_digest(link, models)


def test_retained_evidence_excludes_credentials_and_media(monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "ETC", tmp_path / "etc")
    monkeypatch.setattr(collector, "DATA", tmp_path / "data")
    for base, name in [
        (collector.ETC, "code"),
        (collector.ETC, "public"),
        (collector.ETC, "systemd"),
        (collector.DATA, "reports"),
    ]:
        path = base / collector.PREVIOUS / name
        path.mkdir(parents=True)
        (path / "evidence").write_text("retained")
    first = collector.retained_evidence()
    assert first["files"] == 4
    (collector.DATA / collector.PREVIOUS / "supabase-key").write_text("never read")
    assert collector.retained_evidence() == first
    (collector.DATA / collector.PREVIOUS / "reports/evidence").write_text("changed")
    assert collector.retained_evidence() != first


def test_loaded_unit_dropins_and_daemon_drift_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(collector, "UNIT_DIR", tmp_path)
    unit = collector.UNITS[1]
    path = tmp_path / unit
    path.write_text("# test unit\n")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    props = {"FragmentPath": str(path), "DropInPaths": "", "NeedDaemonReload": "no"}

    def read(command):
        if command[1] == "show":
            assert command == ["systemctl", "show", "--all", unit]
        return (
            "\n".join(k + "=" + v for k, v in props.items()) if command[1] == "show" else "disabled"
        )

    monkeypatch.setattr(collector, "read_command", read)
    # Tests may run as a non-root workspace user. Unit metadata is inert here.
    from types import SimpleNamespace

    stat = Path.lstat
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda p: SimpleNamespace(st_uid=0, st_mode=0o100644) if p == path else stat(p),
    )
    assert collector.unit_state(unit, expected)["loaded_reviewed_unit"]
    props["DropInPaths"] = "/etc/systemd/system/foreign.conf"
    assert not collector.unit_state(unit, expected)["loaded_reviewed_unit"]
    props["DropInPaths"], props["NeedDaemonReload"] = "", "yes"
    assert not collector.unit_state(unit, expected)["loaded_reviewed_unit"]
    props["NeedDaemonReload"] = "no"
    del props["DropInPaths"]
    assert not collector.unit_state(unit, expected)["loaded_reviewed_unit"]
