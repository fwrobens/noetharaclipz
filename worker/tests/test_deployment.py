"""Deployment safety/readiness guards. Never invoke a real worker or database."""

import json
import os
import sys
from dataclasses import replace
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "deploy/worker"))
from noetharaclipz_deploy.supervisor import gate, cleanup_temp
from noetharaclipz_deploy.healthcheck import healthy
from noetharaclipz.config import Settings
from noetharaclipz.runner import Worker
from noetharaclipz.local_provider import available_memory


def test_deployment_defaults_to_standby_without_secret_or_owner():
    assert gate({"NC_AI_PROVIDER": "local"}) == "standby"


@pytest.mark.parametrize(
    "env",
    [
        {"NC_DEPLOY_MODE": "qa"},
        {"NC_DEPLOY_MODE": "global"},
        {"NC_DEPLOY_MODE": "qa", "NC_WORKER_OWNER_ID": "bad"},
        {
            "NC_DEPLOY_MODE": "global",
            "NC_GLOBAL_QUEUE_APPROVED": "true",
            "NC_WORKER_OWNER_ID": "some-user",
        },
        {"NC_AI_PROVIDER": "gemini"},
        {"GEMINI_FREE_TIER_VERIFIED": "true"},
    ],
)
def test_unsafe_deployment_modes_rejected(env):
    with pytest.raises(ValueError):
        gate({"NC_AI_PROVIDER": "local", **env})


def test_scoped_mode_requires_actual_uuid():
    assert (
        gate(
            {
                "NC_AI_PROVIDER": "local",
                "NC_DEPLOY_MODE": "qa",
                "NC_WORKER_OWNER_ID": "84d8ae5f-a46d-4c67-82a3-98d80a881507",
            }
        )
        == "qa"
    )


def test_health_is_stale_or_unready_until_real_selected_provider_ready():
    assert healthy({"at": 100, "mode": "standby", "ai_ready": False}, now=101)
    assert not healthy({"at": 100, "mode": "qa", "ai_ready": False}, now=101)
    assert not healthy({"at": 100, "mode": "qa", "ai_ready": True, "main_age_seconds": 0}, now=200)
    assert not healthy(
        {"at": 100, "mode": "qa", "ai_ready": True, "main_age_seconds": 1400}, now=101
    )
    assert healthy({"at": 100, "mode": "qa", "ai_ready": True, "main_age_seconds": 0}, now=101)


def test_probe_written_only_after_successful_db_heartbeat(monkeypatch, tmp_path):
    target = tmp_path / "health.json"
    monkeypatch.setenv("NC_HEALTH_FILE", str(target))

    class Backend:
        fail = True

        def rpc(self, *args, **kwargs):
            if self.fail:
                raise RuntimeError("offline")
            return None

    b = Backend()
    w = Worker(
        replace(Settings(), scope_owner="84d8ae5f-a46d-4c67-82a3-98d80a881507"),
        backend=b,
        provider=object(),
    )
    with pytest.raises(RuntimeError):
        w.heartbeat(True, "Ready")
    assert not target.exists()
    b.fail = False
    w.heartbeat(True, "Ready")
    state = json.loads(target.read_text())
    assert state["ai_ready"] and state["mode"] == "qa" and "Ready" not in target.read_text()
    assert target.stat().st_mode & 0o077 == 0


def test_temp_cleanup_never_follows_symlinks_or_removes_active_dirs(tmp_path):
    old = tmp_path / "noetharaclipz-old"
    old.mkdir()
    os.utime(old, (1, 1))
    current = tmp_path / "noetharaclipz-active"
    current.mkdir()
    unrelated = tmp_path / "existing-service"
    unrelated.mkdir()
    os.utime(unrelated, (1, 1))
    link = tmp_path / "noetharaclipz-link"
    link.symlink_to(unrelated, target_is_directory=True)
    cleanup_temp(tmp_path)
    assert not old.exists() and current.exists() and unrelated.exists() and link.is_symlink()


@pytest.mark.parametrize("version", [1, 2])
def test_available_memory_respects_container_limit_and_reclaimable_host_ram(monkeypatch, version):
    gib = 1024**3
    files = {"/proc/meminfo": "MemAvailable: 12582912 kB\n"}
    if version == 2:
        files.update(
            {
                "/sys/fs/cgroup/memory.max": str(8 * gib),
                "/sys/fs/cgroup/memory.current": str(3 * gib),
            }
        )
    else:
        files.update(
            {
                "/sys/fs/cgroup/memory/memory.limit_in_bytes": str(8 * gib),
                "/sys/fs/cgroup/memory/memory.usage_in_bytes": str(3 * gib),
            }
        )

    def read(path, **kwargs):
        if str(path) not in files:
            raise OSError("Unavailable")
        return files[str(path)]

    monkeypatch.setattr(Path, "read_text", read)
    assert available_memory() == 5 * gib


def test_unready_worker_watchdog_stops_child_and_exits_for_restart(monkeypatch, tmp_path):
    from noetharaclipz_deploy import supervisor

    secret = tmp_path / "test-key"
    secret.write_text("sb_secret_" + "contract_only_" * 3)
    health = tmp_path / "health.json"
    for key, value in {
        "NC_DEPLOY_MODE": "qa",
        "NC_AI_PROVIDER": "local",
        "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_WORKER_OWNER_ID": "84d8ae5f-a46d-4c67-82a3-98d80a881507",
        "NC_SUPABASE_KEY_FILE": str(secret),
        "NC_HEALTH_FILE": str(health),
        "TMPDIR": str(tmp_path),
    }.items():
        monkeypatch.setenv(key, value)

    class Stop:
        def set(self):
            pass

        def is_set(self):
            return False

        def wait(self, seconds):
            return False

    class Child:
        pid = 12345
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.stopped = True

        def wait(self, timeout=None):
            return 0

    child = Child()

    def launch(args, env):
        assert "SUPABASE_SECRET_KEY" in env and "GEMINI_API_KEY" not in env
        assert "SUPABASE_SERVICE_ROLE_KEY" not in env
        return child

    clock = iter([0, 300])
    monkeypatch.setattr(supervisor.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(supervisor.threading, "Event", Stop)
    monkeypatch.setattr(supervisor.signal, "signal", lambda *args: None)
    monkeypatch.setattr(supervisor.subprocess, "Popen", launch)
    assert supervisor.main() == 1
    assert child.stopped and json.loads(health.read_text())["ai_ready"] is False
