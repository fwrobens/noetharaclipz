"""Print a worker-only firewall proposal; NEVER executes commands.

Target-specific values come from the operator's read-only Ohio host reports.
Apply only after explicit approval and fresh compatibility/collision checks.
"""

import argparse
import json
import shlex

BRIDGE = "nccz-qa0"
CHAIN = "NCZQA_EGRESS"
DNS = "172.31.0.2"
DENIED = (
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "198.18.0.0/15",
    "224.0.0.0/4",
    "240.0.0.0/4",
)


def proposal():
    rules = [
        ["-d", DNS + "/32", "-p", protocol, "--dport", "53", "-j", "RETURN"]
        for protocol in ("udp", "tcp")
    ]
    rules += [
        ["-d", cidr, "-j", "REJECT", "--reject-with", "icmp-admin-prohibited"]
        for cidr in DENIED
    ]
    rules += [
        [
            "-m",
            "addrtype",
            "--dst-type",
            "LOCAL",
            "-j",
            "REJECT",
            "--reject-with",
            "icmp-admin-prohibited",
        ],
        ["-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "RETURN"],
        ["-p", "tcp", "--dport", "443", "-j", "RETURN"],
        ["-j", "REJECT", "--reject-with", "icmp-admin-prohibited"],
    ]
    host_rule = ["-i", BRIDGE, "-j", "REJECT", "--reject-with", "icmp-admin-prohibited"]
    forward_rule = ["-i", BRIDGE, "-j", CHAIN]
    base = ["iptables", "--wait", "5"]
    apply = [base + ["-N", CHAIN]]
    apply += [base + ["-A", CHAIN] + rule for rule in rules]
    apply += [
        base + ["-I", "INPUT", "1"] + host_rule,
        base + ["-I", "DOCKER-USER", "1"] + forward_rule,
    ]
    rollback = [
        base + ["-D", "DOCKER-USER"] + forward_rule,
        base + ["-D", "INPUT"] + host_rule,
    ]
    rollback += [base + ["-D", CHAIN] + rule for rule in reversed(rules)]
    rollback += [base + ["-X", CHAIN]]
    return {
        "execution": "print-only; no subprocess or host mutations",
        "bridge": BRIDGE,
        "dns": DNS,
        "apply_after_approval": apply,
        "rollback_after_worker_stop": rollback,
        "requirements": [
            "No existing chain NCZQA_EGRESS or bridge nccz-qa0 owned by another application",
            "Reviewed IPv4 iptables/Docker backend and source-interface matching",
            "Worker/seed IPv6 disabled within their own network namespaces",
            "No worker/seed started until all proposed rules succeed",
            "Never change global policies, flush shared chains or alter security groups",
            "QA on-failure restart only; no unattended host/daemon reboot startup",
            "Rollback requires stopping this worker and seed first",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "shell"), default="json")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    data = proposal()
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print(
            "# REVIEW ONLY. Requires separate host review and deployment authorization."
        )
        print(
            "# Never apply if the reserved chain/bridge is already owned by another service."
        )
        print("set -eu")
        print('if [ "${NC_QA_FIREWALL_APPROVED:-}" != yes ]; then')
        print(
            "  printf '%s\\n' 'Separate QA network authorization is required; no rules applied.' >&2"
        )
        print("  exit 1")
        print("fi")
        for command in data[
            "rollback_after_worker_stop" if args.rollback else "apply_after_approval"
        ]:
            print(shlex.join(["sudo", "-n"] + command))


if __name__ == "__main__":
    main()
