"""Proposed firewall scope/ordering and parser validation, no kernel writes."""

import importlib.util
import shutil
import subprocess
import os
import sys
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location(
    "egress_policy", Path(__file__).resolve().parents[2] / "deploy/worker/egress_policy.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_existing_services_never_match_proposed_shared_chain_hooks():
    commands = module.proposal()["apply_after_approval"]
    hooks = [cmd for cmd in commands if "-I" in cmd]
    assert len(hooks) == 2
    for command in hooks:
        assert command[command.index("-i") + 1] == "nccz-qa0"
    assert not any("-P" in cmd or "-F" in cmd for cmd in commands)
    assert commands[0][-2:] == ["-N", "NCZQA_EGRESS"]


def test_dns_exception_precedes_private_block_and_tls_is_after_blocks():
    rules = [cmd[5:] for cmd in module.proposal()["apply_after_approval"] if "-A" in cmd]
    assert all("172.31.0.2/32" in rule and "53" in rule and "RETURN" in rule for rule in rules[:2])
    https = next(i for i, rule in enumerate(rules) if "443" in rule)
    for cidr in ("169.254.0.0/16", "172.16.0.0/12", "10.0.0.0/8", "192.168.0.0/16"):
        assert next(i for i, rule in enumerate(rules) if cidr in rule) < https
    assert "REJECT" in rules[-1]


def test_rollback_deletes_only_reviewed_hooks_and_owned_chain_rules():
    for cmd in module.proposal()["rollback_after_worker_stop"]:
        assert "-F" not in cmd and "-P" not in cmd
        if "INPUT" in cmd or "DOCKER-USER" in cmd:
            assert "-D" in cmd and "nccz-qa0" in cmd
        else:
            assert "NCZQA_EGRESS" in cmd


@pytest.mark.skipif(not shutil.which("iptables-translate"), reason="Read-only parser unavailable")
def test_every_proposed_rule_translates_without_touching_kernel_rules():
    for cmd in module.proposal()["apply_after_approval"]:
        # iptables-translate is a pure syntax translator; never invoke iptables.
        result = subprocess.run(["iptables-translate"] + cmd[3:], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "nft" in result.stdout


def test_rendered_shell_refuses_accidental_execution_without_approval(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["egress_policy.py", "--format", "shell"])
    module.main()
    text = capsys.readouterr().out
    env = {k: v for k, v in os.environ.items() if k != "NC_QA_FIREWALL_APPROVED"}
    # The guard fails before any sudo/iptables command can execute.
    result = subprocess.run(["sh"], input=text, capture_output=True, text=True, env=env)
    assert result.returncode == 1
    assert "no rules applied" in result.stderr
