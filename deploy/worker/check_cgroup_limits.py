"""Read actual current-process cgroup limits. No configuration/host changes.

Run INSIDE the standby container, not on the EC2 host. Docker inspect flags
alone do not establish enforcement, particularly with rootless Docker.
"""

import json
from pathlib import Path, PurePosixPath


def read_limits(root=Path("/sys/fs/cgroup"), membership=Path("/proc/self/cgroup")):
    result = {}

    def number(value):
        value = value.strip()
        return None if value in ("max", "-1") else int(value)

    try:
        groups = [line.split(":", 2) for line in membership.read_text().splitlines()]

        def relative(value):
            parts = PurePosixPath(value).parts
            if ".." in parts:
                raise ValueError("Cgroup membership cannot be resolved safely")
            return value.lstrip("/")

        unified = next((g for g in groups if g[0] == "0" and not g[1]), None)
        if unified:
            base = root / relative(unified[2])
            cpu = (base / "cpu.max").read_text().split()
            result = {
                "version": 2,
                "memory_bytes": number((base / "memory.max").read_text()),
                "cpu_quota": number(cpu[0]),
                "cpu_period": int(cpu[1]),
                "extra_swap_bytes": number((base / "memory.swap.max").read_text()),
                "pids_max": number((base / "pids.max").read_text()),
            }
        else:

            def controller(name):
                group = next(g for g in groups if name in g[1].split(","))
                for mount in (group[1], name):
                    path = root / mount / relative(group[2])
                    if path.is_dir():
                        return path
                raise OSError("Controller mount unavailable")

            mem, cpu, pids = controller("memory"), controller("cpu"), controller("pids")
            limit = int((mem / "memory.limit_in_bytes").read_text())
            result = {
                "version": 1,
                "memory_bytes": limit,
                "cpu_quota": number((cpu / "cpu.cfs_quota_us").read_text()),
                "cpu_period": int((cpu / "cpu.cfs_period_us").read_text()),
                "extra_swap_bytes": int(
                    (mem / "memory.memsw.limit_in_bytes").read_text()
                )
                - limit,
                "pids_max": number((pids / "pids.max").read_text()),
            }
    except (OSError, ValueError, StopIteration, IndexError) as exc:
        result["read_error"] = type(exc).__name__
    return result


def evaluate(limits):
    quota, period = limits.get("cpu_quota", -1), limits.get("cpu_period", 0)
    pids = limits.get("pids_max")
    checks = {
        "memory_exactly_8gib": limits.get("memory_bytes") == 8 * 1024**3,
        "cpu_exactly_2": isinstance(quota, int)
        and quota > 0
        and period > 0
        and quota == 2 * period,
        "no_extra_swap": limits.get("extra_swap_bytes") == 0,
        "pids_at_most_256": isinstance(pids, int) and 0 < pids <= 256,
        "all_controls_read": "read_error" not in limits,
    }
    return {
        "actual_cgroup_limits": limits,
        "checks": checks,
        "passed": all(checks.values()),
        "source": "current process cgroup files, not requested Docker flags",
    }


def main():
    result = evaluate(read_limits())
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
