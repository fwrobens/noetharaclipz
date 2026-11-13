"""Preparation-only SSM receiver. Stages verified source in a NEW private /var/tmp.

No unit installation, credentials, model execution, queue access or networking
changes. The hash-pinned collector permits only read operations on the host.
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
HELPERS = {
    "inspect_beta_host.py",
    "inspect_continuous_24h_host.py",
    "inspect_continuous_pilot_host.py",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate(payload):
    deployment = payload["deployment_id"]
    if (
        str(UUID(deployment)) != deployment
        or deployment
        in (
            "c25d8492-56fb-4c56-a519-e9a9e4246525",
            "11865b83-9836-4ff3-a99e-dfac4df71f34",
        )
        or payload.get("format") != "nccz-beta-readonly-preparation-v1"
        or any(
            payload.get(key) is not False
            for key in (
                "operator_approved",
                "worker_start_authorized",
                "monitoring_install_authorized",
            )
        )
        or sha(payload["source_bundle_json"].encode())
        != payload.get("source_bundle_sha256")
        or set(payload["helpers"]) != HELPERS
        or set(payload["helper_sha256"]) != HELPERS
    ):
        raise ValueError("Unreviewed or already-authorized preparation payload")
    bundle = json.loads(payload["source_bundle_json"])
    if (
        bundle.get("base_image")
        != "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
        or bundle.get("source_dirty") is not False
    ):
        raise ValueError("Changed reviewed worker image/source")
    files = {
        **bundle["files"],
        **{"systemd/" + k: v for k, v in bundle["units"].items()},
        **{"handoff/" + k: v for k, v in payload["helpers"].items()},
    }
    hashes = {
        **bundle["sha256"],
        **{"systemd/" + k: v for k, v in bundle["unit_sha256"].items()},
        **{"handoff/" + k: v for k, v in payload["helper_sha256"].items()},
    }
    review_name = "review/noetharaclipz-beta-alerts@.service"
    if payload.get("monitor_unit_text") and sha(
        payload["monitor_unit_text"].encode()
    ) == payload.get("monitor_unit_sha256"):
        files[review_name] = payload["monitor_unit_text"]
        hashes[review_name] = payload["monitor_unit_sha256"]
    else:
        raise ValueError("Reviewed monitor template required for syntax-only preflight")
    if set(files) != set(hashes):
        raise ValueError("Incomplete source manifest")
    for name, text in files.items():
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or path.parts[0]
            not in ("host", "worker", "runtime", "systemd", "handoff", "review")
            or sha(text.encode()) != hashes[name]
        ):
            raise ValueError("Unsafe path or changed source")
    return files


def write_new(path, raw):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(
        os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), "wb"
    ) as f:
        f.write(raw)


def main(payload):
    sys.dont_write_bytecode = True
    os.umask(0o077)
    files = validate(payload)
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != INSTANCE
    ):
        raise ValueError("Expected existing EC2 host and root preparation identity")
    root = Path("/var/tmp") / ("nccz-beta-" + payload["deployment_id"])
    root.mkdir(mode=0o700, exist_ok=False)
    write_new(root / "preparation.json", canonical(payload))
    write_new(root / "bundle.json", payload["source_bundle_json"].encode())
    for name, text in files.items():
        write_new(root / name, text.encode())
    receipt = {
        "received_utc": datetime.now(timezone.utc).isoformat(),
        "deployment_id": payload["deployment_id"],
        "directory": str(root),
        "source_bundle_sha256": payload["source_bundle_sha256"],
        "preparation_sha256": sha(canonical(payload)),
        "worker_started": False,
        "monitoring_installed": False,
        "credentials_read": False,
        "operator_approval_issued": False,
    }
    write_new(root / "transfer-receipt.json", canonical(receipt))
    sys.path.insert(0, str(root / "handoff"))
    spec = importlib.util.spec_from_file_location(
        "verified_beta_collector", root / "handoff/inspect_beta_host.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        report = module.collect(
            root, payload["deployment_id"], payload["source_bundle_sha256"]
        )
    except Exception as error:
        report = {
            "read_only": True,
            "host_preparation_checks_passed": False,
            "error_type": type(error).__name__,
            "worker_started": False,
            "monitoring_installed": False,
        }
    write_new(root / "host-preflight.json", canonical(report))
    print(json.dumps({"transfer_receipt": receipt, "host_report": report}, indent=2))


if __name__ == "__main__":
    main(HANDOFF)  # noqa: F821 - injected by the reviewed signed handoff bootstrap
