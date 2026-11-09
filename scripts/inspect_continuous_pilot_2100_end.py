"""Read-only final collector. Waits for the existing pilot to stop; never stops it."""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE = Path("/tmp/nccz-continuous-pilot-0qkrd0gd")
CFG = Path(
    "/etc/noetharaclipz-isolated/continuous/11865b83-9836-4ff3-a99e-dfac4df71f34"
)
DATA = Path(
    "/var/lib/noetharaclipz-isolated/continuous/11865b83-9836-4ff3-a99e-dfac4df71f34"
)
MANIFEST_SHA = "0903df1cfcb68f120877ca1088f4608584bc1bddebbb1b9b4ddb41725ec3792f"
COLLECTOR_SHA = "7bba366d6bb5ade982feb94668e127396e043ed5a10bad50c9b4efbf21918efc"
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]
STOP = 1794259800


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def main():
    sys.dont_write_bytecode = True
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        os.environ.pop(key, None)
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != "i-0be10e530045fc650"
    ):
        raise ValueError("Wrong host or identity")
    script = SOURCE / "inspect-pilot-host.py"
    if (
        script.is_symlink()
        or hashlib.sha256(script.read_bytes()).hexdigest() != COLLECTOR_SHA
    ):
        raise ValueError("Reviewed collector changed")
    spec = importlib.util.spec_from_file_location("read_only_collector", script)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    sys.path.insert(0, str(CFG / "code/host"))
    import reliability_platform as platform

    platform.run = collector.read_command
    from continuous_host import load

    manifest, cfg, data = load(CFG / "public/manifest.json", active=False)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != MANIFEST_SHA:
        raise ValueError("Active manifest changed")
    reports = data / "reports"
    print(
        "Waiting for the existing authorized pilot's automatic stop; no container action will be taken.",
        flush=True,
    )
    while time.time() < STOP + 90:
        status = read(reports / "status.json") or {}
        if status.get("stage") in ("closed", "blocked_security_or_consent"):
            break
        time.sleep(5)
    cid = read(reports / "container.json")["id"]
    if (
        platform.docker(
            "inspect",
            "--format",
            '{{index .Config.Labels "io.noetharaclipz.continuous"}}',
            cid,
        )
        != manifest["deployment_id"]
    ):
        raise ValueError("Refusing to inspect logs from an unrelated container")

    def state(container):
        body, count, policy = platform.docker(
            "inspect",
            "--format",
            "{{json .State}}|{{.RestartCount}}|{{json .HostConfig.RestartPolicy}}",
            container,
        ).rsplit("|", 2)
        value = json.loads(body)
        return {
            **{
                k: value.get(k)
                for k in (
                    "Status",
                    "Running",
                    "Restarting",
                    "ExitCode",
                    "OOMKilled",
                    "StartedAt",
                    "FinishedAt",
                )
            },
            "restart_count": int(count),
            "restart_policy": json.loads(policy),
        }

    baseline = read(SOURCE / "host-preflight.json")
    services = platform.service_snapshot(excluded=cid)
    old = {}
    for old_cid, earlier in baseline["previous_trials"].items():
        current = state(old_cid)
        current["unchanged"] = (
            current["StartedAt"] == earlier["started_at"]
            and current["FinishedAt"] == earlier["finished_at"]
            and current["restart_count"] == int(earlier["restart_count"])
            and current["Running"] is False
        )
        old[old_cid] = current
    # Only this matching container's logs are read; retain lifecycle lines only.
    result = subprocess.run(
        DOCKER + ["logs", "--timestamps", "--tail", "60", cid],
        capture_output=True,
        text=True,
        timeout=30,
    )
    lifecycle = [
        line
        for line in (result.stdout + result.stderr).splitlines()
        if "continuous_generation_stopped" in line
    ]
    fingerprint = platform.firewall_fingerprint(verify=True)
    report = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "worker_started_stopped_restarted_or_executed": False,
        "credential_file_contents_read": False,
        "manifest_sha256": MANIFEST_SHA,
        "fixed_stop_utc": "2026-11-09T21:30:00Z",
        "docker_state": state(cid),
        "container_id": cid,
        "status": read(reports / "status.json"),
        "metrics": read(reports / "metrics-summary.json"),
        "grant_present": (cfg / "gates/grant.json").exists(),
        "continuous_unit": {
            "active": collector.read_command(
                ["systemctl", "is-active", "noetharaclipz-continuous.service"]
            ),
            "enabled": collector.read_command(
                ["systemctl", "is-enabled", "noetharaclipz-continuous.service"]
            ),
        },
        "existing_services_unchanged": services == baseline["existing_services"],
        "previous_trials": old,
        "isolation_unchanged": fingerprint == baseline["firewall_fingerprint"],
        "lifecycle_log_lines": lifecycle,
        "generation_proofs": [
            read(p)
            for p in reports.glob("network-*.json")
            if p.name != "network-attempt.json"
        ],
        "retained_report_files": [
            {"name": p.name, "bytes": p.stat().st_size}
            for p in reports.iterdir()
            if p.is_file()
        ],
    }
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps(
                {
                    "read_only": True,
                    "collector_failed": True,
                    "error_type": type(error).__name__,
                    "details": str(error)[:250],
                    "container_action_taken": False,
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
