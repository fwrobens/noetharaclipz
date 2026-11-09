"""No Docker/model/queue starts: exercise approval, restart gate and real counter parsing."""
# ruff: noqa: E402

import json
import io
import signal
import subprocess
import sys
import threading
import time
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "deploy/worker"
sys.path.insert(0, str(ROOT))
import reliability_entry as entry
import reliability_host as host
import reliability_metrics as metrics
import reliability_platform as platform
import reliability_policy as policy
import reliability_probe as probe

TRIAL = "bebbf5ad-094f-4b6f-964f-c7ac22e1f760"
OWNER = "84d8ae5f-a46d-4c67-82a3-98d80a881507"


def plan():
    return {"trial_id": TRIAL, "instance": host.INSTANCE, "image": host.IMAGE, "maximum_seconds": 1800,
            "memory_bytes": 8 * 1024**3, "cpus": 2, "active_jobs": 1, "global_processing": False,
            "gemini_enabled": False, "owner_policy": "fresh_empty_owner_after_separate_approval",
            "requires_future_approval": True, "sample": {"duration_seconds": 180, "bytes": 18_575_024,
                "looped_or_concatenated": False, "sha256": "sample-sha"}, "code_sha256": {},
            "model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
            "model_revision": "7b375e1b73b11138ff12fe22c8f2822d8fe03467"}


def approval():
    return {"trial_id": TRIAL, "separately_authorized": True, "provider": "local", "owner_id": OWNER,
            "global_processing": False, "gemini_enabled": False, "crash_test": "runner_sigkill_once",
            "approved_at_unix": 1000, "stop_at_unix": 2800, "plan_sha256": "pinned-plan"}


@pytest.mark.parametrize("change", [{"cpus": 3}, {"memory_bytes": 16 * 1024**3}, {"active_jobs": 2},
    {"maximum_seconds": 1801}, {"global_processing": True}, {"gemini_enabled": True},
    {"requires_future_approval": False}, {"owner_policy": "all_users"}, {"trial_id": host.OLD_TRIAL}])
def test_plan_cannot_expand_scope_or_reopen_expired_trial(change):
    with pytest.raises(ValueError):
        host.validate_plan({**plan(), **change})


def test_exact_prepared_plan_and_separate_future_approval_are_required():
    host.validate_plan(plan())
    assert policy.validate_approval(plan(), approval(), 1100) == OWNER


@pytest.mark.parametrize("change", [{"separately_authorized": False}, {"global_processing": True},
    {"gemini_enabled": True}, {"owner_id": policy.OLD_OWNER}, {"trial_id": host.OLD_TRIAL},
    {"stop_at_unix": 2801}, {"stop_at_unix": 1099}, {"approved_at_unix": 1200}, {"crash_test": "host_reboot"}])
def test_bad_or_expired_approval_is_rejected(change):
    with pytest.raises(ValueError):
        policy.validate_approval(plan(), {**approval(), **change}, 1100)


def fresh_user():
    return {"id": OWNER, "created_at": "1970-01-01T00:16:41+00:00", "app_metadata": {"nccz_qa_trial": TRIAL}}


def test_only_new_empty_owner_can_opt_in_using_existing_owner_scoped_rpc():
    policy.validate_fresh_owner(plan(), approval(), fresh_user(), [], "different-protected-owner")
    for projects in ([{"id": "old-project"}],):
        with pytest.raises(ValueError):
            policy.validate_fresh_owner(plan(), approval(), fresh_user(), projects, "different-protected-owner")
    for changed in ({"created_at": "1970-01-01T00:16:39+00:00"}, {"app_metadata": {}}, {"id": policy.OLD_OWNER}):
        with pytest.raises(ValueError):
            policy.validate_fresh_owner(plan(), approval(), {**fresh_user(), **changed}, [], "different-protected-owner")
    with pytest.raises(ValueError):
        policy.validate_fresh_owner(plan(), approval(), fresh_user(), [], OWNER)
    with pytest.raises(ValueError, match="atomic"):
        policy.existing_user_release(OWNER, [policy.PROTECTED_JOB])


def test_absent_approval_cannot_reach_credentials_docker_or_systemd(monkeypatch, tmp_path):
    monkeypatch.setattr(host, "load_trial", lambda _trial: (tmp_path, tmp_path, plan(), "pinned-plan"))
    monkeypatch.setattr(host, "admission", lambda: pytest.fail("Host admission reached without approval"))
    monkeypatch.setattr(host, "API", lambda: pytest.fail("Credential was read without approval"))
    monkeypatch.setattr(host, "run", lambda *_a, **_k: pytest.fail("Subprocess launched without approval"))
    with pytest.raises(FileNotFoundError):
        host.launch(TRIAL, tmp_path / "not-issued.json", "not-issued")


