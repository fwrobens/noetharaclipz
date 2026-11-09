"""Gated installation and detached systemd start for one reviewed 24h pilot.

Preparation is not approval. A separate private immutable authorization record
must be issued following the user's explicit approval of the exact plan/hash.
Missing approval returns without installing files or requesting processing.
This helper never runs/monitors a worker as a shell child, enables boot startup,
changes networking, rewrites old evidence or releases any existing queued job.
"""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
from uuid import UUID

OWNER = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69"
OLD_CONSENT = "4426bdad-bc7a-4972-ace2-ae65ac3f9fa4"
PREVIOUS = "11865b83-9836-4ff3-a99e-dfac4df71f34"
SOURCE_SHA = "564a5b6a5de0664448737e0c5291c30a4d1ff2074be096b08711dce11fb381d8"
PROTECTED = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"
PROTECTED_SHA = "deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb"
UNIT = "noetharaclipz-continuous.service"
ISOLATION = "noetharaclipz-isolation.service"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_plan(plan):
    candidate = plan["manifest_candidate"]
    for key in ("deployment_id", "owner_id", "consent_id"):
        if str(UUID(candidate[key])) != candidate[key]:
            raise ValueError("Canonical pilot identifiers required")
    reference = plan.get("approval_reference", "")
    if (
        plan.get("format") != "nccz-24h-reviewed-plan-v1"
        or candidate["deployment_id"] == PREVIOUS
        or candidate["owner_id"] != OWNER
        or candidate["consent_id"] == OLD_CONSENT
        or candidate.get("operator_approved") is not False
        or candidate.get("approval_reference") != ""
        or candidate["valid_until"] - candidate["not_before"] != 86400
        or candidate.get("restore_isolation") is not False
        or candidate.get("memory_bytes") != 8 * 1024**3
        or candidate.get("cpus") != 2
        or candidate.get("active_jobs") != 1
        or candidate.get("global_processing") is not False
        or candidate.get("gemini_enabled") is not False
        or candidate.get("image")
        != "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
        or candidate.get("model") != "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
        or plan.get("boot_start_authorized") is not False
        or plan.get("systemd_only") is not True
        or not 1 <= len(reference.strip()) <= 300
        or sha(canonical(candidate)) != plan.get("candidate_sha256")
        or not re.fullmatch(
            r"_worker-transfer/[0-9a-f-]{36}/24h-operator-authorization-"
            + re.escape(candidate["deployment_id"])
            + r"\.json",
            plan.get("authorization_object", ""),
        )
    ):
        raise ValueError("Unsafe, stale or changed 24h review plan")
    active = dict(candidate, operator_approved=True, approval_reference=reference)
    if sha(canonical(active)) != plan.get("activation_manifest_sha256"):
        raise ValueError("Prospective activation manifest hash changed")
    return active


def require_window(manifest, now):
    # A late launch is not a successful 24-hour trial. Never shift the deadline.
    if not manifest["not_before"] <= now < manifest["not_before"] + 300:
        raise ValueError(
            "Launch only in the reviewed first five minutes; no shell wait or deadline extension"
        )


def validate_authorization(receipt, plan):
    candidate = plan["manifest_candidate"]
    if (
        receipt.get("format") != "nccz-24h-operator-authorization-v1"
        or receipt.get("deployment_id") != candidate["deployment_id"]
        or receipt.get("owner_id") != candidate["owner_id"]
        or receipt.get("consent_id") != candidate["consent_id"]
        or receipt.get("candidate_sha256") != plan["candidate_sha256"]
        or receipt.get("manifest_sha256") != plan["activation_manifest_sha256"]
        or receipt.get("approval_reference") != plan["approval_reference"]
        or receipt.get("not_before") != candidate["not_before"]
        or receipt.get("valid_until") != candidate["valid_until"]
        or receipt.get("processing_approval_authorized") is not True
        or receipt.get("installation_and_start_authorized") is not True
        or receipt.get("boot_start_authorized") is not False
        or receipt.get("global_processing") is not False
        or not receipt.get("explicit_user_reply", "").strip()
        or not receipt.get("authorized_at_utc")
    ):
        raise ValueError(
            "Separate explicit authorization of this exact scope is required"
        )


