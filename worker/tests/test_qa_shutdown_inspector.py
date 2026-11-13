"""Stopped-container evidence must never start work or turn missing peaks into 0."""
# ruff: noqa: E402

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/worker"))
import inspect_qa_shutdown as inspector


def stopped():
    return {"state": {"Status": "exited", "Running": False, "Restarting": False, "Pid": 0,
                      "ExitCode": 0, "OOMKilled": False, "FinishedAt": "2026-11-09T00:50:38.123456789Z"},
            "restart_policy": {"Name": "on-failure", "MaximumRetryCount": 3},
            "entrypoint": ["python", "/run/qa-deadline.py"]}


def environment():
    return {"NC_QA_STOP_AT": str(inspector.DEADLINE), "NC_QA_TRIAL_ID": inspector.TRIAL,
            "NC_WORKER_OWNER_ID": inspector.OWNER, "NC_DEPLOY_MODE": "qa", "NC_AI_PROVIDER": "local",
            "GEMINI_FREE_TIER_VERIFIED": "false", "NC_GLOBAL_QUEUE_APPROVED": "false"}


def test_stopped_clean_exit_and_unchanged_deadline_support_separate_findings():
    findings = inspector.restart_findings(stopped(), environment(), True, inspector.DEADLINE + 100)
    assert findings["docker_container_stopped"] and findings["normal_exit_without_oom"]
    assert findings["finished_within_approved_window"]
    assert findings["docker_on_failure_policy_does_not_restart_this_normal_exit"]
    assert findings["unchanged_expired_wrapper_blocks_processing_before_models_or_credentials"]


@pytest.mark.parametrize("change", [{"ExitCode": 137}, {"OOMKilled": True}, {"Running": True, "Status": "running", "Pid": 123}])
def test_running_or_failed_containers_are_not_reported_as_cleanly_stopped(change):
    info = stopped()
    info["state"].update(change)
    assert not inspector.restart_findings(info, environment(), True, inspector.DEADLINE + 100)["normal_exit_without_oom"]


def test_late_exit_and_always_restart_policy_are_not_approved():
    info = stopped()
    info["state"]["FinishedAt"] = "2026-11-09T01:00:00Z"
    info["restart_policy"] = {"Name": "always", "MaximumRetryCount": 0}
    findings = inspector.restart_findings(info, environment(), True, inspector.DEADLINE + 100)
    assert not findings["finished_within_approved_window"]
    assert not findings["docker_on_failure_policy_does_not_restart_this_normal_exit"]


@pytest.mark.parametrize("changed", [{"NC_QA_STOP_AT": "9999999999"}, {"NC_DEPLOY_MODE": "global"},
    {"NC_GLOBAL_QUEUE_APPROVED": "true"}, {"GEMINI_FREE_TIER_VERIFIED": "true"}, {"NC_WORKER_OWNER_ID": ""}])
def test_changed_scope_or_deadline_invalidates_restart_safeguard(changed):
    findings = inspector.restart_findings(stopped(), {**environment(), **changed}, True, inspector.DEADLINE + 100)
    assert not findings["unchanged_expired_wrapper_blocks_processing_before_models_or_credentials"]


def test_modified_wrapper_invalidates_source_safeguard():
    assert not inspector.restart_findings(stopped(), environment(), False, inspector.DEADLINE + 100)["unchanged_expired_wrapper_blocks_processing_before_models_or_credentials"]


@pytest.mark.parametrize("operation", ["run", "start", "restart", "exec", "update", "stop", "rm", "compose", "network", "image"])
def test_inspector_refuses_every_docker_mutation_or_container_execution(operation, monkeypatch):
    monkeypatch.setattr(inspector.subprocess, "run", lambda *_a, **_k: pytest.fail("A disallowed command reached Docker"))
    with pytest.raises(ValueError, match="read-only"):
        inspector.read([operation, inspector.CID])


def test_absent_cgroup_is_unavailable_not_zero(monkeypatch):
    class Missing:
        def __truediv__(self, _name):
            return self
        def is_dir(self):
            return False
    monkeypatch.setattr(inspector, "Path", lambda _path: Missing())
    usage = inspector.resource_counters()
    assert usage["available"] is False
    assert usage["peak_ram_bytes"] is None and usage["cpu_usage_seconds"] is None


def test_log_redaction_removes_credentials():
    source = 'Bearer abc-secret sb_secret_privatevalue eyJheader.eyJclaims.signature password=hunter2 token=private'
    safe = inspector.redact(source)
    for secret in ("abc-secret", "sb_secret_privatevalue", "eyJheader.eyJclaims.signature", "hunter2", "token=private"):
        assert secret not in safe
