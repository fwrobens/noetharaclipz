"""One read-only snapshot of the approved 24h pilot, also usable after expiry.

No waiting, worker execution, credential reads, queue calls, service changes or
network mutations. It reads retained controller/metrics/proof files and Docker
state; the existing systemd controller remains the independent monitor.
"""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEPLOYMENT = "c25d8492-56fb-4c56-a519-e9a9e4246525"
MANIFEST_SHA = "3918b9eb1dee06597852c016a7098a873eea914bbac8afa151557cda2c34dda0"
HELPER_SHA = "7f1b81ce79264e33d8980d6b9dc670ab51c83838c6d05e192d8309eb1766cf67"
BASE_HELPER_SHA = "7bba366d6bb5ade982feb94668e127396e043ed5a10bad50c9b4efbf21918efc"
CFG = Path("/etc/noetharaclipz-isolated/continuous") / DEPLOYMENT
DATA = Path("/var/lib/noetharaclipz-isolated/continuous") / DEPLOYMENT
PREPARATION = Path("/var/tmp") / ("nccz-24h-" + DEPLOYMENT)
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def verify_file(path, expected):
    info = path.lstat()
    if (
        path.is_symlink()
        or info.st_uid != 0
        or info.st_mode & 0o022
        or sha(path.read_bytes()) != expected
    ):
        raise ValueError("Reviewed diagnostic/runtime source changed")


def read_command(command, allowed, cid):
    logs = DOCKER + ["logs", "--timestamps", "--tail", "60", cid]
    if not allowed(command) and command != logs:
        raise ValueError("Status collector prohibits this command")
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode and command[0] != "systemctl":
        raise RuntimeError("Read-only command failed: " + " ".join(command[:4]))
    return (
        (result.stdout + result.stderr).strip()
        if command == logs
        else result.stdout.strip()
    )


def safe_state(raw):
    body, count, policy = raw.rsplit("|", 2)
    state = json.loads(body)
    return {
        **{
            k: state.get(k)
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
        "health": (state.get("Health") or {}).get("Status", "none"),
        "restart_count": int(count),
        "restart_policy": json.loads(policy),
    }


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
        raise ValueError("Wrong host or execution identity")
    manifest = read(CFG / "public/manifest.json")
    if sha(canonical(manifest)) != MANIFEST_SHA:
        raise ValueError("Wrong installed manifest")
    for name, expected in manifest["files"].items():
        verify_file(CFG / "code" / name, expected)
    for name, expected in manifest["unit_sha256"].items():
        verify_file(CFG / "systemd" / name, expected)
    helper = PREPARATION / "handoff/inspect_continuous_24h_host_v2.py"
    verify_file(helper, HELPER_SHA)
    verify_file(
        PREPARATION / "handoff/inspect_continuous_pilot_host.py", BASE_HELPER_SHA
    )
    sys.path[:0] = [str(PREPARATION / "handoff"), str(CFG / "code/host")]
    spec = importlib.util.spec_from_file_location("verified_status_admission", helper)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    import reliability_platform as platform
    from continuous_host import load

    load(CFG / "public/manifest.json", active=False)
    reports = DATA / "reports"
    record = read(reports / "container.json")
    if not record or record.get("deployment_id") != DEPLOYMENT:
        raise ValueError("Controller container record not yet available")
    cid = record["id"]
    platform.run = lambda command, timeout=30: read_command(
        command, collector.command_allowed, cid
    )
    if (
        platform.docker(
            "inspect",
            "--format",
            '{{index .Config.Labels "io.noetharaclipz.continuous"}}',
            cid,
        )
        != DEPLOYMENT
    ):
        raise ValueError("Container does not belong to this deployment")

    def state(container):
        return safe_state(
            platform.docker(
                "inspect",
                "--format",
                "{{json .State}}|{{.RestartCount}}|{{json .HostConfig.RestartPolicy}}",
                container,
            )
        )

    baseline = read(reports / "admission.json")
    units = {
        name: collector.unit_state(name, expected)
        for name, expected in manifest["unit_sha256"].items()
    }
    services = platform.service_snapshot(excluded=cid)
    platform.verify_network()
    fingerprint = platform.firewall_fingerprint(verify=True)
    old = {old_cid: state(old_cid) for old_cid in collector.admission.OLD_CONTAINERS}
    old[collector.PREVIOUS_CID] = state(collector.PREVIOUS_CID)
    status = read(reports / "status.json") or {}
    metrics = read(reports / "metrics-summary.json")
    proofs = [
        read(path)
        for path in reports.glob("network-*.json")
        if path.name != "network-attempt.json"
    ]
    logs = platform.docker("logs", "--timestamps", "--tail", "60", cid)
    result = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "worker_started_stopped_restarted_or_executed": False,
        "credential_file_contents_read": False,
        "deployment_id": DEPLOYMENT,
        "manifest_sha256": MANIFEST_SHA,
        "fixed_stop_utc": "2026-11-10T23:00:00Z",
        "container_id": cid,
        "docker_state": state(cid),
        "status": status,
        "status_age_seconds": round(time.time() - status["at"], 3)
        if "at" in status
        else None,
        "metrics": metrics,
        "grant_present": (CFG / "gates/grant.json").exists(),
        "units": units,
        "boot_start_disabled": all(v["enabled"] == "disabled" for v in units.values()),
        "existing_services": services,
        "existing_services_unchanged": services == baseline["existing_services"],
        "previous_containers": old,
        "previous_evidence_unchanged": collector.retained_evidence()
        == baseline["previous_evidence"],
        "isolation_unchanged": fingerprint == baseline["firewall_fingerprint"],
        "generation_proofs": proofs,
        "lifecycle_log_lines": [
            line
            for line in logs.splitlines()
            if "continuous_generation_stopped" in line
        ],
        "retained_report_files": [
            {"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(reports.iterdir())
            if p.is_file()
        ],
        "full_24h_test_passed": False,
    }
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps(
                {
                    "collector_failed": True,
                    "read_only": True,
                    "error_type": type(error).__name__,
                    "details": str(error)[:250],
                    "container_action_taken": False,
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
