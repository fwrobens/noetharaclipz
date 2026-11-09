"""Controller/transport tests use inert doubles and harmless subprocesses only."""

import json
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/worker"))
import continuous_entry as entry  # noqa: E402
import continuous_host as host  # noqa: E402
import continuous_policy as policy  # noqa: E402
from continuous_metrics import DurableMetrics  # noqa: E402
from noetharaclipz.config import Settings  # noqa: E402
from noetharaclipz.consent import ConsentedBackend, ProcessingRevoked  # noqa: E402
from noetharaclipz.runner import Worker, Lease  # noqa: E402

OWNER = "10000000-0000-0000-0000-000000000001"
CONSENT = "40000000-0000-0000-0000-000000000001"
DEPLOY = "50000000-0000-0000-0000-000000000001"
PROJECT = "20000000-0000-0000-0000-000000000001"
JOB = "30000000-0000-0000-0000-000000000001"
TOKEN = "60000000-0000-0000-0000-000000000001"


def manifest(now=100):
    return {
        "schema": 1,
        "deployment_id": DEPLOY,
        "owner_id": OWNER,
        "consent_id": CONSENT,
        "image": policy.IMAGE,
        "model": policy.MODEL,
        "memory_bytes": 8 * 1024**3,
        "cpus": 2,
        "active_jobs": 1,
        "global_processing": False,
        "gemini_enabled": False,
        "operator_approved": True,
        "approval_reference": "Explicit unit fixture; never a deployment approval",
        "not_before": now - 1,
        "valid_until": now + 3600,
        "files": {name: "a" * 64 for name in policy.REQUIRED_CODE},
        "unit_sha256": {
            "noetharaclipz-isolation.service": "a" * 64,
            "noetharaclipz-continuous.service": "b" * 64,
        },
        "restore_isolation": True,
    }


def job():
    return {
        "id": JOB,
        "project_id": PROJECT,
        "owner_id": OWNER,
        "consent_id": CONSENT,
        "kind": "analysis",
        "attempts": 1,
        "lease_token": TOKEN,
        "source_identity": {
            "id": "video-fixture",
            "source_path": OWNER + "/" + PROJECT + "/source.mp4",
            "byte_size": 12,
        },
    }


def settings():
    return Settings(
        provider="local",
        scope_owner=OWNER,
        queue_mode="consented",
        consent_id=CONSENT,
        free_verified=False,
        service_key="sb_secret_" + "unit-fixture" * 4,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"operator_approved": False},
        {"operator_approved": "false"},
        {"cpus": 3},
        {"memory_bytes": 16 * 1024**3},
        {"active_jobs": 2},
        {"global_processing": True},
        {"gemini_enabled": True},
        {"owner_id": next(iter(policy.ARCHIVED_OWNERS))},
        {"valid_until": 99},
        {"valid_until": 100 + 8 * 86400},
    ],
)
def test_manifest_cannot_expand_scope_or_reuse_archived_trials(change):
    with pytest.raises(ValueError):
        policy.validate_manifest({**manifest(), **change}, 100)


@pytest.mark.parametrize(
    "change",
    [
        {"queue_mode": "unknown"},
        {"consent_id": None},
        {"provider": "gemini"},
        {"scope_owner": None},
        {"free_verified": True},
    ],
)
def test_missing_explicit_consent_configuration_never_uses_legacy(change):
    with pytest.raises(ValueError):
        replace(settings(), **change)


def transport_backend(handler):
    return ConsentedBackend(settings(), httpx.Client(transport=httpx.MockTransport(handler)))


def test_worker_consumes_only_v2_owner_and_consent_bound_claims():
    calls = []

    def handle(request):
        name = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content)
        calls.append((name, body))
        if name == "worker_continuous_protocol":
            return httpx.Response(
                200,
                json={
                    "version": 2,
                    "contract": "future-jobs-only-v1",
                    "global_claim": False,
                    **{
                        k: True
                        for k in ("future_jobs_only", "revocable", "job_exclusions", "audit")
                    },
                },
            )
        assert body.get("owner") == OWNER and body.get("consent") == CONSENT
        return httpx.Response(
            200, json={"authorized": True} if name == "worker_consent_status" else None
        )

    worker = Worker(settings(), backend=transport_backend(handle), provider=object())
    assert worker.once() is False
    assert [c[0] for c in calls] == [
        "worker_continuous_protocol",
        "worker_consent_status",
        "worker_claim_optin",
    ]


