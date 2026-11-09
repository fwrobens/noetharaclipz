"""Explicit startup probes and one guarded runner-only fault inside the new QA container."""

import ipaddress
import json
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from check_cgroup_limits import evaluate, read_limits

# Exercise our private-subnet REJECT rules using unused destinations. Docker's
# raw PREROUTING drops live container IPs before the filter-table counters, so
# targeting an application's real IP cannot prove which isolation rule fired.
TARGETS = [("staging", "172.18.255.254", 8080, "NCZQA_EGRESS", "172.16.0.0/12"),
    ("supabase", "172.19.255.254", 8000, "NCZQA_EGRESS", "172.16.0.0/12"),
    ("vpc", "172.31.255.254", 443, "NCZQA_EGRESS", "172.16.0.0/12"),
    ("imds", "169.254.169.254", 80, "NCZQA_EGRESS", "169.254.0.0/16"),
    ("host", "172.31.32.48", 8080, "INPUT", None),
    ("gateway", "172.20.0.1", 443, "INPUT", None),
    ("non_https", "1.1.1.1", 80, "NCZQA_EGRESS", "last")]


def check_runner(pid, health, command, env, now):
    if (pid <= 1 or health.get("pid") != pid or health.get("mode") != "qa"
            or not health.get("ai_ready") or not 0 <= now - health.get("at", 0) < 90
            or b"from noetharaclipz.runner import main" not in command
            or env.get("NC_DEPLOY_MODE") != "qa" or env.get("NC_AI_PROVIDER") != "local"
            or env.get("NC_GLOBAL_QUEUE_APPROVED") != "false"
            or now >= int(env["NC_QA_STOP_AT"]) - 300):
        raise ValueError("Refusing to signal anything except this new trial's live runner")


def main():
    mode = sys.argv[1]
    if mode == "public":
        proof = evaluate(read_limits())
        assert proof["passed"]
        assert Path("/proc/sys/net/ipv6/conf/all/disable_ipv6").read_text().strip() == "1"
        assert Path("/proc/sys/net/ipv6/conf/default/disable_ipv6").read_text().strip() == "1"
        statuses = {}
        for host, path in (("zxdnjnsghdnviflahvry.supabase.co", "/auth/v1/health"),
                           ("huggingface.co", "/api/models/HuggingFaceTB/SmolVLM2-500M-Video-Instruct")):
            ips = {x[4][0] for x in socket.getaddrinfo(host, 443, socket.AF_INET)}
            assert ips and all(ipaddress.ip_address(ip).is_global for ip in ips)
            try:
                with urllib.request.urlopen("https://" + host + path, timeout=8) as response:
                    status = response.status
                    response.read(1024)
            except urllib.error.HTTPError as error:
                status = error.code
            assert status in ((200, 401) if host.endswith("supabase.co") else (200,))
            statuses[host] = status
        print(json.dumps({"kernel": proof, "public_tls": statuses, "ipv6_disabled": True}))
    elif mode == "deny":
        target = TARGETS[int(sys.argv[2])]
        error_number = None
        with socket.socket() as connection:
            connection.settimeout(2)
            try:
                connection.connect((target[1], target[2]))
                blocked = False
            except OSError as error:
                blocked = True
                error_number = error.errno
        # A connection failure alone is never sufficient proof. The host must
        # also observe an increase in this target's scoped REJECT counter.
        print(json.dumps({"target": target[0], "address": target[1], "port": target[2],
                          "blocked": blocked, "socket_errno": error_number}))
    elif mode == "crash-runner":
        pid = int(sys.argv[2])
        health = json.loads(Path("/run/worker/health.json").read_text())
        command = Path("/proc/" + str(pid) + "/cmdline").read_bytes()
        check_runner(pid, health, command, os.environ, time.time())
        os.kill(pid, signal.SIGKILL)
        print(json.dumps({"runner_only_sigkill": True, "pid": pid}))
    else:
        raise ValueError("Unknown probe")


if __name__ == "__main__":
    main()