def test_expired_entry_exits_before_quota_model_secret_or_subprocess(monkeypatch, tmp_path):
    activation = tmp_path / "activation.json"
    activation.write_text(json.dumps(approval()))
    monkeypatch.setattr(entry, "Path", lambda _path: activation)
    monkeypatch.setattr(entry.time, "time", lambda: 3000)
    monkeypatch.setattr(entry, "read_limits", lambda: pytest.fail("Expired entry reached runtime preflight"))
    monkeypatch.setattr(entry.subprocess, "Popen", lambda *_a, **_k: pytest.fail("Expired worker started"))
    for key, value in {"NC_AI_PROVIDER": "local", "NC_DEPLOY_MODE": "qa", "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_GLOBAL_QUEUE_APPROVED": "false", "NC_WORKER_OWNER_ID": OWNER,
        "NC_QA_STOP_AT": "2800", "NC_QA_TRIAL_ID": TRIAL}.items():
        monkeypatch.setenv(key, value)
    assert entry.main() == 0


def grant():
    return {"nonce": "new-generation", "trial_id": TRIAL, "owner_id": OWNER, "network_verified": True,
            "expires_at_unix": 1120, "stop_at_unix": 2800}


@pytest.mark.parametrize("change", [{"nonce": "old-generation"}, {"expires_at_unix": 1099},
    {"expires_at_unix": 1131}, {"stop_at_unix": 2900}, {"owner_id": policy.OLD_OWNER}, {"network_verified": False}])
def test_restart_never_reuses_a_stale_foreign_or_unverified_grant(change):
    assert entry.grant_valid(grant(), approval(), "new-generation", 1100)
    assert not entry.grant_valid({**grant(), **change}, approval(), "new-generation", 1100)


def counters(cpu, memory, peak):
    return {"cpu.stat": "usage_usec " + str(cpu) + "\nuser_usec 10\nsystem_usec 5",
            "memory.current": str(memory), "memory.peak": str(peak)}


def test_metrics_retain_actual_high_water_marks_and_sum_restart_generations():
    measurements = metrics.Measurements()
    assert measurements.summary()["peak_memory_bytes"] is None
    assert measurements.summary()["total_cpu_seconds"] is None
    assert measurements.add("first", counters(1_000_000, 100, 200), 10, 100)["interval_cpu_percent_one_core_100"] is None
    assert measurements.summary()["sampled_peak_cpu_percent"] is None
    row = measurements.add("first", counters(3_000_000, 150, 400), 12, 102)
    assert row["interval_cpu_percent_one_core_100"] == 100
    measurements.generations["first"]["final_snapshot_captured"] = True
    measurements.add("second", counters(500_000, 50, 300), 14, 104)
    result = measurements.summary()
    assert result["total_cpu_seconds"] == 3.5 and result["peak_memory_bytes"] == 400
    assert result["sampled_peak_cpu_percent"] == 100 and not result["final_snapshots_complete"]
    with pytest.raises(ValueError, match="counter reset"):
        measurements.add("second", counters(1, 20, 200), 16, 106)


def test_real_cgroup_membership_and_counter_files_are_read_without_assuming_parent(tmp_path):
    proc = tmp_path / "proc/22"
    proc.mkdir(parents=True)
    (proc / "cgroup").write_text("0::/custom.slice/docker-example.scope\n")
    root = tmp_path / "cgroup"
    path = root / "custom.slice/docker-example.scope"
    path.mkdir(parents=True)
    for name, value in counters(2_000_000, 22, 44).items():
        (path / name).write_text(value)
    assert metrics.cgroup_path(22, tmp_path / "proc", root) == path
    assert metrics.read_sample(path)["memory.peak"] == "44"
    (proc / "cgroup").write_text("0::/../../unrelated\n")
    with pytest.raises(ValueError):
        metrics.cgroup_path(22, tmp_path / "proc", root)