def test_missing_server_protocol_never_falls_back_or_loads_a_provider():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"version": 1})

    worker = Worker(settings(), backend=transport_backend(handle), provider=object())
    with pytest.raises(RuntimeError, match="no legacy queue fallback"):
        worker.once()
    assert len(calls) == 1 and calls[0].endswith("/worker_continuous_protocol")


@pytest.mark.parametrize(
    "change",
    [
        {"owner_id": "foreign"},
        {"consent_id": "foreign"},
        {"id": "9c5c8869-ec2e-4a3e-927d-697615bb58a3"},
        {"attempts": 4},
    ],
)
def test_invalid_claim_is_refused_before_reading_media(change):
    backend = transport_backend(lambda _request: httpx.Response(200, json={**job(), **change}))
    with pytest.raises(ValueError):
        backend.rpc("worker_claim_optin")
    assert backend.job is None


def test_revocation_during_lease_does_not_mark_job_failed_or_fall_back():
    calls = []

    def handle(request):
        calls.append(request.url.path.rsplit("/", 1)[-1])
        if calls[-1] == "worker_claim_optin":
            return httpx.Response(200, json=job())
        return httpx.Response(403, json={"code": "42501", "message": "Revoked"})

    backend = transport_backend(handle)
    leased = backend.rpc("worker_claim_optin")
    lease = Lease(backend, leased)
    with pytest.raises(ProcessingRevoked):
        lease.tick(True)
    assert calls == ["worker_claim_optin", "worker_tick_optin"]


def test_worker_stops_after_revocation_and_leaves_lease_for_natural_recovery(monkeypatch):
    backend = transport_backend(lambda request: httpx.Response(200, json=job()))
    worker = Worker(settings(), backend=backend, provider=object())
    worker.protocol_checked = True
    monkeypatch.setattr(
        worker, "process", lambda _job: (_ for _ in ()).throw(ProcessingRevoked("fixture"))
    )
    assert worker.once() is True and worker.stop_event.is_set()


@pytest.mark.parametrize(
    "operation", ["worker_claim", "worker_claim_scoped", "worker_protocol", "reserve_inference"]
)
def test_consent_transport_rejects_legacy_global_or_paid_paths(operation):
    backend = transport_backend(lambda _request: pytest.fail("Forbidden request sent"))
    with pytest.raises(ValueError):
        backend.rpc(operation)


def test_checkpoint_and_storage_cannot_bypass_revocation_or_ownership(tmp_path):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=job())

    backend = transport_backend(handle)
    backend.rpc("worker_claim_optin")
    for path in ["foreign/" + PROJECT + "/clip.mp4", OWNER + "/" + PROJECT + "/../outside.mp4"]:
        with pytest.raises(ValueError):
            backend.upload("rendered-clips", path, tmp_path / "anything", "video/mp4")
    with pytest.raises(ValueError):
        backend.update("videos", {})
    with pytest.raises(ValueError):
        backend.cleanup()
    with pytest.raises(ValueError):
        backend.rows("projects", id="eq.foreign")
    assert len(calls) == 1


