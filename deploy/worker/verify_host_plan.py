"""Offline review of a read-only host report. Never deploys or changes a host."""

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("host_report", type=Path)
    args = p.parse_args()
    host = json.loads(args.host_report.read_text())
    gib = 1024**3
    checks = {
        "at_least_four_host_vcpus": host.get("logical_cpus", 0) >= 4,
        "at_least_10gib_current_memavailable": host.get("memory_bytes", {}).get(
            "MemAvailable", 0
        )
        >= 10 * gib,
        "at_least_20gib_free_existing_disk": host.get("disk_bytes", {}).get("free", 0)
        >= 20 * gib,
        "existing_container_limits_inspected": host.get(
            "container_limits_no_environment", {}
        ).get("ok", False),
        "docker_resource_details_available": host.get("docker_resources", {}).get(
            "ok", False
        ),
    }
    report = {
        "snapshot_checks": checks,
        "deployment_authorized": False,
        "ready_to_start": False,
        "remaining_manual_gates": [
            "Verify this report is from i-0be10e530045fc650 and review peak existing workloads",
            "Verify EC2 region/type and incremental-cost budget; confirmed m6i is not credit based",
            "Review existing networks/firewall, IMDS isolation and dedicated paths/UID",
            "Review host Docker boot setting and log/storage retention",
            "Obtain explicit deployment permission, then enable a QA owner only",
        ],
        "commands_executed": [],
    }
    print(json.dumps(report, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