def test_retained_cgroup_counter_is_not_double_counted_after_restart():
    measurements = metrics.Measurements()
    measurements.add("before", {**counters(3_000_000, 100, 400), "_cgroup_inode": "same"}, 10, 100)
    measurements.add("after", {**counters(4_000_000, 200, 500), "_cgroup_inode": "same"}, 12, 102)
    assert measurements.summary()["total_cpu_seconds"] == 4
    measurements.add("recreated", {**counters(500_000, 150, 300), "_cgroup_inode": "new"}, 14, 104)
    assert measurements.summary()["total_cpu_seconds"] == 4.5


def test_crash_guard_refuses_init_supervisor_foreign_pid_or_global_mode():
    env = {"NC_DEPLOY_MODE": "qa", "NC_AI_PROVIDER": "local", "NC_GLOBAL_QUEUE_APPROVED": "false", "NC_QA_STOP_AT": "2800"}
    health = {"pid": 12, "mode": "qa", "ai_ready": True, "at": 1100}
    command = b"python -c from noetharaclipz.runner import main; main()"
    probe.check_runner(12, health, command, env, 1101)
    for pid, cmd, changed in [(1, command, {}), (13, command, {}), (12, b"python supervisor", {}),
                             (12, command, {"NC_GLOBAL_QUEUE_APPROVED": "true"})]:
        with pytest.raises(ValueError):
            probe.check_runner(pid, health, cmd, {**env, **changed}, 1101)


def test_old_or_foreign_container_never_reaches_a_docker_action():
    for cid, trial in ((platform.OLD_CID, TRIAL), ("new", host.OLD_TRIAL)):
        with pytest.raises(ValueError):
            host.owned({"Id": cid, "Config": {"Labels": {"io.noetharaclipz.trial": trial}}}, plan())


def test_host_controller_refuses_claims_and_heartbeats_even_with_an_api_instance():
    api = platform.API.__new__(platform.API)
    for name in ("worker_claim", "worker_claim_scoped", "worker_heartbeat", "worker_heartbeat_scoped"):
        with pytest.raises(ValueError):
            api.rpc(name)


def test_generated_docker_command_is_new_pinned_scoped_and_has_no_public_ports(tmp_path):
    command = host.create_command(plan(), approval(), tmp_path / "config", tmp_path / "data")
    assert command[:3] == platform.DOCKER + ["create"]
    assert "8g" in command and "on-failure:3" in command and "--cpus" in command
    assert not any(value.startswith(("-p=", "--publish", "--privileged")) for value in command)
    assert "NC_GLOBAL_QUEUE_APPROVED=false" in command and "GEMINI_FREE_TIER_VERIFIED=false" in command
    assert "NC_WORKER_OWNER_ID=" + OWNER in command and "NC_QA_STOP_AT=2800" in command
    assert command[-2:] == [platform.IMAGE, "/run/trial-code/reliability_entry.py"]
    assert platform.OLD_CID not in command and "SUPABASE_SERVICE_ROLE_KEY" not in " ".join(command)


def test_preparation_is_non_starting_idempotent_and_preserves_archive(monkeypatch, tmp_path):
    base, data = tmp_path / "etc", tmp_path / "data"
    monkeypatch.setattr(host, "ETC", base)
    monkeypatch.setattr(host, "DATA", data)
    monkeypatch.setattr(host, "admission", lambda: {"services": [], "firewall_fingerprint": "verified"})
    monkeypatch.setattr(host, "run", lambda *_a, **_k: pytest.fail("Preparation tried to launch a process"))
    monkeypatch.setattr(host, "API", lambda: pytest.fail("Preparation read a credential"))
    def directory(path, **_kwargs):
        path.mkdir(exist_ok=True)
    def once(path, value, **_kwargs):
        with path.open("x") as stream:
            stream.write(value if isinstance(value, str) else json.dumps(value))
    monkeypatch.setattr(host, "mkdir", directory)
    monkeypatch.setattr(host, "write_once", once)
    p = plan()
    code, archive = "# reviewed code\n", '{"old_evidence":true}\n'
    p["code_sha256"] = {"example.py": host.digest(code.encode())}
    p["previous_evidence_sha256"] = {"old.json": host.digest(archive.encode())}
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"plan": p, "code": {"example.py": code}, "previous_evidence": {"old.json": archive}}))
    first = host.prepare(bundle)
    second = host.prepare(bundle)
    assert first["ready_for_approval"] and not first["worker_started"]
    assert first["plan_sha256"] == second["plan_sha256"]
    assert (base / TRIAL / "previous-evidence/old.json").read_text() == archive
    assert not (base / TRIAL / "activation.json").exists()


