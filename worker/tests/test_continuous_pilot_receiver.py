"""Receiver validation only; no host, network, account or worker operations."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "pilot_receiver", ROOT / "scripts/receive_continuous_pilot_preparation.py"
)
receiver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receiver)


def fixture_payload(monkeypatch, name="host/example.py"):
    code = "# Inert receiver fixture\n"
    units = {
        name: "# Inert unit fixture\n"
        for name in ("noetharaclipz-isolation.service", "noetharaclipz-continuous.service")
    }
    bundle = {
        "source_dirty": False,
        "files": {name: code},
        "sha256": {name: receiver.sha(code.encode())},
        "units": units,
        "unit_sha256": {name: receiver.sha(code.encode()) for name, code in units.items()},
    }
    manifest = {
        "operator_approved": False,
        "valid_until": 0,
        "consent_id": receiver.CONSENT,
        "files": bundle["sha256"],
        "unit_sha256": bundle["unit_sha256"],
    }
    payload = {
        "format": "nccz-continuous-pilot-preparation-v1",
        "deployment_id": receiver.DEPLOYMENT,
        "owner_id": receiver.OWNER,
        "worker_start_authorized": False,
        "source_bundle_json": json.dumps(bundle),
        "collector": code,
        "manifest_proposal": manifest,
        "operator_approval_proposal": {
            "operator_approved": False,
            "worker_start_authorized": False,
        },
    }
    raw = receiver.canonical(payload)
    for key, value in {
        "HANDOFF_SHA": receiver.sha(raw),
        "BUNDLE_SHA": receiver.sha(payload["source_bundle_json"].encode()),
        "COLLECTOR_SHA": receiver.sha(code.encode()),
        "MANIFEST_SHA": receiver.sha(receiver.canonical(manifest)),
    }.items():
        monkeypatch.setattr(receiver, key, value)
    return raw


def test_tampered_private_handoff_is_rejected_before_staging(monkeypatch):
    raw = fixture_payload(monkeypatch)
    receiver.validate_payload(raw)
    with pytest.raises(ValueError, match="hash mismatch"):
        receiver.validate_payload(raw + b" ")


@pytest.mark.parametrize("path", ["/outside.py", "host/../../outside.py", "host\\outside.py"])
def test_source_extraction_cannot_escape_private_directory(monkeypatch, path):
    raw = fixture_payload(monkeypatch, path)
    with pytest.raises(ValueError, match="Unsafe or changed source path"):
        receiver.validate_payload(raw)


def test_existing_or_symlink_receipts_cannot_be_overwritten(tmp_path):
    target = tmp_path / "transfer-receipt.json"
    receiver.write_new(target, {"verified": True})
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        receiver.write_new(target, {"verified": False})
    link = tmp_path / "host-preflight.json"
    link.symlink_to(target)
    with pytest.raises(FileExistsError):
        receiver.write_new(link, {})
    assert target.read_bytes() == original
