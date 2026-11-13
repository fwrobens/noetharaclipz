"""Authorized one-owner 21:00--21:30 UTC launch; no early processing approval.

Uses the already received reviewed sources and existing EC2 file credential.
Never enables boot startup or modifies existing services, network rules or jobs.
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

ROOT = Path("/tmp/nccz-continuous-pilot-0qkrd0gd")
INSTANCE = "i-0be10e530045fc650"
DEPLOYMENT = "11865b83-9836-4ff3-a99e-dfac4df71f34"
OWNER = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69"
CONSENT = "4426bdad-bc7a-4972-ace2-ae65ac3f9fa4"
START = 1794258000
STOP = 1794259800
CANDIDATE = "a2974efc290782d52d16acef2b1814548b3756908af017247dec5450d7ad29ce"
BUNDLE = "564a5b6a5de0664448737e0c5291c30a4d1ff2074be096b08711dce11fb381d8"
COLLECTOR = "7bba366d6bb5ade982feb94668e127396e043ed5a10bad50c9b4efbf21918efc"
UNIT = "noetharaclipz-continuous.service"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_authorization(payload):
    receipt, manifest = payload["authorization"], payload["manifest"]
    if (
        receipt.get("user_reply") != "yes"
        or receipt.get("candidate_sha256") != CANDIDATE
        or receipt.get("processing_approval_authorized") is not True
        or receipt.get("installation_and_start_authorized") is not True
        or manifest.get("operator_approved") is not True
        or manifest.get("approval_reference") != receipt.get("approval_reference")
        or not manifest.get("approval_reference")
        or manifest.get("deployment_id") != DEPLOYMENT
        or manifest.get("owner_id") != OWNER
        or manifest.get("consent_id") != CONSENT
        or manifest.get("not_before") != START
        or manifest.get("valid_until") != STOP
        or sha(canonical(manifest)) != payload.get("manifest_sha256")
    ):
        raise ValueError("Missing exact user authorization or active manifest")
    candidate = dict(manifest, operator_approved=False, approval_reference="")
    if sha(canonical(candidate)) != CANDIDATE:
        raise ValueError("Authorized scope changed beyond approval metadata")
    return receipt, manifest


def require_window(now):
    if not START <= now < STOP - 600:
        raise ValueError(
            "Outside approved launch window or fewer than ten minutes remain"
        )


def private_new(path, value):
    raw = (
        value
        if isinstance(value, bytes)
        else (json.dumps(value, indent=2) + "\n").encode()
    )
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def systemctl(*args):
    permitted = (("daemon-reload",), ("start", UNIT), ("stop", UNIT))
    if args not in permitted:
        raise ValueError("Unrelated systemd action refused")
    result = subprocess.run(
        ["systemctl", *args], capture_output=True, text=True, timeout=120
    )
    if result.returncode:
        raise RuntimeError("Dedicated pilot systemd action failed: " + args[0])


def main(payload):
    os.umask(0o077)
    receipt, manifest = validate_authorization(payload)
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != INSTANCE
    ):
        raise ValueError("Wrong host or execution identity")
    if ROOT.is_symlink() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o077:
        raise ValueError("Received source directory is not private root-owned")
    if sha((ROOT / "bundle.json").read_bytes()) != BUNDLE:
        raise ValueError("Received bundle hash changed")
    collector_path = ROOT / "inspect-pilot-host.py"
    if collector_path.is_symlink() or sha(collector_path.read_bytes()) != COLLECTOR:
        raise ValueError("Reviewed read-only collector changed")
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        os.environ.pop(name, None)
    if time.time() < START:
        print(
            json.dumps(
                {
                    "stage": "waiting_for_authorized_2100_window",
                    "stop_utc": "2026-11-09T21:30:00Z",
                    "processing_approval_issued": False,
                    "worker_started": False,
                }
            ),
            flush=True,
        )
    while time.time() < START:
        time.sleep(1)
    require_window(time.time())
    state_path = ROOT / "launch-2100-attempt.json"
    if state_path.exists():
        raise ValueError(
            "Launch already attempted; preserve its receipt and do not retry automatically"
        )
    sys.path.insert(0, str(ROOT / "host"))
    import reliability_platform as platform

    original_run = platform.run
    spec = importlib.util.spec_from_file_location("reviewed_collector", collector_path)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    try:
        fresh = collector.collect(ROOT, DEPLOYMENT, BUNDLE)
    finally:
        platform.run = original_run
    if not fresh["host_preparation_checks_passed"]:
        print(json.dumps({"fresh_host_preflight": fresh, "worker_started": False}))
        return
    import continuous_host as host

    host.validate_manifest(manifest, time.time())
    cfg = host.ETC / DEPLOYMENT
    data = host.DATA / DEPLOYMENT
    current = host.ETC / "current"
    unit_names = ("noetharaclipz-isolation.service", UNIT)
    if os.path.lexists(current) or any(
        os.path.lexists(Path("/etc/systemd/system") / name) for name in unit_names
    ):
        raise ValueError("Existing pilot unit/current path must not be replaced")
    api = platform.API()  # First credential-content access, after fresh security.
    protocol = api.rpc("worker_continuous_protocol")
    if protocol.get("version") != 2 or protocol.get("global_claim") is not False:
        raise ValueError("Wrong server consent protocol")
    row = api.rows("processing_jobs", id="eq.9c5c8869-ec2e-4a3e-927d-697615bb58a3")[0]
    if (
        sha(json.dumps(row, sort_keys=True).encode())
        != "deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb"
    ):
        raise ValueError("Protected upload changed")
    status = api.rpc("worker_consent_status", owner=OWNER, consent=CONSENT)
    if status.get("authorized") or status.get("approved_at") is not None:
        raise ValueError("Approval already exists; never reset or duplicate it")
    require_window(time.time())
    private_new(
        state_path,
        {
            "stage": "approval_about_to_be_requested",
            "manifest_sha256": payload["manifest_sha256"],
            "utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    approval = api.rpc(
        "approve_processing_consent",
        owner=OWNER,
        consent=CONSENT,
        expires_at="2026-11-09T21:30:00+00:00",
        reason=receipt["approval_reference"],
    )
    private_new(ROOT / "processing-approval-2100.json", approval)
    if (
        approval.get("consent_id") != CONSENT
        or datetime.fromisoformat(approval["expires_at"]).timestamp() != STOP
    ):
        raise ValueError("Unexpected processing approval")
    active_path = ROOT / "active-manifest-2100.json"
    private_new(active_path, canonical(manifest))
    private_new(ROOT / "user-authorization-2100.json", receipt)
    installation = host.install(ROOT / "bundle.json", active_path)
    private_new(data / "reports/installation-2100.json", installation)
    private_new(data / "reports/user-authorization.json", receipt)
    os.symlink(str(cfg), current)
    for name in unit_names:
        source = cfg / "systemd" / name
        if sha(source.read_bytes()) != manifest["unit_sha256"][name]:
            raise ValueError("Installed unit hash changed")
        target = Path("/etc/systemd/system") / name
        with os.fdopen(
            os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644
            ),
            "wb",
        ) as stream:
            stream.write(source.read_bytes())
        target.chmod(0o644)
    # Ensure the reviewed service's runtime lock mount exists without replacing
    # or truncating a lock used by Docker/iptables.
    lock = os.open("/run/xtables.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.close(lock)
    require_window(time.time())
    systemctl("daemon-reload")
    try:
        systemctl("start", UNIT)
        private_new(
            data / "reports/launch-requested.json",
            {
                "at": time.time(),
                "stop_at": STOP,
                "manifest_sha256": payload["manifest_sha256"],
            },
        )
        until = min(time.time() + 55, STOP - 30)
        status = {}
        while time.time() < until:
            file = data / "reports/status.json"
            if file.exists():
                status = json.loads(file.read_text())
            if status.get("ai_ready") or status.get("stage", "").startswith("blocked"):
                break
            time.sleep(1)
        proofs = [
            json.loads(file.read_text())
            for file in (data / "reports").glob("network-*.json")
            if file.name != "network-attempt.json"
        ]
        print(
            json.dumps(
                {
                    "launch_requested": True,
                    "deployment_id": DEPLOYMENT,
                    "manifest_sha256": payload["manifest_sha256"],
                    "processing_approval_issued": True,
                    "fixed_stop_utc": "2026-11-09T21:30:00Z",
                    "status": status,
                    "generation_proofs": proofs,
                    "global_processing": False,
                    "gemini_enabled": False,
                    "existing_services_unchanged": platform.service_snapshot(
                        excluded=json.loads(
                            (data / "reports/container.json").read_text()
                        )["id"]
                    )
                    == fresh["existing_services"],
                },
                indent=2,
            ),
            flush=True,
        )
    except Exception:
        (cfg / "gates/grant.json").unlink(missing_ok=True)
        host.atomic(data / "revoked.json", {"launch_failure": True, "at": time.time()})
        systemctl("stop", UNIT)
        raise


if __name__ == "__main__":
    try:
        main(LAUNCH)  # noqa: F821 -- supplied by verified private bootstrap
    except Exception as error:
        print(
            json.dumps(
                {
                    "launch_failed": True,
                    "error_type": type(error).__name__,
                    "details": str(error)[:220],
                    "deadline_extended": False,
                }
            ),
            flush=True,
        )
        raise SystemExit(1) from None
