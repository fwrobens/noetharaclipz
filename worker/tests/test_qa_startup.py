"""QA startup boundaries: real Compose parsing/cryptography, no worker/network."""
# ruff: noqa: E402

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy/worker"))
import credential_envelope as envelope
import qa_deadline as deadline
import start_qa_worker as startup

OWNER = "84d8ae5f-a46d-4c67-82a3-98d80a881507"
TRIAL = "9563aeb9-2620-4e05-acf2-1e69ce18b819"


def environment(stop=2000):
    return {"NC_AI_PROVIDER": "local", "NC_DEPLOY_MODE": "qa", "GEMINI_FREE_TIER_VERIFIED": "false",
            "NC_GLOBAL_QUEUE_APPROVED": "false", "NC_WORKER_OWNER_ID": OWNER,
            "NC_QA_TRIAL_ID": TRIAL, "NC_QA_STOP_AT": str(stop)}


@pytest.mark.parametrize("change", [{"NC_AI_PROVIDER": "gemini"}, {"GEMINI_FREE_TIER_VERIFIED": "true"},
    {"NC_GLOBAL_QUEUE_APPROVED": "true"}, {"NC_WORKER_OWNER_ID": ""}, {"NC_DEPLOY_MODE": "global"},
    {"NC_QA_TRIAL_ID": ""}, {"NC_QA_STOP_AT": "invalid"}])
def test_qa_cannot_start_without_explicit_safe_scope_and_fixed_deadline(change):
    with pytest.raises(ValueError):
        deadline.remaining_window({**environment(), **change}, 1000)


def test_restart_cannot_reset_or_extend_the_window():
    env = environment()
    assert deadline.remaining_window(env, 1000) == 1000
    assert deadline.remaining_window(env, 1500) == 500
    assert deadline.remaining_window(env, 2001) == 0
    with pytest.raises(ValueError, match="30-minute"):
        deadline.remaining_window(environment(3000), 1000)


def test_expired_container_exits_normally_before_importing_models_or_credentials():
    result = subprocess.run([sys.executable, str(ROOT / "deploy/worker/qa_deadline.py")],
                            env={**os.environ, **environment(1)}, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"qa_window_expired": True, "worker_started": False}


def test_real_process_group_is_stopped_at_fixed_deadline(monkeypatch, tmp_path):
    quota = tmp_path / "limits.py"
    quota.write_text("def read_limits(): return {}\ndef evaluate(x): return {'passed':True}\n")
    real_spec = importlib.util.spec_from_file_location
    monkeypatch.setattr(deadline.importlib.util, "spec_from_file_location", lambda name, path: real_spec(name, quota))
    monkeypatch.setattr(deadline, "GRACE_SECONDS", 0)
    for key, value in environment(int(time.time()) + 8).items():
        monkeypatch.setenv(key, value)
    real_popen = subprocess.Popen
    children = []

    def harmless_child(command, **kwargs):
        assert command[-1] == "noetharaclipz_deploy.supervisor" and kwargs["start_new_session"]
        child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(deadline.subprocess, "Popen", harmless_child)
    began = time.monotonic()
    assert deadline.main() == 0
    assert time.monotonic() - began < 6 and children[0].poll() is not None


def test_real_oaep_round_trip_is_bound_to_one_host_project_image_and_qa_owner(monkeypatch, tmp_path, capsys):
    private = tmp_path / "transport.key"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:4096",
                    "-out", str(private)], check=True, capture_output=True, timeout=30)
    private.chmod(0o600)
    public = subprocess.check_output(["openssl", "pkey", "-in", str(private), "-pubout"])
    secret = b"test-only-existing-server-credential"
    sealed = envelope.seal(public, secret, OWNER, TRIAL)
    assert secret.decode() not in json.dumps(sealed)
    # Simulate ONLY root ownership on this non-root test runner. Real OpenSSL
    # encryption/decryption, modes, symlinks and context checks remain intact.
    class HostKey(type(Path())):
        def lstat(self):
            info = super().lstat()
            return SimpleNamespace(st_uid=0, st_mode=info.st_mode)
    monkeypatch.setattr(envelope, "Path", HostKey)
    assert envelope.unseal(sealed, private) == secret
    changed = {**sealed, "owner_id": "c7ade7f9-2003-4a38-ae19-393fffae8452"}
    with pytest.raises(ValueError, match="cryptographic operation failed"):
        envelope.unseal(changed, private)
    private.chmod(0o644)
    with pytest.raises(ValueError, match="root-only"):
        envelope.unseal(sealed, private)
    assert secret.decode() not in capsys.readouterr().out


@pytest.fixture(scope="module")
def merged_profile(tmp_path_factory):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI required for real Compose parsing; no containers run")
    path = tmp_path_factory.mktemp("compose-qa")
    (path / "env").write_text("NC_WORKER_IMAGE=" + startup.IMAGE + "\nNC_WORKER_ROOT=" + str(startup.ROOT)
        + "\nNC_SUPABASE_KEY_FILE=" + str(startup.CONFIG / "supabase-key") + "\nNC_QA_OWNER_ID=" + OWNER + "\n")
    (path / "trial.json").write_text(json.dumps(startup.trial_override(TRIAL, 2000)))
    args = ["docker", "--host=unix:///var/run/docker.sock", "compose", "--project-name", "noetharaclipz-isolated",
        "--env-file", str(path / "env"), "-f", str(ROOT / "deploy/worker/compose.yaml"),
        "-f", str(ROOT / "deploy/worker/compose.qa.yaml"), "-f", str(path / "trial.json"), "config", "--format", "json"]
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)["services"]["worker"]


def test_actual_compose_merge_preserves_qa_secret_mounts_limits_and_deadline(merged_profile):
    startup.require_profile(merged_profile, OWNER, 2000, TRIAL)


@pytest.mark.parametrize("change", [{"cpus": 3}, {"mem_limit": 16 * 1024**3}, {"restart": "always"},
    {"ports": [{"published": "8080"}]}, {"secrets": []}, {"entrypoint": ["python", "-m", "noetharaclipz.runner"]},
    {"volumes": []}, {"security_opt": []}])
def test_changed_qa_compose_configuration_cannot_be_started(merged_profile, change):
    profile = copy.deepcopy(merged_profile)
    profile.update(change)
    with pytest.raises(ValueError):
        startup.require_profile(profile, OWNER, 2000, TRIAL)
