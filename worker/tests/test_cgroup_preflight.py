"""Read-only quota proof: requested flags/outer host limits cannot pass."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "quota_probe", Path(__file__).resolve().parents[2] / "deploy/worker/check_cgroup_limits.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_v2_actual_container_limits_pass(tmp_path):
    group = tmp_path / "cgroup"
    group.mkdir()
    for name, value in {
        "memory.max": str(8 * 1024**3),
        "cpu.max": "200000 100000",
        "memory.swap.max": "0",
        "pids.max": "256",
    }.items():
        (group / name).write_text(value)
    membership = tmp_path / "membership"
    membership.write_text("0::/\n")
    assert module.evaluate(module.read_limits(group, membership))["passed"]


def test_outer_host_limits_or_unlimited_controls_do_not_pass():
    outer = {
        "memory_bytes": 32 * 1024**3,
        "cpu_quota": 400000,
        "cpu_period": 100000,
        "extra_swap_bytes": 0,
        "pids_max": 4096,
    }
    assert not module.evaluate(outer)["passed"]
    assert not module.evaluate({"read_error": "ValueError"})["passed"]


def test_v1_membership_uses_own_child_not_host_root(tmp_path):
    group = tmp_path / "cgroup"
    group.mkdir()
    for mount, values in {
        "memory": {
            "memory.limit_in_bytes": str(8 * 1024**3),
            "memory.memsw.limit_in_bytes": str(8 * 1024**3),
        },
        "cpu,cpuacct": {"cpu.cfs_quota_us": "200000", "cpu.cfs_period_us": "100000"},
        "pids": {"pids.max": "256"},
    }.items():
        child = group / mount / "docker/qa"
        child.mkdir(parents=True)
        for name, value in values.items():
            (child / name).write_text(value)
    membership = tmp_path / "membership"
    membership.write_text("2:memory:/docker/qa\n3:cpu,cpuacct:/docker/qa\n4:pids:/docker/qa\n")
    assert module.evaluate(module.read_limits(group, membership))["passed"]


def test_missing_kernel_controls_fail_closed(tmp_path):
    member = tmp_path / "membership"
    member.write_text("0::/\n")
    assert not module.evaluate(module.read_limits(tmp_path, member))["passed"]
