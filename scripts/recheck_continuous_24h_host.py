"""Stage a corrected read-only collector alongside the failed receipt.

Preserve the first collector and its report. Explicit --all is required for
empty systemd properties. Only new private diagnostic files are written.
"""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from uuid import UUID


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def write_once(path, raw):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"
    ) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(payload):
    os.umask(0o077)
    deployment = payload["deployment_id"]
    if str(UUID(deployment)) != deployment:
        raise ValueError("Canonical deployment required")
    if (
        os.geteuid() != 0
        or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip()
        != "i-0be10e530045fc650"
    ):
        raise ValueError("Wrong host or execution identity")
    root = Path("/var/tmp") / ("nccz-24h-" + deployment)
    if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ValueError("Untrusted preparation directory")
    raw = (root / "preparation.json").read_bytes()
    if sha(raw) != payload["preparation_sha256"]:
        raise ValueError("Preparation identity changed")
    initial = json.loads(raw)
    for name, expected in initial["helper_sha256"].items():
        path = root / "handoff" / name
        if (
            Path(name).name != name
            or path.is_symlink()
            or sha(path.read_bytes()) != expected
        ):
            raise ValueError("Previously reviewed helper changed")
    source = payload["collector"]
    if sha(source.encode()) != payload["collector_sha256"]:
        raise ValueError("Corrected collector hash changed")
    helper = root / "handoff/inspect_continuous_24h_host_v2.py"
    write_once(helper, source.encode())
    sys.path.insert(0, str(root / "handoff"))
    spec = importlib.util.spec_from_file_location("corrected_24h_admission", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = (root / "host-preflight.json").read_bytes()
    try:
        report = module.collect(root, deployment, payload["bundle_sha256"])
    except Exception as error:
        report = {
            "read_only": True,
            "host_preparation_checks_passed": False,
            "error_type": type(error).__name__,
            "details": str(error)[:300],
            "worker_started_or_executed": False,
        }
    if (root / "host-preflight.json").read_bytes() != before:
        raise ValueError("Initial preflight evidence changed")
    output = canonical(report)
    write_once(root / "host-preflight-v2.json", output)
    receipt = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "deployment_id": deployment,
        "collector_name": helper.name,
        "collector_sha256": payload["collector_sha256"],
        "report_name": "host-preflight-v2.json",
        "report_sha256": sha(output),
        "initial_preflight_preserved": True,
        "initial_preflight_sha256": sha(before),
        "worker_started": False,
        "operator_approval_issued": False,
        "network_rules_changed": False,
        "unit_files_changed": False,
    }
    write_once(root / "admission-recheck-receipt.json", canonical(receipt))
    print(
        json.dumps({"recheck_receipt": receipt, "host_report": report}, indent=2),
        flush=True,
    )


if __name__ == "__main__":
    main(RECHECK)  # noqa: F821 -- supplied by hash-verified private bootstrap
