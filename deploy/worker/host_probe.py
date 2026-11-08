"""Run manually on the selected host for READ-ONLY capacity inspection.

Never install software, run commands inside containers, read process arguments/
environment, inspect container environment, or alter any AWS/Docker resource.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path


def read(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return {
            "ok": r.returncode == 0,
            "output": r.stdout.strip() if r.returncode == 0 else "unavailable",
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "output": "unavailable"}


def main():
    memory = {
        k: int(v.split()[0]) * 1024
        for k, v in (
            line.split(":", 1)
            for line in Path("/proc/meminfo").read_text().splitlines()
        )
        if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
    }
    disk = shutil.disk_usage("/var/lib" if Path("/var/lib").exists() else "/")
    report = {
        "read_only": True,
        "memory_bytes": memory,
        "logical_cpus": os.cpu_count(),
        "loadavg": os.getloadavg(),
        "disk_bytes": {"total": disk.total, "free": disk.free},
        "cpu_model": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            None,
        ),
    }
    report["filesystems"] = read(["df", "-hT"])
    report["process_usage_no_arguments"] = read(
        ["ps", "-eo", "comm,pcpu,pmem,rss", "--sort=-rss"]
    )
    report["listening_ports"] = read(["ss", "-lntuH"])
    docker = ["docker", "--host=unix:///var/run/docker.sock"]
    report["docker_resources"] = read(
        docker
        + [
            "info",
            "--format",
            "server={{.ServerVersion}} cgroup_version={{.CgroupVersion}} driver={{.CgroupDriver}} storage={{.Driver}} cpus={{.NCPU}} memory={{.MemTotal}}",
        ]
    )
    report["docker_boot_enabled"] = read(["systemctl", "is-enabled", "docker"])
    report["compose_version"] = read(docker + ["compose", "version", "--short"])
    report["containers"] = read(
        docker + ["ps", "--format", "{{.Names}} {{.Status}} {{.Ports}}"]
    )
    report["container_usage"] = read(
        docker + ["stats", "--no-stream", "--format", "{{json .}}"]
    )
    report["docker_networks"] = read(
        docker + ["network", "ls", "--format", "{{.Name}} {{.Driver}}"]
    )
    ids = read(docker + ["ps", "-q"])
    if ids["ok"] and ids["output"]:
        report["container_limits_no_environment"] = read(
            docker
            + [
                "inspect",
                "--format",
                "{{.Name}} memory={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} nano_cpus={{.HostConfig.NanoCpus}} cpu_quota={{.HostConfig.CpuQuota}} pids={{.HostConfig.PidsLimit}} restart={{.HostConfig.RestartPolicy.Name}}",
                *ids["output"].splitlines(),
            ]
        )
    report["decision"] = (
        "Review peak workloads, CPU credits, filesystem/egress isolation and at least 8 GiB genuinely spare RAM plus host headroom; one snapshot is insufficient."
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
