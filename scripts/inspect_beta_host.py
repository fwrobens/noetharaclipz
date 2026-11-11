"""Read-only admission after the stopped 24h deployment. No installation/start.

Reuse hash-reviewed collectors with explicitly updated predecessor constants;
their original files and old reports remain unchanged. Call from a verified
source staging directory only.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inspect_continuous_24h_host as base  # noqa: E402

PREVIOUS = "c25d8492-56fb-4c56-a519-e9a9e4246525"
PREVIOUS_SHA = "3918b9eb1dee06597852c016a7098a873eea914bbac8afa151557cda2c34dda0"
PREVIOUS_CID = "abb2252ebb8bf3665db5e7310d2e594e563401fa8bc85214126d862ffb9c51f9"


def collect(root, deployment, bundle_sha):
    if deployment in (PREVIOUS, base.PREVIOUS):
        raise ValueError("Distinct new beta deployment required")
    saved = base.PREVIOUS, base.PREVIOUS_SHA, base.PREVIOUS_CID
    try:
        base.PREVIOUS, base.PREVIOUS_SHA, base.PREVIOUS_CID = (
            PREVIOUS,
            PREVIOUS_SHA,
            PREVIOUS_CID,
        )
        report = base.collect(root, deployment, bundle_sha)
    finally:
        base.PREVIOUS, base.PREVIOUS_SHA, base.PREVIOUS_CID = saved
    report["pending"] = [
        "Exact hosted release and rollback/Auth inventory approval",
        "Fresh authenticated owner consent and two-hour manifest review",
        "Separate approval of attended monitoring installation, scoped processing and detached startup",
        "Fresh per-generation actual kernel quotas and scoped live denial proofs before queue grant",
    ]
    report["worker_start_authorized"] = False
    report["monitoring_installed"] = False
    report["read_only"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    args = parser.parse_args()
    print(
        json.dumps(collect(args.root, args.deployment_id, args.bundle_sha256), indent=2)
    )


if __name__ == "__main__":
    main()
