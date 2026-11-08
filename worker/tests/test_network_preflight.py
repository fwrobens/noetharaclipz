"""Network preflight fail-closed ownership and real-denial evidence boundaries."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "deploy/worker"


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


net = module("network_preflight")
policy = module("egress_policy")


def snapshot(**changes):
    result = {"instance": net.INSTANCE, "ram": 20 * 1024**3, "disk": 40 * 1024**3,
              "ip_forward": True,
              "project_containers": "", "networks": ["bridge", "existing-app"],
              "links": ["lo", "enX0"], "firewall": ["-A FORWARD -j DOCKER-USER"],
              "cidrs": ["172.17.0.0/16", "172.18.0.0/16", "172.19.0.0/16", "172.31.32.0/20"]}
    return {**result, **changes}


def test_admission_allows_only_the_unused_reviewed_host_envelope():
    net.admit(snapshot())


@pytest.mark.parametrize("changes", [
    {"instance": "another-instance"}, {"ram": 9 * 1024**3}, {"disk": 19 * 1024**3}, {"ip_forward": False},
    {"project_containers": "existing-stopped-worker"}, {"networks": [net.NETWORK]},
    {"links": [net.BRIDGE]}, {"firewall": ["-N " + net.CHAIN]},
    {"firewall": ["-A FORWARD -j ACCEPT", "-A FORWARD -j DOCKER-USER"]},
    {"cidrs": ["172.20.0.0/16"]},
])
def test_wrong_host_foreign_resources_or_bypass_order_abort_before_policy(changes):
    with pytest.raises(ValueError):
        net.admit(snapshot(**changes))


def test_rollback_of_every_successful_prefix_never_flushes_shared_rules():
    commands = policy.proposal()["apply_after_approval"]
    assert [net.inverse_rule(x) for x in reversed(commands)] == policy.proposal()["rollback_after_worker_stop"]
    for end in range(1, len(commands)):
        undo = [net.inverse_rule(x) for x in reversed(commands[:end])]
        assert all("-F" not in x and "-P" not in x for x in undo)
        assert undo[-1][-2:] == ["-X", net.CHAIN]


@pytest.mark.parametrize("command", [
    ["iptables", "--wait", "5", "-F", "INPUT"],
    ["iptables", "--wait", "5", "-A", "OTHER_APP", "-j", "ACCEPT"],
    ["iptables", "--wait", "5", "-I", "INPUT", "1", "-i", "enX0", "-j", "ACCEPT"],
])
def test_never_construct_an_undo_for_foreign_or_global_rules(command):
    with pytest.raises(ValueError):
        net.inverse_rule(command)


def test_closed_port_or_timeout_is_not_a_firewall_isolation_pass():
    with pytest.raises(ValueError):
        net.rejection_verified(4, 4, connected=False)
    with pytest.raises(ValueError):
        net.rejection_verified(4, 5, connected=True)
    assert net.rejection_verified(4, 5, connected=False)


def test_audit_receipt_cannot_overwrite_another_attempt(tmp_path):
    path = tmp_path / "receipt.json"
    original = {"probe_id": "owned", "phase": "starting"}
    net.save_report(path, original, create=True)
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        net.save_report(path, {"probe_id": "other"}, create=True)
    with pytest.raises(ValueError):
        net.save_report(path, {"probe_id": "other"})
    assert json.loads(path.read_text()) == original


def test_audit_receipt_does_not_follow_a_replaced_symlink(tmp_path):
    target = tmp_path / "other-app.json"
    target.write_text('{"probe_id":"owned","untouched":true}')
    link = tmp_path / "receipt.json"
    link.symlink_to(target)
    with pytest.raises(OSError):
        net.save_report(link, {"probe_id": "owned", "phase": "changed"})
    assert json.loads(target.read_text())["untouched"] is True
