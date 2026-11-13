"""Seal an inert two-hour review packet. No network or approval/start operation.

Fresh consent is supplied only after an explicit owner response and native
authenticated request. Computes prospective activation hashes for review but
never writes an active manifest or issues a processing approval.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_continuous_bundle import collect, IMAGE, CONFIG  # noqa: E402

OWNER = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69"
EXPIRED_CONSENT = "6b13bb7a-5b9b-4564-80d8-3904872d8c01"
PROTECTED_JOB = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def consent_valid(receipt):
    row = receipt.get("consent", {})
    return (
        receipt.get("explicit_owner_consent") is True
        and receipt.get("authenticated_role") == "authenticated"
        and row.get("owner_id") == OWNER
        and row.get("consent_id") not in (None, EXPIRED_CONSENT)
        and bool(row.get("requested_at"))
        and row.get("terms_version") == "local-video-v1"
        and row.get("approved_at") is None
        and row.get("revoked_at") is None
        and row.get("expires_at") is None
    )


def prepare(build, receipt, start, now, access_sha, deployment, media):
    if (
        not consent_valid(receipt)
        or build.get("source_dirty") is not False
        or build.get("release_eligible") is not True
        or not now + 3600 <= start < now + 6 * 86400
        or len(access_sha) != 64
        or any(c not in "0123456789abcdef" for c in access_sha)
    ):
        raise ValueError(
            "Fresh unapproved owner consent, clean build and future reviewed window required"
        )
    files = collect()
    baseline = json.loads(
        (ROOT / "docs/evidence/continuous-24h-manifest-candidate.json").read_text()
    )
    hashes = {name: sha(source.encode()) for name, source in files.items()}
    if hashes != baseline["files"]:
        raise ValueError(
            "Previously reviewed worker runtime changed; verification required"
        )
    units = {
        p.name: p.read_text()
        for p in (ROOT / "deploy/worker/systemd").glob("*.service")
    }
    unit_hashes = {name: sha(source.encode()) for name, source in units.items()}
    if unit_hashes != baseline["unit_sha256"]:
        raise ValueError("Previously reviewed worker units changed")
    corpus_raw = (ROOT / "docs/evidence/beta-corpus-preparation.json").read_bytes()
    corpus = json.loads(corpus_raw)
    samples = corpus["samples"]
    if len(samples) != 6 or {s["id"] for s in samples} != set("ABCDEF"):
        raise ValueError("Exactly the six reviewed samples are required")
    for sample in samples:
        raw = (media / sample["file"]).read_bytes()
        if sha(raw) != sample["sha256"] or len(raw) != sample["bytes"]:
            raise ValueError("Reviewed sample bytes missing or changed")
    m = {
        "schema": 1,
        "deployment_id": deployment,
        "owner_id": OWNER,
        "consent_id": receipt["consent"]["consent_id"],
        "operator_approved": False,
        "approval_reference": "beta-two-hour-review-" + deployment,
        "not_before": start,
        "valid_until": start + 7200,
        "image": IMAGE,
        "model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
        "memory_bytes": 8 * 1024**3,
        "cpus": 2,
        "active_jobs": 1,
        "global_processing": False,
        "gemini_enabled": False,
        "restore_isolation": False,
        "source_commit": build["source_commit"],
        "files": hashes,
        "unit_sha256": unit_hashes,
        "boot_start": False,
        "frontend_origin": "https://noetharaclipz.lovable.app",
        "frontend_build": build["source_commit"],
        "frontend_artifact_sha256": build["artifact_sha256"],
        "frontend_access_sha256": access_sha,
        "alert_mode": "operator-attended-local-log-only",
        "workload": {
            "corpus_receipt_sha256": sha(corpus_raw),
            "samples": [
                {k: s[k] for k in ("id", "file", "sha256", "bytes", "at_minute")}
                for s in samples
            ],
            "cancellation_sample": "D",
            "one_proposed_worker_only_fault_sample": "E",
            "permanently_excluded_job": PROTECTED_JOB,
            "input_hash_enforcement": "Reviewed test runner; deployed queue remains owner/future-job scoped",
        },
    }
    prospective = {**m, "operator_approved": True}
    active_sha = sha(canonical(prospective))
    watchdog = {
        "schema": 1,
        "operator_approved": False,
        "deployment_id": deployment,
        "manifest_sha256": active_sha,
        "delivery_enabled": False,
        "destination_file": "/etc/noetharaclipz-isolated/beta-webhook",
        "destination_host": None,
        "destination_sha256": None,
        "payload_format": "generic",
    }
    review = {
        "deployment_id": deployment,
        "owner_id": OWNER,
        "consent_id": m["consent_id"],
        "status": "owner_consented_operator_unapproved",
        "manifest_candidate_sha256": sha(canonical(m)),
        "prospective_active_manifest_sha256": active_sha,
        "window_utc": {
            "start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
            "stop": datetime.fromtimestamp(start + 7200, timezone.utc).isoformat(),
        },
        "watchdog_candidate_sha256": sha(canonical(watchdog)),
        "prospective_active_watchdog_sha256": sha(
            canonical({**watchdog, "operator_approved": True})
        ),
        "watchdog_source_sha256": sha((ROOT / "deploy/beta/watchdog.py").read_bytes()),
        "watchdog_unit_sha256": sha(
            (ROOT / "deploy/beta/noetharaclipz-beta-alerts@.service").read_bytes()
        ),
        "alert_proposal_sha256": sha(
            (ROOT / "deploy/beta/alert-delivery-proposal.json").read_bytes()
        ),
        "frontend_build": build["source_commit"],
        "frontend_artifact_sha256": build["artifact_sha256"],
        "frontend_access_sha256": access_sha,
        "corpus_receipt_sha256": sha(corpus_raw),
        "host_preflight_passed": False,
        "publication_authorized": False,
        "monitoring_install_authorized": False,
        "operator_attended_authorized": False,
        "processing_approval_issued": False,
        "worker_start_authorized": False,
        "fault_injection_authorized": False,
        "rollback_revision_verified": False,
    }
    bundle = {
        "format": "nccz-continuous-source-v1",
        "base_image": IMAGE,
        "base_image_config": CONFIG,
        "source_commit": build["source_commit"],
        "source_dirty": False,
        "sha256": hashes,
        "files": files,
        "units": units,
        "unit_sha256": unit_hashes,
    }
    return m, watchdog, review, bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--owner-consent", type=Path, required=True)
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--access-sha256", required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deployment-id", default=None)
    args = parser.parse_args()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        raise ValueError("Commit preparation source before sealing")
    build = json.loads(args.build.read_text())
    if (
        build["source_commit"]
        != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip()
    ):
        raise ValueError(
            "Reseal the current production source before preparing its manifest"
        )
    start = datetime.fromisoformat(args.start_utc.replace("Z", "+00:00"))
    if start.utcoffset().total_seconds() != 0:
        raise ValueError("Explicit UTC window required")
    deployment = args.deployment_id or str(uuid4())
    if (
        str(UUID(deployment)) != deployment
        or deployment == "c25d8492-56fb-4c56-a519-e9a9e4246525"
    ):
        raise ValueError("New canonical beta deployment ID required")
    packet = prepare(
        build,
        json.loads(args.owner_consent.read_text()),
        int(start.timestamp()),
        time.time(),
        args.access_sha256,
        deployment,
        args.media,
    )
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, value in zip(
        (
            "manifest-candidate.json",
            "watchdog-candidate.json",
            "review.json",
            "bundle.json",
        ),
        packet,
    ):
        (args.output / name).write_bytes(canonical(value))
    print(json.dumps(packet[2], indent=2))


if __name__ == "__main__":
    main()
