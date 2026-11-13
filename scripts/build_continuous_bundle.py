"""Build an inert, hash-pinned application overlay for the existing private image.

Never creates an account/approval, contacts Supabase, installs a unit or starts a
worker. The source must be committed before producing a deployable artifact.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
CONFIG = "sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5"


def collect():
    files = {}
    helpers = [
        "reliability_platform.py",
        "reliability_metrics.py",
        "reliability_probe.py",
        "check_cgroup_limits.py",
        "egress_policy.py",
        "credential_envelope.py",
    ]
    paths = list((ROOT / "deploy/worker").glob("continuous_*.py"))
    paths += [ROOT / "deploy/worker" / name for name in helpers]
    for path in paths:
        files["host/" + path.name] = path.read_text()
    for prefix, directory in (
        ("worker", ROOT / "worker/noetharaclipz"),
        ("runtime", ROOT / "deploy/worker/noetharaclipz_deploy"),
    ):
        for path in directory.rglob("*.py"):
            if path.is_symlink():
                raise ValueError("Source symlink is not permitted")
            files[
                prefix + "/" + directory.name + "/" + str(path.relative_to(directory))
            ] = path.read_text()
    return dict(sorted(files.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-template", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.manifest_template.exists():
        raise ValueError("Do not overwrite immutable artifacts")
    changed = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "worker/noetharaclipz", "deploy/worker"],
        cwd=ROOT,
    ).decode()
    if changed:
        raise ValueError(
            "Commit the reviewed source before building a deployable bundle"
        )
    files = collect()
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()}
    units = {
        p.name: p.read_text()
        for p in (ROOT / "deploy/worker/systemd").glob("*.service")
    }
    unit_hashes = {
        name: hashlib.sha256(text.encode()).hexdigest() for name, text in units.items()
    }
    bundle = {
        "format": "nccz-continuous-source-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "base_image": IMAGE,
        "base_image_config": CONFIG,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip(),
        "source_dirty": False,
        "sha256": hashes,
        "files": files,
        "units": units,
        "unit_sha256": unit_hashes,
    }
    template = json.loads(
        (ROOT / "deploy/worker/continuous-manifest.example.json").read_text()
    )
    template["files"] = hashes
    template["source_commit"] = bundle["source_commit"]
    template["unit_sha256"] = unit_hashes
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    for path, data in (
        (args.output, raw),
        (args.manifest_template, (json.dumps(template, indent=2) + "\n").encode()),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(
            os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
        ) as stream:
            stream.write(data)
    print(
        json.dumps(
            {
                "bundle_sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "files": len(files),
                "source_commit": bundle["source_commit"],
                "image_rebuilt": False,
                "approval_issued": False,
                "worker_started": False,
            }
        )
    )


if __name__ == "__main__":
    main()
