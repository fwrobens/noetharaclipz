"""Host-side durable cgroup-v2 measurements, including across Docker restarts."""

import json
from pathlib import Path, PurePosixPath


def cgroup_path(pid, proc=Path("/proc"), root=Path("/sys/fs/cgroup")):
    membership = (proc / str(pid) / "cgroup").read_text()
    value = next(line.split(":", 2)[2] for line in membership.splitlines() if line.startswith("0::"))
    relative = PurePosixPath(value)
    if not relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Untrusted cgroup membership path")
    return root / str(relative).lstrip("/")


def read_sample(path):
    values = {"_cgroup_inode": str(path.stat().st_ino)}
    for name in ("memory.current", "memory.peak", "memory.events", "memory.max", "cpu.stat", "cpu.max", "pids.current"):
        p = path / name
        if p.is_file():
            values[name] = p.read_text().strip()
    if "cpu.stat" not in values or "memory.current" not in values:
        raise ValueError("Live cgroup counters unavailable; never substitute zero")
    return values


class Measurements:
    def __init__(self):
        self.generations = {}
        self.cpu_domains = {}
        self.samples = 0

    def add(self, generation, values, monotonic, wall):
        cpu = dict(line.split() for line in values["cpu.stat"].splitlines())
        used = int(cpu["usage_usec"])
        memory = int(values["memory.current"])
        kernel_peak = int(values["memory.peak"]) if "memory.peak" in values else None
        state = self.generations.setdefault(generation, {"last_usage": None, "last_at": None,
            "cpu_usage_usec": 0, "memory_peak_bytes": None, "sampled_peak_cpu_percent": None,
            "final_snapshot_captured": False, "counter_reset_observed": False})
        if state["last_usage"] is not None and used < state["last_usage"]:
            state["counter_reset_observed"] = True
            raise ValueError("CPU counter reset within one start generation")
        domain = values.get("_cgroup_inode", generation)
        if state.get("cpu_domain") is None:
            # Some runtimes keep the same cgroup across restarts. Do not sum
            # its cumulative CPU counter twice. If a recreated cgroup reused
            # an inode but reset its counter, start a distinct counter domain.
            if used < self.cpu_domains.get(domain, 0):
                domain += ":" + generation
            state["cpu_domain"] = domain
        domain = state["cpu_domain"]
        self.cpu_domains[domain] = max(self.cpu_domains.get(domain, 0), used)
        percent = None
        if state["last_at"] is not None and monotonic > state["last_at"]:
            percent = (used - state["last_usage"]) / 1_000_000 / (monotonic - state["last_at"]) * 100
            state["sampled_peak_cpu_percent"] = max(state["sampled_peak_cpu_percent"] or 0, percent)
        state.update(last_usage=used, last_at=monotonic, cpu_usage_usec=used)
        state["memory_peak_bytes"] = max(state["memory_peak_bytes"] or 0, kernel_peak or memory)
        self.samples += 1
        return {"at_unix": wall, "generation": generation, "memory_current_bytes": memory,
                "kernel_memory_peak_bytes": kernel_peak, "cpu_usage_usec": used,
                "interval_cpu_percent_one_core_100": percent, "cgroup": values}

    def summary(self):
        return {"sample_count": self.samples, "generations": self.generations,
                "peak_memory_bytes": max((g["memory_peak_bytes"] or 0 for g in self.generations.values()), default=None),
                "sampled_peak_cpu_percent": max((g["sampled_peak_cpu_percent"] for g in self.generations.values()
                                                if g["sampled_peak_cpu_percent"] is not None), default=None),
                "total_cpu_seconds": sum(self.cpu_domains.values()) / 1_000_000 if self.samples else None,
                "cpu_counter_domains": self.cpu_domains,
                "cpu_peak_is_sampled_not_instantaneous": True,
                "final_snapshots_complete": bool(self.generations) and all(g["final_snapshot_captured"] for g in self.generations.values())}


def append_sample(path, sample):
    with path.open("a") as stream:
        stream.write(json.dumps(sample, separators=(",", ":")) + "\n")
        stream.flush()