def test_firewall_verification_never_applies_rules(monkeypatch):
    apply = platform.proposal()["apply_after_approval"]
    rules = []
    for command in apply:
        args = command[3:].copy()
        if args[0] == "-N":
            continue
        if args[0] == "-I":
            del args[2]
        args[0] = "-A"
        rules.append(" ".join(args))
    rules.insert(0, "-A FORWARD -j DOCKER-USER")
    called = []
    def read(command):
        called.append(command)
        assert command[3] in ("-C", "-S")
        return "\n".join(rules)
    monkeypatch.setattr(platform, "run", read)
    assert platform.firewall_fingerprint(verify=True) == platform.firewall_fingerprint()
    assert any(command[3] == "-C" for command in called)


def test_independent_sampler_saves_final_counters_before_acknowledging_exit(monkeypatch, tmp_path):
    sampler = host.Sampler("new-cid", tmp_path, tmp_path)
    events = []
    monkeypatch.setattr(host, "inspect", lambda _cid: {})
    monkeypatch.setattr(host, "container_state_file", lambda *_args: {"phase": "finalizing", "nonce": "new-nonce"})
    monkeypatch.setattr(sampler, "sample", lambda final=False: events.append(("saved", final)))
    def acknowledge(_path, value, **_kwargs):
        events.append(("ack", value["nonce"]))
        sampler.stop.set()
    monkeypatch.setattr(host, "atomic", acknowledge)
    sampler.loop()
    assert events == [("saved", True), ("ack", "new-nonce")]


@pytest.mark.parametrize("reason", ["deadline", "gate_revoked"])
def test_real_harmless_child_stops_on_deadline_or_revocation_without_a_worker(monkeypatch, tmp_path, reason):
    nonce = "test-nonce"
    started = time.time()
    activation = {**approval(), "approved_at_unix": started - 1,
                  "stop_at_unix": started + (99 if reason == "deadline" else 1700)}
    activation_path = tmp_path / "activation.json"
    activation_path.write_text(json.dumps(activation))
    gate_path = tmp_path / "grant.json"
    gate_path.write_text(json.dumps({**grant(), "nonce": nonce, "expires_at_unix": started + 25,
                                    "stop_at_unix": activation["stop_at_unix"]}))
    (tmp_path / "finalized.json").write_text(json.dumps({"nonce": nonce}))
    monkeypatch.setattr(entry, "Path", lambda _path: activation_path)
    monkeypatch.setattr(entry, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(entry, "GATE", tmp_path)
    monkeypatch.setattr(entry, "uuid4", lambda: nonce)
    monkeypatch.setattr(entry, "read_limits", lambda: {})
    monkeypatch.setattr(entry, "evaluate", lambda _limits: {"passed": True})
    for key, value in {"NC_AI_PROVIDER": "local", "NC_DEPLOY_MODE": "qa", "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_GLOBAL_QUEUE_APPROVED": "false", "NC_WORKER_OWNER_ID": OWNER,
        "NC_QA_STOP_AT": str(activation["stop_at_unix"]), "NC_QA_TRIAL_ID": TRIAL}.items():
        monkeypatch.setenv(key, value)
    real_popen = subprocess.Popen
    children = []
    def harmless(command, **kwargs):
        assert command[-1] == "noetharaclipz_deploy.supervisor" and kwargs["start_new_session"]
        child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(entry.subprocess, "Popen", harmless)
    # No signal handlers on the pytest process need to change for this check.
    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    timer = None
    if reason == "gate_revoked":
        timer = threading.Timer(0.3, gate_path.unlink)
        timer.start()
    try:
        assert entry.main() == (0 if reason == "deadline" else 1)
        assert children[0].poll() is not None
        state = json.loads((tmp_path / "state.json").read_text())
        assert state["phase"] == "finalizing"
        assert state["reason"] == ("deadline" if reason == "deadline" else "network_grant_revoked_or_stale")
    finally:
        if timer:
            timer.cancel()


@pytest.mark.parametrize("status,body,expected", [
    (400, {"code": "P0001", "message": "Worker lease expired"}, True),
    (400, {"code": "P0001", "message": "Job already finished"}, True),
    (500, {"code": "internal", "message": "unavailable"}, False),
    (403, {"code": "42501", "message": "permission denied"}, False),
])
def test_unrelated_http_failure_is_not_misreported_as_stale_lease_rejection(status, body, expected):
    error = urllib.error.HTTPError("https://example.invalid", status, "test", {}, io.BytesIO(json.dumps(body).encode()))
    assert host.expected_stale_rejection(error) is expected
