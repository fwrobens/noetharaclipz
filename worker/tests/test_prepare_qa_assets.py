"""Asset preparation cannot broaden network ownership, mounts, secrets or limits."""

import builtins
import copy
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "deploy/worker"
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("prepare_qa_assets", ROOT / "prepare_qa_assets.py")
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


def network_pair():
    receipt = {"network_preflight_passed": True, "diagnostic_removed": True,
               "existing_services_unchanged": True, "policy_sha256": assets.POLICY_SHA,
               "network_id": "owned-id", "probe_id": "owned-probe"}
    network = {"Id": "owned-id", "Name": assets.NETWORK, "Labels": {"io.noetharaclipz.preflight": "owned-probe"},
               "Options": {"com.docker.network.bridge.name": "nccz-qa0"}, "EnableIPv6": False,
               "Containers": {}, "IPAM": {"Config": [{"Subnet": "172.20.0.0/24"}]}}
    return receipt, network


def profile():
    return {"image": assets.IMAGE, "cpus": 2, "mem_limit": "8589934592", "memswap_limit": "8589934592",
            "pids_limit": 256, "user": "62001:62001", "pull_policy": "never",
            "volumes": [{"source": str(assets.ROOT / "models"), "target": "/models"}],
            "environment": {"HF_HUB_OFFLINE": "0", "TRANSFORMERS_OFFLINE": "0"}}


def test_owned_empty_network_and_exact_seed_profile_are_admitted():
    assets.require_network(*network_pair())
    assets.require_seed_profile(profile())


@pytest.mark.parametrize("field,value", [("Id", "foreign"), ("Containers", {"unknown": {}}), ("EnableIPv6", True)])
def test_changed_or_busy_network_cannot_be_used_for_seeding(field, value):
    receipt, network = network_pair()
    network[field] = value
    with pytest.raises(ValueError):
        assets.require_network(receipt, network)


def test_success_receipt_cannot_be_reused_for_a_network_with_different_owner():
    receipt, network = network_pair()
    network["Labels"]["io.noetharaclipz.preflight"] = "another-attempt"
    with pytest.raises(ValueError):
        assets.require_network(receipt, network)


@pytest.mark.parametrize("change", [
    {"cpus": 3}, {"mem_limit": "17179869184"}, {"memswap_limit": "17179869184"},
    {"secrets": ["supabase_key"]}, {"ports": [{"published": "8080"}]},
    {"environment": {"SUPABASE_SECRET_KEY": "must-not-enter-seed"}},
    {"volumes": [{"source": "/other-app", "target": "/models"}]},
])
def test_seed_cannot_gain_resources_credentials_ports_or_other_app_mounts(change):
    seed = copy.deepcopy(profile())
    seed.update(change)
    with pytest.raises(ValueError):
        assets.require_seed_profile(seed)


def test_an_existing_file_or_symlink_is_never_overwritten(tmp_path):
    target = tmp_path / "existing"
    target.write_text("untouched")
    link = tmp_path / "link"
    link.symlink_to(target)
    for path in (target, link):
        with pytest.raises(FileExistsError):
            assets.write_new(path, "replacement")
    assert target.read_text() == "untouched"


@pytest.mark.parametrize("passed", [False, True])
def test_real_seed_program_gates_the_downloader_on_kernel_proof(passed):
    imported = []
    real_import = builtins.__import__
    def importer(name, *args, **kwargs):
        if name == "noetharaclipz_deploy.assets":
            imported.append(name)
            return types.SimpleNamespace(main=lambda: imported.append("download"))
        return real_import(name, *args, **kwargs)
    quota = "def read_limits(): return {}\ndef evaluate(value): return {'passed': " + repr(passed) + "}"
    scope = {"__builtins__": {**vars(builtins), "__import__": importer}}
    if passed:
        exec(assets.seed_program(quota), scope)
        assert imported == ["noetharaclipz_deploy.assets", "download"]
    else:
        with pytest.raises(SystemExit, match="download blocked"):
            exec(assets.seed_program(quota), scope)
        assert imported == []
