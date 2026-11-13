"""Operator-only, bounded EC2 network preflight under the existing QA approval.

Applies ONLY the hash-pinned reviewed policy. Never starts a worker, mounts a
secret, loads models, claims jobs, changes shared policies or restarts services.
On success retain the owned bridge/rules for QA; always remove the diagnostic.
On failure remove only resources created here, after the diagnostic is gone.
"""

import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

INSTANCE = "i-0be10e530045fc650"
IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
NETWORK = "noetharaclipz-isolated_worker-egress"
BRIDGE, CHAIN = "nccz-qa0", "NCZQA_EGRESS"
SUBNET = ipaddress.ip_network("172.20.0.0/24")
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]
POLICY_SHA = "ec116cab16d2276b87d675eced9d12b83f05b860687f7ade458b8e35a868a646"
QUOTA_SHA = "e35ff35de3e085799b7d10ed2b3d7eec6ad0ca28d10ab682e075921e0bfed5fe"


def run(command, source=None, timeout=30):
    result = subprocess.run(command, input=source, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Commands in this helper never contain credentials. Do not include
        # stdin, and redact credential-shaped text if a tool emits it anyway.
        error = result.stderr.strip()
        error = re.sub(r"(?i)(Bearer\s+)\S+", r"\1[redacted]", error)
        error = re.sub(r"(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)\S+",
                       r"\1[redacted]", error)
        raise RuntimeError(json.dumps({"command": command[:4], "exit_code": result.returncode,
                                       "stderr": error[-2000:]}))
    return result.stdout.strip()


def inverse_rule(command):
    """Only undo a successfully applied, owned rule; never flush a chain."""
    if command[:3] != ["iptables", "--wait", "5"]:
        raise ValueError("Not a reviewed iptables command")
    result = command.copy()
    operation, chain = result[3:5]
    if operation in ("-N", "-A") and chain == CHAIN:
        result[3] = "-X" if operation == "-N" else "-D"
    elif (operation == "-I" and chain in ("INPUT", "DOCKER-USER")
          and result[5:8] == ["1", "-i", BRIDGE]):
        result[3] = "-D"
        del result[5]
    else:
        raise ValueError("Refuse to alter an unowned rule")
    return result


def admit(snapshot):
    if snapshot["instance"] != INSTANCE:
        raise ValueError("Wrong EC2 instance")
    if snapshot["ram"] < 10 * 1024**3 or snapshot["disk"] < 20 * 1024**3:
        raise ValueError("Insufficient host headroom")
    if not snapshot["ip_forward"]:
        raise ValueError("IPv4 forwarding disabled; do not change host settings")
    if snapshot["project_containers"] or NETWORK in snapshot["networks"] or BRIDGE in snapshot["links"]:
        raise ValueError("Reserved project/network/bridge collision")
    if any(CHAIN in line or BRIDGE in line for line in snapshot["firewall"]):
        raise ValueError("Reserved firewall resource collision")
    forward = [line for line in snapshot["firewall"] if line.startswith("-A FORWARD ")]
    if not forward or forward[0] != "-A FORWARD -j DOCKER-USER":
        raise ValueError("Unreviewed FORWARD ordering")
    if any(SUBNET.overlaps(ipaddress.ip_network(value, strict=False)) for value in snapshot["cidrs"]):
        raise ValueError("Dedicated subnet overlaps an existing route/network")


def counters(chain):
    rows = []
    for line in run(["iptables", "--wait", "5", "-L", chain, "-n", "-v", "-x", "--line-numbers"]).splitlines():
        fields = line.split()
        if len(fields) >= 10 and fields[0].isdigit():
            rows.append({"packets": int(fields[1]), "target": fields[3],
                         "in": fields[6], "dest": fields[9]})
    return rows


def rejection_verified(before, after, connected):
    if connected or after <= before:
        raise ValueError("Connection denial lacks matching firewall counter proof")
    return True


def save_report(path, report, create=False):
    if not create and json.loads(path.read_text())["probe_id"] != report["probe_id"]:
        raise ValueError("Preflight receipt ownership mismatch")
    flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if create else os.O_TRUNC)
    with os.fdopen(os.open(path, flags, 0o600), "w") as stream:
        json.dump(report, stream, indent=2)


