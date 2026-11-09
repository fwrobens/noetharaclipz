"""Read-only inspection of the expired EC2 QA trial. NEVER start/exec a container.

Uses only Docker inspect/ps/logs/events and selected local non-secret files.
Never loads credentials, installs tools, changes policy or edits host settings.
Stopped cgroup counters may be gone; absence is not zero consumption.
"""

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

INSTANCE = "i-0be10e530045fc650"
CID = "fbe3d4f4d9b1c95cb3cae77278a40a5cf5d52c77435eccdc3d14c60d17c06f99"
TRIAL = "9563aeb9-2620-4e05-acf2-1e69ce18b819"
OWNER = "c7ade7f9-2003-4a38-ae19-393fffae8452"
DEADLINE = 1794185532
WRAPPER_SHA = "32f01d74f7379c02cf6825491220a7b1d67fd786c2c4cc1cf21486d8a771f394"
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]
EXPECTED_SERVICES = {"supabase_" + name + "_wwgwnlhmbmrspmzdptzh" for name in ("rest", "inbucket", "auth", "kong", "db")} | {"noethara-ec2-staging-worker-1"}
SAFE_ENV = {"NC_QA_STOP_AT", "NC_QA_TRIAL_ID", "NC_WORKER_OWNER_ID", "NC_AI_PROVIDER",
            "GEMINI_FREE_TIER_VERIFIED", "NC_GLOBAL_QUEUE_APPROVED", "NC_DEPLOY_MODE"}


def redact(value):
    value = re.sub(r"(?i)(Bearer\s+)\S+", r"\1[redacted]", value)
    value = re.sub(r"\b(?:sb_secret_|sb_publishable_)[A-Za-z0-9_-]+", "[redacted-key]", value)
    value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted-jwt]", value)
    return re.sub(r"(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,}]+", r"\1[redacted]", value)


