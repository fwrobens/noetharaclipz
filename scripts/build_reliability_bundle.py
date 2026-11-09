"""Build preparation-only data. Never create users, approval receipts or workers."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

ARCHIVED_TRIALS = {"9563aeb9-2620-4e05-acf2-1e69ce18b819", "bebbf5ad-094f-4b6f-964f-c7ac22e1f760"}
ROOT = Path(__file__).resolve().parents[1]
CODE = ["reliability_host.py", "reliability_platform.py", "reliability_entry.py", "reliability_probe.py",
        "reliability_policy.py", "reliability_metrics.py", "check_cgroup_limits.py", "egress_policy.py", "credential_envelope.py"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trial-id", type=UUID, required=True, help="New configuration ID; never reuse an activated trial")
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--source-metadata", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--plan-output", type=Path, required=True)
    p.add_argument("--additional-evidence", type=Path, action="append", default=[])
    args = p.parse_args()
    trial = str(args.trial_id)
    if trial in ARCHIVED_TRIALS:
        raise ValueError("An archived trial cannot be rebuilt or reactivated")
    if args.output.exists() or args.plan_output.exists():
        raise ValueError("A prepared immutable bundle/plan must not be overwritten")
    raw = args.sample.read_bytes()
    media = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(args.sample)]))
    source = json.loads(args.source_metadata.read_text())
    assert source["license"] == "CC BY 3.0" and source["looped_or_concatenated"] is False
    duration = float(media["format"]["duration"])
    assert 120 <= duration <= 300 and len(raw) < 45_000_000
    code = {name: (ROOT / "deploy/worker" / name).read_text() for name in CODE}
    evidence_paths = sorted((ROOT / "docs/evidence").glob("ec2-qa-*.json"))
    evidence_paths += [ROOT / "docs/evidence" / name for name in ("ec2-post-trial-supabase.json", "ec2-runtime-preflight.json")]
    evidence_paths += args.additional_evidence
    if len({path.name for path in evidence_paths}) != len(evidence_paths):
        raise ValueError("Evidence filenames must be unique; never replace historical evidence")
    old = {path.name: path.read_text() for path in evidence_paths}
    plan = {"schema": 1, "trial_id": trial, "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "instance": "i-0be10e530045fc650", "instance_type": "m6i.2xlarge", "region": "us-east-2",
        "image": "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759",
        "model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct", "model_revision": "7b375e1b73b11138ff12fe22c8f2822d8fe03467",
        "maximum_seconds": 1800, "memory_bytes": 8 * 1024**3, "cpus": 2, "active_jobs": 1,
        "global_processing": False, "gemini_enabled": False, "requires_future_approval": True,
        "owner_policy": "fresh_empty_owner_after_separate_approval",
        "fault_test": "one_runner_sigkill_during_approved_source_analysis",
        "resource_sampling": {"interval_seconds": 2, "kernel_memory_peak": True,
            "cpu_peak": "maximum observed interval rate, one core = 100 percent",
            "final_generation_snapshot_handshake": True, "durable_host_log": True},
        "sample": {**source, "filename": args.sample.name, "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw), "duration_seconds": duration,
                   "streams": [{k: stream.get(k) for k in ("codec_type", "codec_name", "width", "height")} for stream in media["streams"]]},
        "code_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in code.items()},
        "previous_evidence_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in old.items()},
        "previous_evidence_commit": "4f53553beca3c1578227b9508e0090e42b20f9e6"}
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    # Also expose the exact canonical plan bytes used on EC2 and approval issuance.
    args.plan_output.parent.mkdir(parents=True, exist_ok=True)
    with args.plan_output.open("x") as stream:
        stream.write(encoded)
    payload = {"format": "noetharaclipz-reliability-preparation-v1", "plan": plan, "code": code, "previous_evidence": old}
    with args.output.open("x") as stream:
        json.dump(payload, stream, separators=(",", ":"))
    print(json.dumps({"trial_id": trial, "plan_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                      "sample_bytes": len(raw), "duration": duration, "approval_issued": False, "worker_started": False}))


if __name__ == "__main__":
    main()