def test_normal_local_analysis_path_uses_transactional_consent_checkpoints_only(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    calls = []
    leased = job()
    source = leased["source_identity"]

    def handle(request):
        path = request.url.path
        calls.append((request.method, path))
        if "/rpc/" in path:
            operation = path.rsplit("/", 1)[-1]
            body = json.loads(request.content)
            assert body.get("owner") == OWNER and body.get("consent") == CONSENT
            return httpx.Response(200, json=leased if operation == "worker_claim_optin" else True)
        if "/storage/" in path:
            return httpx.Response(200, content=b"x" * 12 if request.method == "GET" else b"{}")
        assert request.method == "GET", "Raw checkpoint/table writes must never occur"
        if path.endswith("/videos"):
            return httpx.Response(200, json=[source])
        if path.endswith("/projects"):
            return httpx.Response(
                200,
                json=[
                    {"id": PROJECT, "owner_id": OWNER, "instructions": "Transport contract fixture"}
                ],
            )
        return httpx.Response(200, json=[])

    class Provider:
        name = "local-smolvlm2"
        model = policy.MODEL + "@7b375e1b73b11138ff12fe22c8f2822d8fe03467"
        metrics = {}

        def prepare(self, _source, _tick):
            proxy = tmp_path / "proxy"
            proxy.write_bytes(b"fixture")
            thumb = tmp_path / "thumb"
            thumb.write_bytes(b"fixture")
            return {
                "proxy": proxy,
                "thumbnail": thumb,
                "frames": [],
                "metadata": {
                    "duration": 4,
                    "width": 160,
                    "height": 90,
                    "fps": 10,
                    "has_audio": False,
                },
                "source_hash": "a" * 64,
                "scenes": [],
                "audio_events": [],
                "waveform": [],
            }

        def transcript(self, _data, _tick):
            return []

        def preflight(self):
            pass

        def analyze(self, *_args):
            path = tmp_path / "analysis.json"
            path.write_text("{}")
            return (
                SimpleNamespace(summary="Transport fixture only", highlights=[]),
                {
                    "execution_usage": {"input_tokens": 1, "output_tokens": 0},
                    "visual_observation_warning": "Not actual inference",
                },
                path,
            )

    backend = transport_backend(handle)
    leased = backend.rpc("worker_claim_optin")
    Worker(settings(), backend=backend, provider=Provider()).process(leased)
    rpc = [p.rsplit("/", 1)[-1] for method, p in calls if "/rpc/" in p]
    assert (
        rpc.count("worker_checkpoint_optin") == 2 and rpc.count("worker_finish_analysis_optin") == 1
    )
    assert "worker_finish_analysis" not in rpc and "worker_tick" not in rpc


def test_temporary_cleanup_never_follows_symlinks_or_removes_active_dirs(tmp_path, monkeypatch):
    import os

    root = tmp_path / "tmp"
    root.mkdir()
    stale = root / "noetharaclipz-stale"
    stale.mkdir()
    real_lstat = Path.lstat

    def lstat(path):
        value = real_lstat(path)
        if path.parent == root and path.name.startswith("noetharaclipz-"):
            fields = list(value)
            fields[4] = 62001
            return os.stat_result(fields)
        return value

    monkeypatch.setattr(Path, "lstat", lstat)
    os.utime(stale, (1, 1))
    active = root / "noetharaclipz-active"
    active.mkdir()
    os.utime(active, (99999, 99999))
    other = tmp_path / "existing-service"
    other.mkdir()
    (root / "noetharaclipz-symlink").symlink_to(other, target_is_directory=True)
    p = host.Platform.__new__(host.Platform)
    p.data = tmp_path
    p.cleanup_temp(now=100000)
    assert not stale.exists() and active.exists() and other.exists()


def test_security_failure_blocks_controller_without_retry_or_worker_restart(monkeypatch, tmp_path):
    events = []

    class P:
        data = tmp_path

        def run_generation(self, _stop):
            events.append("preflight")
            raise ValueError("Firewall failed")

        def stop_owned(self):
            events.append("revoke_and_stop_owned")

        def status(self, stage, **_kw):
            events.append(stage)

    monkeypatch.setattr(host, "atomic", lambda p, v: p.write_text(json.dumps(v)))
    assert host.Controller(P(), clock=lambda: 100).run(threading.Event()) == 0
    assert events == ["preflight", "revoke_and_stop_owned", "blocked_security_or_consent"]
    assert (tmp_path / "blocked.json").exists()


def test_crash_backoff_and_budget_survive_controller_restart(monkeypatch, tmp_path):
    current = [100]
    waits = []
    starts = []

    class Stop:
        def is_set(self):
            return False

        def wait(self, n):
            waits.append(n)
            current[0] += n
            return False

    class P:
        data = tmp_path

        def run_generation(self, _stop):
            starts.append(current[0])
            raise RuntimeError("Worker exited")

        def stop_owned(self):
            pass

        def status(self, *_a, **_kw):
            pass

    monkeypatch.setattr(host, "atomic", lambda p, v: p.write_text(json.dumps(v)))
    p = P()
    assert host.Controller(p, clock=lambda: current[0]).run(Stop()) == 0
    assert starts == [100, 105, 120] and waits == [5, 15, 45]
    assert host.Controller(p, clock=lambda: current[0]).run(Stop()) == 0
    assert len(starts) == 3


def test_network_admission_failure_precedes_credentials_or_any_container(monkeypatch, tmp_path):
    p = host.Platform.__new__(host.Platform)
    p.path = tmp_path / "manifest"
    p.m = manifest()
    p.data = tmp_path
    monkeypatch.setattr(host, "load", lambda _path: (p.m, tmp_path, tmp_path))
    monkeypatch.setattr(
        host, "verify_network", lambda: (_ for _ in ()).throw(ValueError("Wrong bridge"))
    )
    monkeypatch.setattr(host, "API", lambda: pytest.fail("Credential read before network security"))
    monkeypatch.setattr(
        host, "docker", lambda *_a, **_k: pytest.fail("Docker mutation before network admission")
    )
    with pytest.raises(ValueError, match="Wrong bridge"):
        p.preflight()


def test_generation_orders_security_before_grant_and_always_stops_only_owned(monkeypatch, tmp_path):
    from types import SimpleNamespace

    events = []

    class Stop:
        done = False

        def wait(self, _seconds):
            return self.done

    stop = Stop()
    p = host.Platform.__new__(host.Platform)
    p.path = tmp_path / "manifest"
    p.m = manifest(time.time())
    p.cfg = tmp_path
    p.data = tmp_path
    p.reports = tmp_path
    p.cid = "owned"
    p.baseline = []
    p.fingerprint = "ok"
    p.sampler_stop = threading.Event()
    p.sampling_fault = threading.Event()
    p.last_sample = 0
    p.metrics = SimpleNamespace(summary=lambda: {})
    p.sampling = lambda: None
    p.stop_owned = lambda: events.append("stop_owned")
    p.preflight = lambda: events.append("docker_volumes_firewall_consent")
    p.protected = lambda: events.append("protected_row")
    p.cleanup_temp = lambda: None
    p.ensure_container = lambda: events.append("create_gated_container")
    p.consent = lambda: events.append("consent_recheck")

    def sample():
        events.append("kernel_metrics")
        p.last_sample = time.monotonic()

    p.sample = sample
    p.prove = lambda: (events.append("live_security_proof") or {"passed": True})

    def status(*_args, **_kwargs):
        stop.done = True

    p.status = status
    monkeypatch.setattr(host, "load", lambda _path: (p.m, tmp_path, tmp_path))
    monkeypatch.setattr(host, "service_snapshot", lambda **_kw: [])
    monkeypatch.setattr(host, "firewall_fingerprint", lambda: "ok")
    monkeypatch.setattr(host, "available_ram", lambda: 30 * 1024**3)
    monkeypatch.setattr(host.shutil, "disk_usage", lambda _path: SimpleNamespace(free=30 * 1024**3))
    monkeypatch.setattr(
        host,
        "inspect",
        lambda _cid: {"Id": "owned", "State": {"Running": True, "StartedAt": "generation"}},
    )
    monkeypatch.setattr(host, "owned", lambda info, _m: None)
    monkeypatch.setattr(
        host,
        "container_state_file",
        lambda _info, name: {"nonce": "fresh", "phase": "awaiting_grant"}
        if name == "continuous-state.json"
        else {"ai_ready": True, "at": time.time()},
    )
    monkeypatch.setattr(
        host,
        "docker",
        lambda *args: events.append("start_gated_container")
        if args == ("start", "owned")
        else pytest.fail("Unexpected mutation"),
    )
    monkeypatch.setattr(
        host,
        "atomic",
        lambda path, _value, **_kw: events.append("grant") if path.name == "grant.json" else None,
    )
    assert p.run_generation(stop) == "operator_stop"
    assert (
        events.index("docker_volumes_firewall_consent")
        < events.index("create_gated_container")
        < events.index("start_gated_container")
    )
    assert (
        events.index("kernel_metrics") < events.index("live_security_proof") < events.index("grant")
    )
    assert events[-1] == "stop_owned"


def test_docker_profile_has_no_auto_restart_or_public_ports_and_pins_scoped_code(tmp_path):
    command = host.create_command(manifest(), tmp_path / "cfg", tmp_path / "data")
    assert command[command.index("--restart") + 1] == "no"
    assert "--publish" not in command and "--privileged" not in command
    assert "NC_QUEUE_MODE=consented" in command and "NC_GLOBAL_QUEUE_APPROVED=false" in command
    assert "--cpus" in command and "8g" in command and "--pids-limit" in command
    assert command[-2:] == [policy.IMAGE, "/run/continuous/code/host/continuous_entry.py"]
    assert any("/app/worker,readonly" in x for x in command)


def test_isolation_restoration_never_flushes_or_changes_shared_policies(monkeypatch):
    m = manifest(time.time())
    commands = host.proposal()["apply_after_approval"]
    lines = ["-A FORWARD -j DOCKER-USER"]
    mutations = []
    monkeypatch.setattr(host, "verify_network", lambda: None)
    monkeypatch.setattr(host, "firewall_fingerprint", lambda **_kw: "ok")

    def run(command):
        if command[3] == "-S":
            return "\n".join(lines)
        mutations.append(command)
        assert command[3] in ("-N", "-A", "-I")
        assert command[4] in ("NCZQA_EGRESS", "INPUT", "DOCKER-USER")
        if command[4] != "NCZQA_EGRESS":
            assert "nccz-qa0" in command
        return ""

    monkeypatch.setattr(host, "run", run)
    host.restore_isolation(m)
    assert mutations == commands


def test_foreign_firewall_chain_causes_no_write(monkeypatch):
    monkeypatch.setattr(host, "verify_network", lambda: None)
    calls = []

    def run(command):
        calls.append(command)
        assert command[3] == "-S"
        return "-A FORWARD -j DOCKER-USER\n-A NCZQA_EGRESS -j ACCEPT"

    monkeypatch.setattr(host, "run", run)
    with pytest.raises(ValueError, match="Foreign"):
        host.restore_isolation(manifest(time.time()))
    assert len(calls) == 1


def test_existing_canonical_iptables_policy_is_idempotent_without_mutation(monkeypatch):
    commands = host.proposal()["apply_after_approval"]
    lines = ["-A FORWARD -j DOCKER-USER", "-N NCZQA_EGRESS"]
    for command in commands:
        fields = command[3:].copy()
        if fields[0] == "-N":
            continue
        if fields[0] == "-I":
            fields[0] = "-A"
            del fields[2]
        if "-p" in fields:
            index = fields.index("-p") + 2
            fields[index:index] = ["-m", fields[index - 1]]
        if "--ctstate" in fields:
            fields[fields.index("--ctstate") + 1] = "RELATED,ESTABLISHED"
        lines.append(" ".join(fields))
    monkeypatch.setattr(host, "verify_network", lambda: None)
    monkeypatch.setattr(host, "firewall_fingerprint", lambda **_kw: "ok")

    def run(command):
        assert command[3] == "-S", "Already-correct worker rules must not be changed"
        return "\n".join(lines)

    monkeypatch.setattr(host, "run", run)
    host.restore_isolation(manifest(time.time()))


def test_durable_metrics_keep_peaks_and_counters_across_controller_restarts(monkeypatch, tmp_path):
    import continuous_metrics

    monkeypatch.setattr(continuous_metrics, "atomic", lambda p, v: p.write_text(json.dumps(v)))

    def values(cpu, peak, inode):
        return {
            "cpu.stat": "usage_usec " + str(cpu),
            "memory.current": "12",
            "memory.peak": str(peak),
            "_cgroup_inode": inode,
        }

    first = DurableMetrics(tmp_path)
    first.add("old", values(1_000_000, 500, "one"), 1, 100, final=True)
    second = DurableMetrics(tmp_path)
    second.add("new", values(2_000_000, 400, "two"), 2, 101, final=True)
    assert (
        second.summary()["peak_memory_bytes"] == 500 and second.summary()["total_cpu_seconds"] == 3
    )
    assert second.summary()["final_snapshots_complete"]
    for i in range(70):
        second.add(str(i), values(1, 10, str(i)), 3 + i, 102 + i, final=True)
    summary = second.summary()
    assert len(summary["generations"]) == 64 and len(summary["cpu_counter_domains"]) <= 64
    assert summary["total_cpu_seconds"] == 3.000070


def test_grants_cannot_cross_owner_generation_manifest_or_expiry():
    m = manifest()
    grant = {
        "nonce": "new",
        "deployment_id": DEPLOY,
        "owner_id": OWNER,
        "consent_id": CONSENT,
        "manifest_sha256": policy.manifest_hash(m),
        "security_verified": True,
        "expires_at": 120,
    }
    assert policy.grant_valid(grant, m, "new", 100)
    for changed in (
        {"nonce": "old"},
        {"owner_id": "foreign"},
        {"manifest_sha256": "changed"},
        {"expires_at": 99},
        {"expires_at": 130},
    ):
        assert not policy.grant_valid({**grant, **changed}, m, "new", 100)


def test_disabled_manifest_template_is_not_a_deployment_approval():
    root = Path(__file__).resolve().parents[2]
    example = json.loads((root / "deploy/worker/continuous-manifest.example.json").read_text())
    with pytest.raises(ValueError):
        policy.validate_manifest(example, time.time())


def test_entry_with_no_grant_never_reads_credential_or_spawns_worker(monkeypatch, tmp_path):
    m = manifest(time.time())
    monkeypatch.setattr(entry, "read", lambda p: m if str(p).endswith("manifest.json") else {})
    monkeypatch.setattr(entry, "state", lambda _value: None)
    monkeypatch.setattr(entry, "evaluate", lambda _v: {"passed": True})
    monkeypatch.setattr(entry, "read_limits", lambda: {})
    monkeypatch.setattr(
        entry.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("Spawned without grant")
    )
    for k, v in {
        "NC_QUEUE_MODE": "consented",
        "NC_AI_PROVIDER": "local",
        "NC_DEPLOY_MODE": "continuous",
        "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_GLOBAL_QUEUE_APPROVED": "false",
        "NC_WORKER_OWNER_ID": OWNER,
        "NC_OWNER_CONSENT_ID": CONSENT,
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(entry.signal, "signal", lambda *_a: None)
    # Expired monotonic wait budget, avoiding real sleeps or credential access.
    times = iter([0, 100])
    monkeypatch.setattr(entry.time, "monotonic", lambda: next(times))
    assert entry.main() == 0


def test_grant_revocation_stops_a_real_harmless_process_group_without_a_worker(
    monkeypatch, tmp_path
):
    m = manifest(time.time())
    nonce = "fresh"
    allowed = threading.Event()
    allowed.set()
    grant = {
        "nonce": nonce,
        "deployment_id": DEPLOY,
        "owner_id": OWNER,
        "consent_id": CONSENT,
        "manifest_sha256": policy.manifest_hash(m),
        "security_verified": True,
        "expires_at": time.time() + 20,
    }

    def read(path):
        if str(path).endswith("manifest.json"):
            return m
        if str(path).endswith("finalized.json"):
            return {"nonce": nonce}
        return grant if allowed.is_set() else {}

    monkeypatch.setattr(entry, "read", read)
    monkeypatch.setattr(entry, "uuid4", lambda: nonce)
    states = []
    monkeypatch.setattr(entry, "state", lambda value: states.append(dict(value)))
    monkeypatch.setattr(entry, "evaluate", lambda _limits: {"passed": True})
    monkeypatch.setattr(entry, "read_limits", lambda: {})
    monkeypatch.setattr(entry.signal, "signal", lambda *_args: None)
    key = tmp_path / "dummy-key"
    key.write_text("unit fixture only")
    monkeypatch.setattr(entry, "Path", lambda _path: key)
    for k, v in {
        "NC_QUEUE_MODE": "consented",
        "NC_AI_PROVIDER": "local",
        "NC_DEPLOY_MODE": "continuous",
        "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_GLOBAL_QUEUE_APPROVED": "false",
        "NC_WORKER_OWNER_ID": OWNER,
        "NC_OWNER_CONSENT_ID": CONSENT,
    }.items():
        monkeypatch.setenv(k, v)
    real_popen = subprocess.Popen
    children = []

    def harmless(command, **kwargs):
        assert "noetharaclipz.runner" in command[-1] and kwargs["start_new_session"]
        child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(entry.subprocess, "Popen", harmless)
    timer = threading.Timer(0.3, allowed.clear)
    timer.start()
    try:
        assert entry.main() == 0
        assert children[0].poll() is not None
        assert (
            states[-1]["phase"] == "finalizing" and states[-1]["reason"] == "grant_revoked_or_stale"
        )
    finally:
        timer.cancel()
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait()