def private_new(path, value):
    raw = value if isinstance(value, bytes) else canonical(value)
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def verify_preparation(root, plan):
    if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ValueError("Received preparation must be private and root-owned")
    raw = (root / "preparation.json").read_bytes()
    if sha(raw) != plan["preparation_sha256"]:
        raise ValueError("Received preparation identity changed")
    payload = json.loads(raw)
    candidate = plan["manifest_candidate"]
    if (
        payload.get("deployment_id") != candidate["deployment_id"]
        or payload.get("owner_id") != candidate["owner_id"]
        or payload.get("operator_approved") is not False
        or sha((root / "bundle.json").read_bytes()) != SOURCE_SHA
    ):
        raise ValueError("Wrong received deployment/source bundle")
    for name, expected in payload["helper_sha256"].items():
        path = root / "handoff" / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or path.stat().st_uid != 0
            or path.stat().st_mode & 0o022
            or sha(path.read_bytes()) != expected
        ):
            raise ValueError("Received admission helper changed")
    bundle = json.loads((root / "bundle.json").read_text())
    if (
        candidate["files"] != bundle["sha256"]
        or candidate["unit_sha256"] != bundle["unit_sha256"]
        or candidate["source_commit"] != bundle["source_commit"]
    ):
        raise ValueError("Review plan does not match the reviewed runtime")


def unit_action(*args):
    if args not in (("stop", ISOLATION), ("stop", UNIT), ("start", "--no-block", UNIT)):
        raise ValueError("Only dedicated pilot systemd actions are allowed")
    result = subprocess.run(
        ["systemctl", *args], capture_output=True, text=True, timeout=120
    )
    if result.returncode:
        raise RuntimeError("Dedicated pilot systemd action failed: " + args[0])


def select_current(current, expected, target, deployment):
    if not current.is_symlink() or current.resolve() != expected:
        raise ValueError("Current deployment changed; refuse handover")
    temporary = current.with_name("current-" + deployment + ".pending")
    os.symlink(str(target), temporary)
    os.replace(temporary, current)


def read_authorization(api, plan):
    try:
        return api.call(
            "/storage/v1/object/authenticated/processing-artifacts/"
            + plan["authorization_object"]
        )
    except urllib.error.HTTPError as error:
        if error.code in (400, 404):
            # Nothing is installed or approved on a missing/invalid receipt.
            return None
        raise


def activate(root, plan, receipt, manifest, host, api, fresh):
    """Called only after every review/security gate; safe scoped rollback on error."""
    validate_authorization(receipt, plan)
    require_window(manifest, time.time())
    deployment = manifest["deployment_id"]
    cfg, data = host.ETC / deployment, host.DATA / deployment
    current, previous_cfg = host.ETC / "current", host.ETC / PREVIOUS
    attempt = root / "launch-attempt.json"
    private_new(
        attempt,
        {
            "manifest_sha256": plan["activation_manifest_sha256"],
            "at": time.time(),
            "authorization_sha256": sha(canonical(receipt)),
        },
    )
    selected = False
    approved = False
    try:
        active = root / "approved-manifest.json"
        private_new(active, canonical(manifest))
        private_new(root / "user-authorization.json", receipt)
        installation = host.install(root / "bundle.json", active)
        private_new(data / "reports/installation.json", installation)
        private_new(data / "reports/user-authorization.json", receipt)
        private_new(data / "reports/admission.json", fresh)
        # Only the old worker's harmless RemainAfterExit isolation check is
        # stopped. The continuous worker is already inactive. No old worker or
        # shared application is restarted and no installed unit text is edited.
        unit_action("stop", ISOLATION)
        select_current(current, previous_cfg, cfg, deployment)
        selected = True
        require_window(manifest, time.time())
        expiry = datetime.fromtimestamp(
            manifest["valid_until"], timezone.utc
        ).isoformat()
        approval = api.rpc(
            "approve_processing_consent",
            owner=OWNER,
            consent=manifest["consent_id"],
            expires_at=expiry,
            reason=plan["approval_reference"],
        )
        approved = True
        private_new(data / "reports/processing-approval.json", approval)
        if (
            approval.get("owner_id") != OWNER
            or approval.get("consent_id") != manifest["consent_id"]
            or datetime.fromisoformat(approval["expires_at"]).timestamp()
            != manifest["valid_until"]
        ):
            raise ValueError("Unexpected operator approval response")
        # Persist first; systemd (not this SSM process) owns all subsequent
        # execution, restart/backoff, monitoring, sampling and deadline shutdown.
        private_new(
            data / "reports/launch-requested.json",
            {
                "at": time.time(),
                "manifest_sha256": plan["activation_manifest_sha256"],
                "stop_at": manifest["valid_until"],
                "boot_enabled": False,
                "ssm_required_after_start": False,
            },
        )
        require_window(manifest, time.time())
        unit_action("start", "--no-block", UNIT)
        return {
            "launch_requested": True,
            "readiness_verified": False,
            "systemd_detached": True,
            "deployment_id": deployment,
            "manifest_sha256": plan["activation_manifest_sha256"],
            "fixed_stop_utc": expiry,
            "unit": UNIT,
            "boot_enabled": False,
            "global_processing": False,
            "gemini_enabled": False,
            "reports_directory": str(data / "reports"),
            "next": "Use the read-only status collector after reconnecting; no terminal keepalive is needed.",
        }
    except Exception:
        cleanup_errors = []
        if data.exists():
            try:
                host.atomic(
                    data / "revoked.json", {"launch_failure": True, "at": time.time()}
                )
            except Exception as error:
                cleanup_errors.append("local_revocation:" + type(error).__name__)
            try:
                (cfg / "gates/grant.json").unlink(missing_ok=True)
            except Exception as error:
                cleanup_errors.append("grant_removal:" + type(error).__name__)
        if selected:
            stopped = True
            for unit in (UNIT, ISOLATION):
                try:
                    unit_action("stop", unit)
                except Exception as error:
                    stopped = False
                    cleanup_errors.append(type(error).__name__)
            if stopped:
                try:
                    select_current(current, cfg, previous_cfg, deployment + "-rollback")
                except Exception as error:
                    cleanup_errors.append("pointer_restore:" + type(error).__name__)
        if approved:
            try:
                api.rpc(
                    "revoke_owner_processing",
                    owner=OWNER,
                    consent=manifest["consent_id"],
                    reason="24h pilot startup failed; preserve evidence; no automatic retry",
                )
            except Exception as error:
                cleanup_errors.append(type(error).__name__)
        failure = {
            "at": time.time(),
            "cleanup_errors": cleanup_errors,
            "worker_restart_authorized": False,
            "deadline_extended": False,
        }
        try:
            private_new(root / "launch-failure.json", failure)
        except OSError:
            # A full/read-only filesystem must not prevent stop/revocation.
            print(json.dumps({"launch_cleanup": failure}), flush=True)
        raise


