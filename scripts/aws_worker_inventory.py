"""Read-only AWS CLI inventory. No EC2/SSM commands are executed on the host.

Does not use Cost Explorer, Insights, SendCommand, resource creation or mutation.
Output can contain private network metadata: keep the report outside Git.
"""

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--instance-id", default="i-0be10e530045fc650")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "read_only": True,
        "region": args.region,
        "instance_id": args.instance_id,
        "host_capacity_verified": False,
    }
    base = ["aws", "--no-cli-pager", "--output", "json", "--region", args.region]
    if args.profile:
        base += ["--profile", args.profile]

    def read(service, operation, *params):
        assert operation.startswith(
            (
                "describe-",
                "get-metric-statistics",
                "list-metrics",
                "get-caller-identity",
            )
        )
        c = subprocess.run(
            base + [service, operation, *params],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if c.returncode:
            # Avoid printing CLI stderr, credential helper output or private auth context.
            return {"unavailable": True, "exit_code": c.returncode}
        return json.loads(c.stdout)

    if not shutil.which("aws"):
        report["blocked"] = (
            "AWS CLI absent; attach a read-only AWS identity before running inventory"
        )
    else:
        report["identity"] = read("sts", "get-caller-identity")
        if report["identity"].get("unavailable"):
            report["blocked"] = (
                "Configured AWS identity unavailable; no instance queries attempted"
            )
        else:
            report["instance"] = read(
                "ec2", "describe-instances", "--instance-ids", args.instance_id
            )
            reservations = report["instance"].get("Reservations", [])
            if reservations:
                instance = reservations[0]["Instances"][0]
                report["instance_type"] = read(
                    "ec2",
                    "describe-instance-types",
                    "--instance-types",
                    instance["InstanceType"],
                )
                type_rows = report["instance_type"].get("InstanceTypes") or [{}]
                burstable = type_rows[0].get("BurstablePerformanceSupported")
                if burstable is True:
                    report["credit_mode"] = read(
                        "ec2",
                        "describe-instance-credit-specifications",
                        "--instance-ids",
                        args.instance_id,
                    )
                else:
                    report["credit_mode"] = (
                        "not applicable: non-burstable instance"
                        if burstable is False
                        else "instance capability unavailable"
                    )
                volumes = [
                    d["Ebs"]["VolumeId"]
                    for d in instance.get("BlockDeviceMappings", [])
                    if "Ebs" in d
                ]
                if volumes:
                    report["volumes"] = read(
                        "ec2", "describe-volumes", "--volume-ids", *volumes
                    )
                groups = [g["GroupId"] for g in instance.get("SecurityGroups", [])]
                if groups:
                    report["security_groups"] = read(
                        "ec2", "describe-security-groups", "--group-ids", *groups
                    )
                report["status"] = read(
                    "ec2",
                    "describe-instance-status",
                    "--instance-ids",
                    args.instance_id,
                )
                now = datetime.now(timezone.utc)
                report["metrics"] = {}
                metrics = ["CPUUtilization"]
                if burstable is True:
                    metrics += [
                        "CPUCreditBalance",
                        "CPUSurplusCreditBalance",
                        "CPUSurplusCreditsCharged",
                    ]
                for metric in metrics:
                    report["metrics"][metric] = read(
                        "cloudwatch",
                        "get-metric-statistics",
                        "--namespace",
                        "AWS/EC2",
                        "--metric-name",
                        metric,
                        "--dimensions",
                        "Name=InstanceId,Value=" + args.instance_id,
                        "--start-time",
                        (now - timedelta(days=7)).isoformat(),
                        "--end-time",
                        now.isoformat(),
                        "--period",
                        "900",
                        "--statistics",
                        "Average",
                        "Maximum",
                        "Minimum",
                    )
                report["existing_guest_metrics"] = read(
                    "cloudwatch",
                    "list-metrics",
                    "--namespace",
                    "CWAgent",
                    "--dimensions",
                    "Name=InstanceId,Value=" + args.instance_id,
                )
                report["note"] = (
                    "EC2 RAM allocation is not free RAM. Obtain read-only host probe and workload history. Missing CWAgent metrics do not establish spare capacity."
                )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.output.chmod(0o600)
    print(
        json.dumps(
            {
                "report": str(args.output),
                "blocked": report.get("blocked"),
                "host_capacity_verified": False,
            }
        )
    )
    return 1 if "blocked" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