def read(command):
    if command[:2] == ["image", "inspect"] or not command or command[0] not in {"inspect", "ps", "logs", "events"}:
        raise ValueError("Only the approved read-only Docker operations are permitted")
    result = subprocess.run(DOCKER + command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        return {"available": False, "exit_code": result.returncode, "error": redact(result.stderr[-1000:])}
    return {"available": True, "stdout": result.stdout, "stderr": result.stderr}


def inspect_fields(cid):
    # No Config.Env, credentials, mounts or health-check output from other apps.
    template = '{"id":"{{.Id}}","name":"{{.Name}}","image":"{{.Config.Image}}","state":{{json .State}},"restart_count":{{.RestartCount}},"restart_policy":{{json .HostConfig.RestartPolicy}},"labels":{{json .Config.Labels}},"entrypoint":{{json .Config.Entrypoint}}}'
    result = read(["inspect", "--type", "container", "--format", template, cid])
    if not result["available"]:
        return result
    info = json.loads(result["stdout"])
    state = info["state"]
    return {"available": True, "id": info["id"], "name": info["name"].lstrip("/"), "image": info["image"],
            "state": {key: state.get(key) for key in ("Status", "Running", "Paused", "Restarting", "OOMKilled", "Dead", "Pid", "ExitCode", "StartedAt", "FinishedAt")},
            "error": redact(state.get("Error", ""))[:1000], "health": (state.get("Health") or {}).get("Status", "none"),
            "restart_count": info["restart_count"], "restart_policy": info["restart_policy"],
            "project": (info["labels"] or {}).get("com.docker.compose.project"),
            "trial": (info["labels"] or {}).get("io.noetharaclipz.trial"), "entrypoint": info["entrypoint"]}


def restart_findings(info, env, wrapper_matches, now):
    state = info["state"]
    stopped = (state.get("Status") == "exited" and not state.get("Running")
               and not state.get("Restarting") and state.get("Pid") == 0)
    policy = info["restart_policy"] == {"Name": "on-failure", "MaximumRetryCount": 3}
    settings = (env.get("NC_QA_STOP_AT") == str(DEADLINE) and env.get("NC_QA_TRIAL_ID") == TRIAL
                and env.get("NC_WORKER_OWNER_ID") == OWNER and env.get("NC_DEPLOY_MODE") == "qa"
                and env.get("NC_AI_PROVIDER") == "local" and env.get("GEMINI_FREE_TIER_VERIFIED") == "false"
                and env.get("NC_GLOBAL_QUEUE_APPROVED") == "false")
    finished = datetime.fromisoformat(state["FinishedAt"].replace("Z", "+00:00")).timestamp() if stopped else None
    return {"docker_container_stopped": stopped,
            "normal_exit_without_oom": stopped and state.get("ExitCode") == 0 and not state.get("OOMKilled"),
            "finished_within_approved_window": stopped and 0 < finished <= DEADLINE,
            "docker_on_failure_policy_does_not_restart_this_normal_exit": stopped and policy and state.get("ExitCode") == 0,
            "unchanged_expired_wrapper_blocks_processing_before_models_or_credentials":
                now > DEADLINE and settings and wrapper_matches and info["entrypoint"] == ["python", "/run/qa-deadline.py"],
            "root_can_explicitly_change_configuration": True}


def resource_counters():
    roots = [Path("/sys/fs/cgroup/system.slice/docker-" + CID + ".scope"), Path("/sys/fs/cgroup/docker") / CID]
    for root in roots:
        if root.is_dir():
            values = {}
            for name in ("memory.current", "memory.peak", "memory.events", "cpu.stat", "cpu.max", "memory.max", "pids.current"):
                path = root / name
                if path.is_file():
                    values[name] = path.read_text().strip()
            return {"available": bool(values), "source": str(root), "counters": values,
                    "peak_cpu_percent_available": False, "cpu_stat_is_cumulative_not_peak": True}
    return {"available": False, "peak_ram_bytes": None, "cpu_usage_seconds": None,
            "peak_cpu_percent": None, "reason": "Stopped container cgroup not retained; Docker inspect and zero stopped stats do not reconstruct historical peaks"}


def main():
    if os.geteuid() != 0 or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip() != INSTANCE:
        raise ValueError("Read only on the existing authorized EC2 host via sudo -n")
    now = int(time.time())
    report = {"checked_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(), "read_only": True,
              "worker_started_restarted_or_executed": False, "credentials_read": False, "instance": INSTANCE}
    info = inspect_fields(CID)
    report["qa_container"] = info
    if info.get("available"):
        if info["trial"] != TRIAL or info["project"] != "noetharaclipz-isolated":
            raise ValueError("Unexpected container ownership; do not inspect another app's logs")
        result = read(["inspect", "--type", "container", "--format", "{{json .Config.Env}}", CID])
        env = dict(v.split("=", 1) for v in json.loads(result["stdout"])) if result["available"] else {}
        report["safe_qa_environment"] = {key: env.get(key) for key in sorted(SAFE_ENV)}
        wrapper = Path("/etc/noetharaclipz-isolated/qa-deadline.py")
        matches = wrapper.is_file() and not wrapper.is_symlink() and hashlib.sha256(wrapper.read_bytes()).hexdigest() == WRAPPER_SHA
        if matches:
            stat = wrapper.stat()
            report["wrapper_permissions"] = {"uid": stat.st_uid, "gid": stat.st_gid, "mode": oct(stat.st_mode & 0o777)}
            matches = stat.st_uid == 0 and not stat.st_mode & 0o022
        report["deadline_wrapper_matches_reviewed_sha256"] = matches
        report["restart_findings"] = restart_findings(info, env, matches, now)
        logs = read(["logs", "--timestamps", "--tail", "150", CID])
        if logs["available"]:
            lines = (logs["stdout"] + "\n" + logs["stderr"]).splitlines()
            relevant = [redact(line)[:2500] for line in lines if any(marker in line for marker in
                ('"qa_window_stopped"', '"qa_window_expired"', '"qa_kernel_preflight"', 'watchdog failed', 'Provider startup failed'))]
            report["shutdown_logs"] = {"available": True, "selected_lines": relevant[-12:],
                "tail_lines_read": len(lines), "raw_logs_not_printed": True}
        else:
            report["shutdown_logs"] = logs
        until = datetime.fromtimestamp(now, timezone.utc).isoformat()
        events = read(["events", "--since", "2026-11-09T00:20:00Z", "--until", until,
                       "--filter", "container=" + CID, "--format", "{{json .}}"])
        if events["available"]:
            selected = []
            for line in events["stdout"].splitlines():
                event = json.loads(line)
                if event.get("Action") in ("start", "die", "stop", "kill", "restart", "oom"):
                    selected.append({"action": event["Action"], "time": event.get("time"),
                        "timeNano": event.get("timeNano"), "exitCode": event.get("Actor", {}).get("Attributes", {}).get("exitCode")})
            report["retained_lifecycle_events"] = {"events": selected, "retention_may_be_incomplete": True}
        else:
            report["retained_lifecycle_events"] = events
    report["resource_usage"] = resource_counters()
    report["existing_services"] = []
    listing = read(["ps", "--all", "--no-trunc", "--format", "{{json .}}"])
    if listing["available"]:
        rows = [json.loads(line) for line in listing["stdout"].splitlines()]
        names = {row["Names"] for row in rows}
        report["missing_expected_services"] = sorted(EXPECTED_SERVICES - names)
        for row in rows:
            if row["Names"] in EXPECTED_SERVICES:
                report["existing_services"].append(inspect_fields(row["ID"]))
    else:
        report["service_listing_error"] = listing
    services = report["existing_services"]
    report["expected_services_running_with_no_reported_health_failures"] = (
        len(services) == len(EXPECTED_SERVICES) and all(s.get("available") and s["state"].get("Running")
        and (s["health"] == "healthy" or s["name"] == "supabase_rest_wwgwnlhmbmrspmzdptzh" and s["health"] == "none") for s in services))
    report["rest_container_has_no_docker_healthcheck_in_baseline"] = True
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