def main(payload):
    os.umask(0o077)
    plan = payload["plan"]
    manifest = validate_plan(plan)
    deployment = manifest["deployment_id"]
    root = Path("/var/tmp") / ("nccz-24h-" + deployment)
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != "i-0be10e530045fc650"
    ):
        raise ValueError("Wrong host or execution identity")
    verify_preparation(root, plan)
    require_window(manifest, time.time())
    if os.path.lexists(root / "launch-attempt.json"):
        raise ValueError(
            "Launch already attempted; preserve records; never retry automatically"
        )
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        os.environ.pop(key, None)
    sys.path.insert(0, str(root / "handoff"))
    spec = importlib.util.spec_from_file_location(
        "verified_24h_admission", root / "handoff/inspect_continuous_24h_host.py"
    )
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    fresh = collector.collect(root, deployment, SOURCE_SHA)
    before = json.loads((root / "host-preflight.json").read_text())
    if (
        not fresh["host_preparation_checks_passed"]
        or not before["host_preparation_checks_passed"]
        or fresh["existing_services"] != before["existing_services"]
        or fresh["previous_evidence"] != before["previous_evidence"]
        or fresh["firewall_fingerprint"] != before["firewall_fingerprint"]
    ):
        raise ValueError(
            "Fresh admission or preserved evidence does not match the reviewed host"
        )
    sys.path.insert(0, str(root / "host"))
    import continuous_host as host
    import reliability_platform as platform

    host.validate_manifest(manifest, time.time())
    api = platform.API()  # First credential read, after fresh host/security checks.
    receipt = read_authorization(api, plan)
    if receipt is None:
        print(
            json.dumps(
                {
                    "stage": "awaiting_separate_manifest_and_installation_approval",
                    "worker_started": False,
                    "processing_approval_issued": False,
                    "units_installed_or_changed": False,
                }
            )
        )
        return
    validate_authorization(receipt, plan)
    protocol = api.rpc("worker_continuous_protocol")
    if (
        protocol.get("version") != 2
        or protocol.get("contract") != "future-jobs-only-v1"
        or protocol.get("provider") != "local-smolvlm2"
        or protocol.get("global_claim") is not False
        or any(
            protocol.get(k) is not True
            for k in ("future_jobs_only", "revocable", "job_exclusions", "audit")
        )
    ):
        raise ValueError("Wrong deployed consent protocol")
    rows = api.rows("processing_jobs", id="eq." + PROTECTED)
    if (
        len(rows) != 1
        or sha(json.dumps(rows[0], sort_keys=True).encode()) != PROTECTED_SHA
    ):
        raise ValueError(
            "Protected upload changed; no processing approval will be requested"
        )
    if api.rows(
        "processing_jobs",
        select="id",
        lease_token="not.is.null",
        lease_expires_at="gt." + datetime.now(timezone.utc).isoformat(),
    ):
        raise ValueError("Active leases exist; no concurrent worker may be started")
    status = api.rpc(
        "worker_consent_status", owner=OWNER, consent=manifest["consent_id"]
    )
    if status.get("authorized") or status.get("approved_at") is not None:
        raise ValueError("This consent is already approved; do not reset or reuse it")
    result = activate(root, plan, receipt, manifest, host, api, fresh)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main(LAUNCH)  # noqa: F821 -- supplied by the hash-verified private bootstrap
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
