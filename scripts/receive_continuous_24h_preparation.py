"""Stage a new private source handoff and collect read-only 24h host admission.

Only preparation files are written. No credential contents, processing approval,
systemd installation, firewall changes or container execution are permitted.
"""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import sys
from uuid import UUID

INSTANCE = "i-0be10e530045fc650"
IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
OWNER = "21b61ad1-bda4-4abd-ac35-7a0bf477ed69"
SOURCE_SHA = "564a5b6a5de0664448737e0c5291c30a4d1ff2074be096b08711dce11fb381d8"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate(payload):
    deployment = payload["deployment_id"]
    if (
        str(UUID(deployment)) != deployment
        or deployment == "11865b83-9836-4ff3-a99e-dfac4df71f34"
        or payload.get("format") != "nccz-24h-preparation-v1"
        or payload.get("owner_id") != OWNER
        or payload.get("operator_approved") is not False
        or payload.get("worker_start_authorized") is not False
        or payload.get("boot_start_authorized") is not False
        or sha(payload["source_bundle_json"].encode()) != SOURCE_SHA
        or set(payload["helpers"]) != set(payload["helper_sha256"])
        or not {
            "inspect_continuous_pilot_host.py",
            "inspect_continuous_24h_host.py",
        }.issubset(payload["helpers"])
    ):
        raise ValueError("Wrong or already authorized preparation scope")
    bundle = json.loads(payload["source_bundle_json"])
    if bundle.get("base_image") != IMAGE or bundle.get("source_dirty") is not False:
        raise ValueError("Unreviewed source/image")
    files = {
        **bundle["files"],
        **{"systemd/" + k: v for k, v in bundle["units"].items()},
    }
    hashes = {
        **bundle["sha256"],
        **{"systemd/" + k: v for k, v in bundle["unit_sha256"].items()},
    }
    if set(files) != set(hashes):
        raise ValueError("Incomplete source bundle")
    for name, source in payload["helpers"].items():
        if Path(name).name != name or not name.endswith(".py"):
            raise ValueError("Unsafe helper path")
        files["handoff/" + name] = source
        hashes["handoff/" + name] = payload["helper_sha256"][name]
    for name, source in files.items():
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or path.parts[0] not in ("host", "worker", "runtime", "systemd", "handoff")
            or sha(source.encode()) != hashes[name]
        ):
            raise ValueError("Unsafe path or changed private source")
    return files, bundle


def write_new(path, raw):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(payload):
    os.umask(0o077)
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != INSTANCE
    ):
        raise ValueError("Wrong host or execution identity")
    files, bundle = validate(payload)
    root = Path("/var/tmp") / ("nccz-24h-" + payload["deployment_id"])
    root.mkdir(mode=0o700)  # Never overwrite a previous preparation or its receipts.
    write_new(root / "bundle.json", payload["source_bundle_json"].encode())
    write_new(root / "preparation.json", canonical(payload))
    for name, source in files.items():
        write_new(root / name, source.encode())
    receipt = {
        "received_utc": datetime.now(timezone.utc).isoformat(),
        "deployment_id": payload["deployment_id"],
        "directory": str(root),
        "preparation_sha256": sha(canonical(payload)),
        "bundle_sha256": SOURCE_SHA,
        "helper_sha256": payload["helper_sha256"],
        "source_files_verified": len(bundle["files"]),
        "unit_files_verified": len(bundle["units"]),
        "worker_started": False,
        "operator_approval_issued": False,
    }
    write_new(root / "transfer-receipt.json", canonical(receipt))
    sys.path.insert(0, str(root / "handoff"))
    spec = importlib.util.spec_from_file_location(
        "verified_24h_collector", root / "handoff/inspect_continuous_24h_host.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        report = module.collect(root, payload["deployment_id"], SOURCE_SHA)
    except Exception as error:
        report = {
            "read_only": True,
            "host_preparation_checks_passed": False,
            "error_type": type(error).__name__,
            "details": str(error)[:300],
            "worker_started_or_executed": False,
            "credential_contents_read": False,
        }
    write_new(root / "host-preflight.json", canonical(report))
    print(
        json.dumps({"transfer_receipt": receipt, "host_report": report}, indent=2),
        flush=True,
    )


if __name__ == "__main__":
    main(PREPARATION)  # noqa: F821 -- supplied by the hash-verified private bootstrap
