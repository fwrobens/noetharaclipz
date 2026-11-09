"""Read-only EC2 admission collector; never imports credentials or starts work.

Run from the verified private source handoff. No Docker exec/run/start/restart,
network probes, secret reads, unit installation or firewall mutations exist here.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from uuid import UUID

DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]
IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
OLD_CONTAINERS = {
    "fbe3d4f4d9b1c95cb3cae77278a40a5cf5d52c77435eccdc3d14c60d17c06f99": 0,
    "af5b1136b2c734fd0c67e26918cb9d415af370db297c4d8250d2f8860ef4301d": 0,
    "6c66cb349cbf21ff16ee168c079289a6e17712f3beb81f2eb1da724a71e5db6e": 1,
}


def command_allowed(command):
    if command[:2] == DOCKER:
        tail = command[2:]
        return (
            bool(tail)
            and (
                tail[0] in ("info", "ps", "inspect", "stats")
                or tail[:2] == ["image", "inspect"]
                or tail[:2] in (["network", "inspect"], ["network", "ls"])
            )
            and (tail[0] != "stats" or "--no-stream" in tail)
        )
    if command[:3] == ["iptables", "--wait", "5"]:
        return command[3:4] in (["-S"], ["-C"]) or command[3:] == ["-t", "raw", "-S"]
    return command in (
        ["systemctl", "is-active", "noetharaclipz-continuous.service"],
        ["systemctl", "is-enabled", "noetharaclipz-continuous.service"],
    )


def read_command(command, timeout=30):
    if not command_allowed(command):
        raise ValueError("Collector prohibits this command")
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode and command[0] != "systemctl":
        raise RuntimeError(
            "Read-only check failed: "
            + " ".join(command[:4])
            + " (exit "
            + str(result.returncode)
            + ")"
        )
    return result.stdout.strip()


def verify_sources(root, expected):
    raw = (root / "bundle.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Source bundle hash changed")
    bundle = json.loads(raw)
    if bundle.get("base_image") != IMAGE or bundle.get("source_dirty") is not False:
        raise ValueError("Unreviewed dependency image/source")
    if set(bundle["files"]) != set(bundle["sha256"]):
        raise ValueError("Incomplete source manifest")
    for name, source in bundle["files"].items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe source path")
        file = root / name
        if (
            file.is_symlink()
            or not file.is_file()
            or hashlib.sha256(file.read_bytes()).hexdigest() != bundle["sha256"][name]
            or file.read_text() != source
        ):
            raise ValueError("Changed staged source")
    return bundle


def collect(root, deployment, expected):
    if str(UUID(deployment)) != deployment:
        raise ValueError("Canonical deployment identifier required")
    verify_sources(root, expected)
    sys.path.insert(0, str(root / "host"))
    import reliability_platform as host
    from reliability_probe import TARGETS

    host.run = read_command  # Enforce read-only even within reviewed helpers.
    host.require_host()
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        os.environ.pop(key, None)
    host.verify_network()
    fingerprint = host.firewall_fingerprint(verify=True)
    host.verify_probe_destinations(TARGETS)
    services = host.service_snapshot()
    memory = {
        line.split(":", 1)[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith(("MemTotal:", "MemAvailable:", "SwapTotal:"))
    }
    free_disk = shutil.disk_usage("/var/lib/noetharaclipz-isolated").free
    info = read_command(
        DOCKER
        + [
            "info",
            "--format",
            "{{.ServerVersion}}|{{.CgroupVersion}}|{{json .SecurityOptions}}",
        ]
    )
    version, cgroup, security = info.split("|", 2)
    image = read_command(
        DOCKER
        + [
            "image",
            "inspect",
            IMAGE,
            "--format",
            "{{.Id}}|{{.Os}}|{{.Architecture}}|{{.Config.User}}",
        ]
    )
    assets = json.loads((host.MODELS / "manifest.json").read_text())
    key = host.KEY.lstat()  # Metadata only; contents are never read.
    secret_metadata_ok = (
        not host.KEY.is_symlink()
        and key.st_uid == 0
        and key.st_gid == 62001
        and key.st_mode & 0o777 == 0o440
    )
    stats = []
    for line in read_command(
        DOCKER + ["stats", "--no-stream", "--format", "{{json .}}"], timeout=45
    ).splitlines():
        value = json.loads(line)
        stats.append(
            {
                key: value.get(key)
                for key in (
                    "Container",
                    "Name",
                    "CPUPerc",
                    "MemUsage",
                    "MemPerc",
                    "PIDs",
                )
            }
        )
    old = {}
    template = (
        "{{.State.Status}}|{{.State.Running}}|{{.State.ExitCode}}|"
        "{{.State.OOMKilled}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.State.FinishedAt}}"
    )
    for cid, restarts in OLD_CONTAINERS.items():
        fields = read_command(DOCKER + ["inspect", "--format", template, cid]).split(
            "|"
        )
        old[cid] = dict(
            zip(
                (
                    "status",
                    "running",
                    "exit_code",
                    "oom_killed",
                    "restart_count",
                    "started_at",
                    "finished_at",
                ),
                fields,
            )
        )
        old[cid]["expected_stopped_state"] = fields[:5] == [
            "exited",
            "false",
            "0",
            "false",
            str(restarts),
        ]
    active = read_command(
        ["systemctl", "is-active", "noetharaclipz-continuous.service"]
    )
    enabled = read_command(
        ["systemctl", "is-enabled", "noetharaclipz-continuous.service"]
    )
    running = read_command(
        DOCKER + ["ps", "-q", "--filter", "label=io.noetharaclipz.continuous"]
    )
    paths = [
        Path(base) / deployment
        for base in (
            "/etc/noetharaclipz-isolated/continuous",
            "/var/lib/noetharaclipz-isolated/continuous",
        )
    ]
    checks = {
        "at_least_10gib_available_ram": memory["MemAvailable"] >= 10 * 1024**3,
        "at_least_20gib_free_disk": free_disk >= 20 * 1024**3,
        "at_least_8_host_cpus": (os.cpu_count() or 0) >= 8,
        "cgroup_v2": cgroup == "2",
        "reviewed_image_identity": image == IMAGE + "|linux|amd64|62001:62001",
        "pinned_assets_manifest": assets
        == {
            "video_model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
            "video_revision": "7b375e1b73b11138ff12fe22c8f2822d8fe03467",
            "whisper_revision": "536b0662742c02347bc0e980a01041f333bce120",
        },
        "secret_file_metadata_valid": secret_metadata_ok,
        "new_deployment_paths_absent": not any(os.path.lexists(p) for p in paths),
        "no_continuous_worker_running": not running
        and active in ("inactive", "unknown"),
        "no_unattended_unit_enabled": enabled in ("disabled", "not-found", "masked"),
        "previous_trials_remain_stopped": all(
            v["expected_stopped_state"] for v in old.values()
        ),
        "existing_services_unchanged_during_collection": services
        == host.service_snapshot(),
        "isolation_unchanged_during_collection": fingerprint
        == host.firewall_fingerprint(verify=True),
    }
    return {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "host_preparation_checks_passed": all(checks.values()),
        "deployment_id": deployment,
        "instance_id": host.INSTANCE,
        "host_cpu_count": os.cpu_count(),
        "load_average": os.getloadavg(),
        "memory_bytes": memory,
        "free_disk_bytes": free_disk,
        "docker": {
            "version": version,
            "cgroup": cgroup,
            "security_options": json.loads(security),
        },
        "container_resource_snapshot": stats,
        "existing_services": services,
        "previous_trials": old,
        "checks": checks,
        "firewall_fingerprint": fingerprint,
        "continuous_unit": {"active": active, "enabled": enabled},
        "worker_started_or_executed": False,
        "credential_contents_read": False,
        "network_rules_changed": False,
        "queue_access": False,
        "models_loaded": False,
        "units_installed": False,
        "pending": [
            "Final operator approval and immutable active manifest",
            "Separately authorized startup",
            "Fresh per-generation live denial proofs and actual new cgroup quota measurements",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    args = parser.parse_args()
    try:
        report = collect(args.source_root, args.deployment_id, args.bundle_sha256)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report = {
            "host_preparation_checks_passed": False,
            "read_only": True,
            "error_type": type(error).__name__,
            "worker_started_or_executed": False,
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