def service_snapshot():
    ids = run(DOCKER + ["ps", "-q"]).split()
    if not ids:
        raise ValueError("Expected existing services not found")
    lines = run(DOCKER + ["inspect", "--format",
        '{{.Id}} {{.State.StartedAt}} {{.RestartCount}} {{with index .State "Health"}}{{.Status}}{{else}}none{{end}}', *ids]).splitlines()
    if any(line.split()[-1] not in ("none", "healthy") for line in lines):
        raise ValueError("An existing service is unhealthy")
    return sorted(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", required=True, type=Path)
    parser.add_argument("--apply-approved-qa-policy", required=True, action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("Run through existing sudo -n; do not change permissions")
    root = args.config_root.resolve()
    policy_path, quota_path = (root / "deploy/worker" / name for name in ("egress_policy.py", "check_cgroup_limits.py"))
    if hashlib.sha256(policy_path.read_bytes()).hexdigest() != POLICY_SHA or hashlib.sha256(quota_path.read_bytes()).hexdigest() != QUOTA_SHA:
        raise ValueError("Reviewed policy/probe source hash mismatch")
    state_path = root.parent / "network-preflight.json"
    if os.path.lexists(state_path):
        raise ValueError("Existing preflight state; review ownership before resuming")
    spec = importlib.util.spec_from_file_location("reviewed_policy", policy_path)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    plan = policy.proposal()
    for command in plan["apply_after_approval"]:
        inverse_rule(command)  # Validate rollback scope before the first mutation.
    memory = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))) * 1024
    cidrs = []
    network_ids = run(DOCKER + ["network", "ls", "-q"]).split()
    for raw in run(DOCKER + ["network", "inspect", "--format", "{{json .IPAM.Config}}", *network_ids]).splitlines():
        cidrs += [item["Subnet"] for item in json.loads(raw) or [] if item.get("Subnet") and ":" not in item["Subnet"]]
    for route in json.loads(run(["ip", "-j", "-4", "route", "show", "table", "all"])):
        if route.get("dst") and route["dst"] != "default":
            cidrs.append(route["dst"])
    snapshot = {"instance": Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip(),
                "ram": memory, "disk": shutil.disk_usage("/var/lib").free,
                "ip_forward": Path("/proc/sys/net/ipv4/ip_forward").read_text().strip() == "1",
                "project_containers": run(DOCKER + ["ps", "-aq", "--filter", "label=com.docker.compose.project=noetharaclipz-isolated"]),
                "networks": run(DOCKER + ["network", "ls", "--format", "{{.Name}}"]).splitlines(),
                "links": [link["ifname"] for link in json.loads(run(["ip", "-j", "link", "show"]))],
                "firewall": run(["iptables", "--wait", "5", "-S"]).splitlines(), "cidrs": cidrs}
    admit(snapshot)
    run(["iptables", "--wait", "5", "-S", "DOCKER-USER"])
    if run(DOCKER + ["image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Os}}|{{.Architecture}}|{{.Config.User}}"] ) != IMAGE + "|linux|amd64|62001:62001":
        raise ValueError("Pinned runtime identity mismatch")
    before_services = service_snapshot()
    nonce = uuid.uuid4().hex
    applied, network_attempted, passed = [], False, False
    report = {"network_preflight_passed": False, "worker_started": False, "models_loaded": False,
              "credentials_used": False, "queue_access": False, "network": NETWORK,
              "bridge": BRIDGE, "subnet": str(SUBNET), "probe_id": nonce, "checks": {}}
    report["phase"] = "policy_apply"
    save_report(state_path, report, create=True)
    try:
        for command in plan["apply_after_approval"]:
            run(command)
            applied.append(command)
        network_attempted = True
        report["phase"] = "network_create"
        save_report(state_path, report)
        network_id = run(DOCKER + ["network", "create", "--driver", "bridge", "--ipv6=false",
            "--subnet", str(SUBNET), "--gateway", "172.20.0.1",
            "--opt", "com.docker.network.bridge.name=" + BRIDGE,
            "--label", "com.docker.compose.project=noetharaclipz-isolated",
            "--label", "com.docker.compose.network=worker-egress",
            "--label", "io.noetharaclipz.preflight=" + nonce, NETWORK])
        name = "nccz-netcheck-" + nonce
        report["phase"] = "diagnostic_start"
        save_report(state_path, report)
        run(DOCKER + ["run", "-d", "--rm", "--name", name, "--label", "io.noetharaclipz.probe=" + nonce,
            "--pull=never", "--platform", "linux/amd64", "--network", NETWORK, "--dns", "172.31.0.2",
            "--sysctl", "net.ipv6.conf.all.disable_ipv6=1", "--sysctl", "net.ipv6.conf.default.disable_ipv6=1",
            "--user", "62001:62001", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--memory", "8g", "--memory-swap", "8g", "--cpus", "2", "--cpu-shares", "256",
            "--pids-limit", "256", "--oom-score-adj", "500", "--entrypoint", "python", IMAGE,
            "-c", "import time; time.sleep(180)"])

        def execute(code, timeout=30):
            return json.loads(run(DOCKER + ["exec", "-i", name, "python", "-"], source=code, timeout=timeout))

        quota = execute(quota_path.read_text())
        if not quota["passed"]:
            raise ValueError("Network diagnostic kernel limits not verified")
        report["actual_cgroup_limits"] = quota["actual_cgroup_limits"]
        report["phase"] = "public_https"
        save_report(state_path, report)
        public_code = '''import socket, ssl, urllib.request, urllib.error, json, ipaddress
from pathlib import Path
hosts = {"supabase": "zxdnjnsghdnviflahvry.supabase.co", "huggingface": "huggingface.co"}
checks = {}
for name, host in hosts.items():
    ips = {x[4][0] for x in socket.getaddrinfo(host, 443, socket.AF_INET)}
    assert ips and all(ipaddress.ip_address(ip).is_global for ip in ips)
    path = "/auth/v1/health" if name == "supabase" else "/api/models/HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
    try:
        with urllib.request.urlopen("https://" + host + path, timeout=12, context=ssl.create_default_context()) as response:
            status = response.status
            response.read(1024)
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status in ((200, 401) if name == "supabase" else (200,))
    checks[name] = {"dns_public_ipv4": True, "tls_verified": True, "http_status": status}
assert Path("/proc/sys/net/ipv6/conf/all/disable_ipv6").read_text().strip() == "1"
assert Path("/proc/sys/net/ipv6/conf/default/disable_ipv6").read_text().strip() == "1"
print(json.dumps({"public_endpoints": checks, "ipv6_disabled": True}))
'''
        report["checks"].update(execute(public_code, timeout=45))
        targets = [("staging_private", "172.18.255.254", 443, CHAIN, "172.16.0.0/12"),
                   ("supabase_private", "172.19.255.254", 443, CHAIN, "172.16.0.0/12"),
                   ("vpc_private", "172.31.255.254", 443, CHAIN, "172.16.0.0/12"),
                   ("imds", "169.254.169.254", 80, CHAIN, "169.254.0.0/16"),
                   ("host", "172.31.32.48", 443, "INPUT", None),
                   ("bridge_gateway", "172.20.0.1", 443, "INPUT", None),
                   ("public_non_https", "1.1.1.1", 80, CHAIN, "last")]
        for label, host, port, chain, destination in targets:
            report["phase"] = "deny_" + label
            save_report(state_path, report)
            def matched_counter():
                rows = counters(chain)
                if destination == "last":
                    if rows[-1]["target"] != "REJECT":
                        raise ValueError("Missing final egress rejection")
                    return rows[-1]["packets"]
                rows = [row for row in rows if row["target"] == "REJECT" and
                        (row["in"] == BRIDGE if destination is None else row["dest"] == destination)]
                if len(rows) != 1:
                    raise ValueError("Expected unique scoped rejection rule")
                return rows[0]["packets"]
            before = matched_counter()
            code = "import socket,json\ns=socket.socket(); s.settimeout(3)\ntry:\n s.connect(" + repr((host, port)) + "); connected=True\nexcept OSError:\n connected=False\nfinally:\n s.close()\nprint(json.dumps({'connected':connected}))\n"
            result = execute(code)
            after = matched_counter()
            rejection_verified(before, after, result["connected"])
            report["checks"][label] = {"blocked": True, "matching_reject_counter_delta": after - before}
        passed = True
        report.update(network_id=network_id, policy_sha256=POLICY_SHA)
    finally:
        # Do not remove protections unless all diagnostic processes are gone.
        owned = run(DOCKER + ["ps", "-aq", "--filter", "label=io.noetharaclipz.probe=" + nonce]).split()
        if owned:
            run(DOCKER + ["rm", "-f", *owned])
        if run(DOCKER + ["ps", "-aq", "--filter", "label=io.noetharaclipz.probe=" + nonce]):
            raise RuntimeError("Diagnostic cleanup failed; protections retained")
        try:
            services_unchanged = service_snapshot() == before_services
        except Exception:
            services_unchanged = False
        if not services_unchanged:
            passed = False
        if not passed:
            if network_attempted and NETWORK in run(DOCKER + ["network", "ls", "--format", "{{.Name}}"]).splitlines():
                owner = run(DOCKER + ["network", "inspect", NETWORK, "--format", '{{index .Labels "io.noetharaclipz.preflight"}}'])
                if owner != nonce:
                    raise RuntimeError("Network ownership mismatch; protections retained")
                run(DOCKER + ["network", "rm", NETWORK])
            for command in reversed(applied):
                run(inverse_rule(command))
        report.update(network_preflight_passed=passed, diagnostic_removed=True,
                      existing_services_unchanged=services_unchanged, scoped_network_and_rules_retained=passed,
                      completed_unix=int(time.time()))
        report["phase"] = "passed" if passed else "failed"
        save_report(state_path, report)
        print(json.dumps(report, indent=2), flush=True)
    if not passed:
        raise ValueError("Network preflight failed; do not seed or start a worker")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"failed": True, "reason": str(exc), "worker_started": False}), file=sys.stderr)
        raise SystemExit(1) from None
