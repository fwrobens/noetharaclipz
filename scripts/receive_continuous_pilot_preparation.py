"""Receive the existing private handoff and run its unchanged read-only collector.

No operator approval, credential read, queue access, unit installation, firewall
change or container execution. Only new private temporary preparation files.
The small signed bootstrap supplies HANDOFF; no URL is embedded in this source.
"""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.parse
import urllib.request

INSTANCE = "i-0be10e530045fc650"
DEPLOYMENT = "11865b83-9836-4ff3-a99e-dfac4df71f34"
OWNER = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69"
CONSENT = "4426bdad-bc7a-4972-ace2-ae65ac3f9fa4"
HANDOFF_SHA = "0a30367d6040d53dceec7632000a0b1b48caa5d2178e75f52f098955c06a700e"
BUNDLE_SHA = "564a5b6a5de0664448737e0c5291c30a4d1ff2074be096b08711dce11fb381d8"
COLLECTOR_SHA = "7bba366d6bb5ade982feb94668e127396e043ed5a10bad50c9b4efbf21918efc"
MANIFEST_SHA = "736b72c902eae0b65d251db69d15dedfe38e5e5b105b71849b3469c702d90d73"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_payload(raw):
    if sha(raw) != HANDOFF_SHA:
        raise ValueError("Existing private handoff hash mismatch")
    payload = json.loads(raw)
    if (
        payload.get("format") != "nccz-continuous-pilot-preparation-v1"
        or payload.get("deployment_id") != DEPLOYMENT
        or payload.get("owner_id") != OWNER
        or payload.get("worker_start_authorized") is not False
        or sha(payload["source_bundle_json"].encode()) != BUNDLE_SHA
        or sha(payload["collector"].encode()) != COLLECTOR_SHA
        or sha(canonical(payload["manifest_proposal"])) != MANIFEST_SHA
    ):
        raise ValueError("Unreviewed source, collector or disabled proposal")
    bundle = json.loads(payload["source_bundle_json"])
    manifest = payload["manifest_proposal"]
    approval = payload["operator_approval_proposal"]
    if (
        manifest.get("operator_approved") is not False
        or manifest.get("valid_until") != 0
        or manifest.get("consent_id") != CONSENT
        or bundle.get("source_dirty") is not False
        or bundle.get("sha256") != manifest.get("files")
        or bundle.get("unit_sha256") != manifest.get("unit_sha256")
        or set(bundle["files"]) != set(bundle["sha256"])
        or set(bundle["units"]) != set(bundle["unit_sha256"])
        or approval.get("operator_approved") is not False
        or approval.get("worker_start_authorized") is not False
    ):
        raise ValueError("Preparation must remain disabled and unapproved")
    for name, source in bundle["files"].items():
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or not name.endswith(".py")
            or path.parts[0] not in ("host", "worker", "runtime")
            or sha(source.encode()) != bundle["sha256"][name]
        ):
            raise ValueError("Unsafe or changed source path")
    for name, source in bundle["units"].items():
        if (
            name
            not in (
                "noetharaclipz-isolation.service",
                "noetharaclipz-continuous.service",
            )
            or sha(source.encode()) != bundle["unit_sha256"][name]
        ):
            raise ValueError("Unreviewed unit text")
    return payload, bundle


def write_new(path, value):
    raw = (
        value
        if isinstance(value, bytes)
        else (json.dumps(value, indent=2) + "\n").encode()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(handoff):
    os.umask(0o077)
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != INSTANCE
    ):
        raise ValueError(
            "Preparation receiver requires the existing authorized EC2 host"
        )
    url = urllib.parse.urlsplit(handoff["handoff_url"])
    if (
        url.scheme != "https"
        or url.hostname != "zxdnjnsghdnviflahvry.supabase.co"
        or url.username
        or url.password
        or not url.path.startswith(
            "/storage/v1/object/sign/processing-artifacts/_worker-transfer/"
        )
    ):
        raise ValueError("Wrong private handoff destination")
    with urllib.request.urlopen(handoff["handoff_url"], timeout=30) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Private handoff size limit exceeded")
    payload, bundle = validate_payload(raw)
    root = Path(tempfile.mkdtemp(prefix="nccz-continuous-pilot-"))
    write_new(root / "bundle.json", payload["source_bundle_json"].encode())
    write_new(root / "manifest-proposal.json", canonical(payload["manifest_proposal"]))
    write_new(
        root / "operator-approval-proposal.json", payload["operator_approval_proposal"]
    )
    for name, source in bundle["files"].items():
        write_new(root / name, source.encode())
    for name, source in bundle["units"].items():
        write_new(root / "systemd" / name, source.encode())
    collector_path = root / "inspect-pilot-host.py"
    write_new(collector_path, payload["collector"].encode())
    receipt = {
        "received_utc": datetime.now(timezone.utc).isoformat(),
        "instance_id": INSTANCE,
        "deployment_id": DEPLOYMENT,
        "source_received": True,
        "directory": str(root),
        "handoff_sha256": HANDOFF_SHA,
        "bundle_sha256": BUNDLE_SHA,
        "collector_sha256": COLLECTOR_SHA,
        "manifest_proposal_sha256": MANIFEST_SHA,
        "source_files_verified": len(bundle["files"]),
        "unit_files_verified": len(bundle["units"]),
        "worker_started": False,
        "operator_approval_issued": False,
    }
    write_new(root / "transfer-receipt.json", receipt)
    spec = importlib.util.spec_from_file_location(
        "reviewed_pilot_collector", collector_path
    )
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    try:
        report = collector.collect(root, DEPLOYMENT, BUNDLE_SHA)
    except (OSError, ValueError, RuntimeError) as error:
        report = {
            "read_only": True,
            "host_preparation_checks_passed": False,
            "error_type": type(error).__name__,
            "details": str(error)[:300],
            "worker_started_or_executed": False,
        }
    write_new(root / "host-preflight.json", report)
    print(json.dumps({"transfer_receipt": receipt, "host_report": report}, indent=2))


if __name__ == "__main__":
    main(HANDOFF)  # noqa: F821 -- supplied by the hash-verified private bootstrap
