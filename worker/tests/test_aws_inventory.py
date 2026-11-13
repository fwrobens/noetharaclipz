"""Local AWS response contracts; never contact AWS or install credentials."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest


@pytest.mark.parametrize("burstable", [False, True])
def test_inventory_only_queries_credit_controls_for_burstable_instances(
    monkeypatch, tmp_path, burstable
):
    script = Path(__file__).resolve().parents[2] / "scripts/aws_worker_inventory.py"
    spec = importlib.util.spec_from_file_location("aws_inventory_contract", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "inventory.json"
    monkeypatch.setattr("sys.argv", [str(script), "--region", "us-east-2", "--output", str(target)])
    monkeypatch.setattr(module.shutil, "which", lambda name: "/contract-only/aws")
    requests = []

    def run(cmd, **kwargs):
        requests.append(cmd)
        if "describe-instances" in cmd:
            response = {
                "Reservations": [
                    {"Instances": [{"InstanceType": "t2.xlarge" if burstable else "m6i.2xlarge"}]}
                ]
            }
        elif "describe-instance-types" in cmd:
            response = {"InstanceTypes": [{"BurstablePerformanceSupported": burstable}]}
        else:
            response = {}
        return SimpleNamespace(returncode=0, stdout=json.dumps(response))

    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.main() == 0
    report = json.loads(target.read_text())
    assert ("CPUCreditBalance" in report["metrics"]) is burstable
    assert any("describe-instance-credit-specifications" in cmd for cmd in requests) is burstable
    assert report["host_capacity_verified"] is False
    if not burstable:
        assert report["credit_mode"] == "not applicable: non-burstable instance"
