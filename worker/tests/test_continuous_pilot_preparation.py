"""No AWS/Supabase/model operations: preparation collector boundaries only."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "pilot_inspector", ROOT / "scripts/inspect_continuous_pilot_host.py"
)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


@pytest.mark.parametrize(
    "command",
    [
        inspector.DOCKER + ["start", "expired-container"],
        inspector.DOCKER + ["restart", "anything"],
        inspector.DOCKER + ["run", "python"],
        inspector.DOCKER + ["exec", "anything", "python"],
        inspector.DOCKER + ["network", "create", "anything"],
        inspector.DOCKER + ["stats"],
        ["iptables", "--wait", "5", "-F"],
        ["iptables", "--wait", "5", "-I", "INPUT", "-j", "ACCEPT"],
        ["systemctl", "start", "noetharaclipz-continuous.service"],
        ["cat", "/etc/noetharaclipz-isolated/supabase-key"],
    ],
)
def test_read_only_collector_rejects_mutations_and_secret_commands(monkeypatch, command):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Rejected command reached the operating system")

    monkeypatch.setattr(inspector.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="prohibits"):
        inspector.read_command(command)


def test_only_current_verified_bundle_sources_can_be_imported(tmp_path):
    name = "host/example.py"
    source = "# Inert test fixture\n"
    file = tmp_path / name
    file.parent.mkdir()
    file.write_text(source)
    bundle = {
        "base_image": inspector.IMAGE,
        "source_dirty": False,
        "files": {name: source},
        "sha256": {name: hashlib.sha256(source.encode()).hexdigest()},
    }
    raw = json.dumps(bundle).encode()
    (tmp_path / "bundle.json").write_bytes(raw)
    expected = hashlib.sha256(raw).hexdigest()
    assert inspector.verify_sources(tmp_path, expected) == bundle
    file.write_text("# Changed fixture\n")
    with pytest.raises(ValueError, match="Changed staged source"):
        inspector.verify_sources(tmp_path, expected)
    with pytest.raises(ValueError, match="bundle hash changed"):
        inspector.verify_sources(tmp_path, "0" * 64)
