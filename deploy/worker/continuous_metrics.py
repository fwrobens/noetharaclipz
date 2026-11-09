"""Bounded, durable cgroup ledger. No model/queue operations."""

import json
import os
import tempfile
from pathlib import Path

from reliability_metrics import Measurements


def atomic(path, value, mode=0o600, gid=0):
    fd, temp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        os.fchown(fd, 0, gid)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


class DurableMetrics:
    def __init__(self, root):
        self.root = root
        self.metrics = Measurements()
        self.retired_cpu = 0
        self.peak_memory = None
        self.peak_cpu = None
        path = root / "metrics-summary.json"
        if path.exists():
            old = json.loads(path.read_text())
            self.metrics.generations = old["generations"]
            self.metrics.cpu_domains = old["cpu_counter_domains"]
            self.metrics.samples = old["sample_count"]
            self.retired_cpu = old.get("retired_cpu_usec", 0)
            self.peak_memory = old.get("peak_memory_bytes")
            self.peak_cpu = old.get("sampled_peak_cpu_percent")

    def add(self, generation, sample, mono, wall, final=False):
        row = self.metrics.add(generation, sample, mono, wall)
        if final:
            self.metrics.generations[generation]["final_snapshot_captured"] = True
        summary = self.metrics.summary()
        self.peak_memory = max(self.peak_memory or 0, summary["peak_memory_bytes"] or 0)
        self.peak_cpu = max(
            self.peak_cpu or 0, summary["sampled_peak_cpu_percent"] or 0
        )
        while len(self.metrics.generations) > 64:
            key = next(iter(self.metrics.generations))
            removed = self.metrics.generations.pop(key)
            domain = removed["cpu_domain"]
            if not any(
                g["cpu_domain"] == domain for g in self.metrics.generations.values()
            ):
                self.retired_cpu += self.metrics.cpu_domains.pop(domain, 0)
        # Bounded samples survive controller/container restarts; no unbounded log.
        path = self.root / "metrics.jsonl"
        if path.exists() and path.stat().st_size >= 5 * 1024**2:
            for i in (2, 1):
                old = self.root / ("metrics.jsonl." + str(i))
                if old.exists():
                    old.replace(self.root / ("metrics.jsonl." + str(i + 1)))
            path.replace(self.root / "metrics.jsonl.1")
        with path.open("a") as stream:
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
        atomic(self.root / "metrics-summary.json", self.summary())

    def summary(self):
        result = self.metrics.summary()
        result.update(
            retired_cpu_usec=self.retired_cpu,
            total_cpu_seconds=(
                sum(self.metrics.cpu_domains.values()) + self.retired_cpu
            )
            / 1_000_000
            if self.metrics.samples
            else None,
            peak_memory_bytes=self.peak_memory,
            sampled_peak_cpu_percent=self.peak_cpu,
            retained_generations_limit=64,
            sample_retention_bytes=4 * 5 * 1024**2,
        )
        return result
