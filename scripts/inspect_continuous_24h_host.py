"""Read-only admission for a new 24h pilot following the closed 30m pilot.

No container execution, credential contents, queue operations, unit changes or
network mutations. The old collector and reviewed runtime are hash-verified by
the preparation receiver before importing this module.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import inspect_continuous_pilot_host as admission

PREVIOUS = "11865b83-9836-4ff3-a99e-dfac4df71f34"
PREVIOUS_SHA = "0903df1cfcb68f120877ca1088f4608584bc1bddebbb1b9b4ddb41725ec3792f"
PREVIOUS_CID = "bc1b8b921156a9bf52db5483dc012549f9f43daedb391bcc95a4dc954a557aac"
ETC = Path("/etc/noetharaclipz-isolated/continuous")
DATA = Path("/var/lib/noetharaclipz-isolated/continuous")
UNIT_DIR = Path("/etc/systemd/system")
UNITS = ("noetharaclipz-isolation.service", "noetharaclipz-continuous.service")
SERVICE_IDS = {
    "3c1d7f471d1bbcf0693826ded3908f63190d33556e99d5b7c604b17610eda56a",
    "9168f3846a6709c2661447393dd00a269389818c9a0bfeffc1a16175263d15e3",
    "20f1292598a0adf47cd0c656889a3c80d269080f70bc3df8502036f9c116bcd7",
    "c8486407222d9c6262343641156de583efa7b2696abacad54f3c4edf6fa14d25",
    "37221a93ce4da260b6f06bd464e431700b6be3acfc28dc8682897b179346b0ab",
    "a53220a17ba9defd7a4a4635e93ce16651e696528660427117d32abb03850d4b",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def file_digest(path, allowed_root):
    resolved = path.resolve(strict=True)
    if (
        not resolved.is_relative_to(allowed_root.resolve(strict=True))
        or not resolved.is_file()
    ):
        raise ValueError("Model asset resolves outside its dedicated directory")
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for block in iter(lambda: stream.read(2 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def model_weights(models):
    # Public pinned-revision LFS SHA256 values, checked against HF metadata.
    files = {
        "smolvlm2_500m": (
            models
            / "huggingface/hub/models--HuggingFaceTB--SmolVLM2-500M-Video-Instruct"
            / "snapshots/7b375e1b73b11138ff12fe22c8f2822d8fe03467/model.safetensors",
            "b9bfd456c9472c0acd5719d6e514c4b859891af205ee1a736552fd3497b8b0c3",
        ),
        "whisper_small": (
            models / "whisper-small/model.bin",
            "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
        ),
    }
    return {
        name: {"sha256": file_digest(path, models), "expected_sha256": expected}
        for name, (path, expected) in files.items()
    }


def command_allowed(command):
    return (
        admission.command_allowed(command)
        or any(
            command == ["systemctl", action, unit]
            for action in ("is-active", "is-enabled")
            for unit in UNITS
        )
        or any(command == ["systemctl", "show", unit] for unit in UNITS)
    )


def read_command(command, timeout=30):
    if not command_allowed(command):
        raise ValueError("24h collector prohibits this command")
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode and command[0] != "systemctl":
        raise RuntimeError("Read-only host check failed: " + " ".join(command[:4]))
    return result.stdout.strip()


def retained_evidence():
    """Only old immutable config and reports; never cache/media or credentials."""
    roots = [ETC / PREVIOUS / name for name in ("code", "public", "systemd")]
    roots += [DATA / PREVIOUS / "reports"]
    hashes = {}
    for root in roots:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Previous evidence path changed")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlink in previous evidence")
            if path.is_file():
                if path.stat().st_size > 25 * 1024**2:
                    raise ValueError("Unexpectedly large previous evidence file")
                hashes[str(path)] = sha(path.read_bytes())
    return {"files": len(hashes), "sha256": sha(canonical(hashes))}


def unit_state(unit, expected):
    path = UNIT_DIR / unit
    info = path.lstat()
    pinned = (
        not path.is_symlink()
        and info.st_uid == 0
        and not info.st_mode & 0o022
        and sha(path.read_bytes()) == expected
    )
    properties = dict(
        line.split("=", 1)
        for line in read_command(["systemctl", "show", unit]).splitlines()
        if "=" in line
    )
    return {
        "active": read_command(["systemctl", "is-active", unit]),
        "enabled": read_command(["systemctl", "is-enabled", unit]),
        "pinned_unit_file": pinned,
        "fragment_path": properties.get("FragmentPath"),
        "drop_in_paths": properties.get("DropInPaths"),
        "need_daemon_reload": properties.get("NeedDaemonReload"),
        "loaded_reviewed_unit": pinned
        and properties.get("FragmentPath") == str(path)
        and properties.get("DropInPaths") == ""
        and properties.get("NeedDaemonReload") == "no",
    }


def collect(root, deployment, bundle_sha):
    if deployment == PREVIOUS:
        raise ValueError("A distinct new deployment is required")
    bundle = admission.verify_sources(root, bundle_sha)
    sys.path.insert(0, str(root / "host"))
    import reliability_platform as platform

    original_command = admission.read_command
    original_run = platform.run
    admission.read_command = read_command
    platform.run = read_command
    try:
        report = admission.collect(root, deployment, bundle_sha)
        import continuous_host as host

        weights = model_weights(platform.MODELS)
        old_manifest, old_cfg, old_data = host.load(
            ETC / PREVIOUS / "public/manifest.json", active=False
        )
        current = ETC / "current"
        raw = read_command(
            admission.DOCKER
            + [
                "inspect",
                "--format",
                "{{json .State}}|{{.RestartCount}}|{{json .HostConfig.RestartPolicy}}",
                PREVIOUS_CID,
            ]
        )
        state, count, policy = raw.rsplit("|", 2)
        state, policy = json.loads(state), json.loads(policy)
        safe_state = {
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
        }
        safe_state.update(restart_count=int(count), restart_policy=policy)
        units = {
            name: unit_state(name, expected)
            for name, expected in bundle["unit_sha256"].items()
        }
        status = json.loads((old_data / "reports/status.json").read_text())
        before = retained_evidence()
        report["checks"].update(
            {
                "previous_manifest_expired_and_unchanged": sha(canonical(old_manifest))
                == PREVIOUS_SHA
                and old_manifest["valid_until"]
                < datetime.now(timezone.utc).timestamp(),
                "current_points_only_to_closed_previous_deployment": current.is_symlink()
                and current.resolve() == old_cfg,
                "previous_processing_grant_absent": not os.path.lexists(
                    old_cfg / "gates/grant.json"
                ),
                "previous_continuous_container_exited_normally": state.get("Status")
                == "exited"
                and state.get("Running") is False
                and state.get("Restarting") is False
                and state.get("ExitCode") == 0
                and state.get("OOMKilled") is False
                and count == "0"
                and policy == {"Name": "no", "MaximumRetryCount": 0},
                "previous_controller_closed": status.get("stage") == "closed"
                and status.get("global_processing") is False,
                "both_units_loaded_from_reviewed_files": all(
                    v["loaded_reviewed_unit"] for v in units.values()
                ),
                "both_units_disabled_at_boot": all(
                    v["enabled"] == "disabled" for v in units.values()
                ),
                "expected_six_existing_services": {
                    v["id"] for v in report["existing_services"]
                }
                == SERVICE_IDS,
                "pinned_model_weight_hashes": all(
                    v["sha256"] == v["expected_sha256"] for v in weights.values()
                ),
                "previous_evidence_unchanged_during_collection": before
                == retained_evidence(),
            }
        )
        report.update(
            {
                "checked_utc": datetime.now(timezone.utc).isoformat(),
                "host_preparation_checks_passed": all(report["checks"].values()),
                "previous_deployment_id": PREVIOUS,
                "previous_manifest_sha256": PREVIOUS_SHA,
                "previous_continuous_container": safe_state,
                "previous_evidence": before,
                "model_weights": weights,
                "reviewed_units": units,
                "boot_start_authorized": False,
                "ssm_required_after_start": False,
                "pending": [
                    "Fresh owner consent and exact 24-hour manifest/window review",
                    "Separate operator approval of installation and detached systemd startup",
                    "Fresh kernel quotas and live scoped denial proofs on each worker generation",
                ],
            }
        )
        return report
    finally:
        admission.read_command = original_command
        platform.run = original_run
