"""Small host helpers for one explicitly approved reliability trial.

Network operations here inspect the existing worker-only rules; none apply or
flush rules. Docker changes are confined to a new name and checked trial label.
"""

import hashlib
import ipaddress
import json
import os
import shlex
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from credential_envelope import server_headers
from egress_policy import proposal

INSTANCE = "i-0be10e530045fc650"
IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
OLD_CID = "fbe3d4f4d9b1c95cb3cae77278a40a5cf5d52c77435eccdc3d14c60d17c06f99"
NETWORK = "noetharaclipz-isolated_worker-egress"
NETWORK_ID = "79d31a3d0a9e1df6873461c6761dd3ce8e170de85785022d34242f04c640ef28"
NETWORK_OWNER = "afd21af8a4fe44aca8e2ae9e7ccedca6"
BASE = "https://zxdnjnsghdnviflahvry.supabase.co"
ETC = Path("/etc/noetharaclipz-isolated/trials")
DATA = Path("/var/lib/noetharaclipz-isolated/trials")
MODELS = Path("/var/lib/noetharaclipz-isolated/models")
KEY = Path("/etc/noetharaclipz-isolated/supabase-key")
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]


def run(command, timeout=30):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # No credential values enter command arguments. Do not expose arbitrary
        # tool stderr, container environments or user content in a failure.
        raise RuntimeError("Command failed (exit " + str(result.returncode) + "): " + " ".join(command[:4]))
    return result.stdout.strip()


def docker(*args, timeout=30):
    return run(DOCKER + list(args), timeout=timeout)


def inspect(cid):
    # Captured in memory only. Never print Config.Env or unrelated health output.
    return json.loads(docker("inspect", "--type", "container", cid))[0]


def require_host():
    if os.geteuid() != 0 or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip() != INSTANCE:
        raise ValueError("Run only on the authorized EC2 instance via existing sudo -n")


def write_once(path, value, gid=0, mode=0o600):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), "w") as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2))
    os.chown(path, 0, gid)
    os.chmod(path, mode)


def atomic(path, value, gid=0, mode=0o600):
    temp = path.with_name(path.name + ".pending")
    # This directory is private to this root controller; never overwrite a
    # foreign temporary file or follow a symlink.
    write_once(temp, value, gid=gid, mode=mode)
    temp.replace(path)


def mkdir(path, uid=0, gid=0, mode=0o700):
    if not path.exists():
        path.mkdir(mode=mode)
        os.chown(path, uid, gid)
        os.chmod(path, mode)
    info = path.lstat()
    if path.is_symlink() or not path.is_dir() or (info.st_uid, info.st_gid, info.st_mode & 0o777) != (uid, gid, mode):
        raise ValueError("Foreign ownership or mode at a dedicated trial path")


def service_snapshot(excluded=None):
    ids = docker("ps", "-q", "--no-trunc").split()
    ids = [cid for cid in ids if cid != excluded]
    rows = []
    template = '{{.Id}}\t{{.State.StartedAt}}\t{{.RestartCount}}\t{{with index .State "Health"}}{{.Status}}{{else}}none{{end}}\t{{json .Config.Labels}}'
    output = docker("inspect", "--format", template, *ids) if ids else ""
    for line in output.splitlines():
        cid, started, restarts, health, labels = line.split("\t", 4)
        project = (json.loads(labels) or {}).get("com.docker.compose.project", "")
        if project == "noetharaclipz-isolated" or project.startswith("nccz-reliability-"):
            raise ValueError("Another Clipz worker is active; only one is permitted")
        if health not in ("healthy", "none"):
            raise ValueError("Existing application is not healthy")
        rows.append({"id": cid, "started_at": started, "restart_count": int(restarts), "health": health})
    if len(rows) < 6:
        raise ValueError("Expected existing applications are missing")
    return sorted(rows, key=lambda row: row["id"])


def verify_network():
    net = json.loads(docker("network", "inspect", NETWORK))[0]
    if (net["Id"] != NETWORK_ID or net.get("EnableIPv6")
            or net["Options"].get("com.docker.network.bridge.name") != "nccz-qa0"
            or net["Labels"].get("io.noetharaclipz.preflight") != NETWORK_OWNER
            or [v["Subnet"] for v in net["IPAM"]["Config"]] != ["172.20.0.0/24"]):
        raise ValueError("Existing dedicated network changed; no network settings will be applied")


def verify_probe_destinations(targets):
    """Read-only admission: never probe an application's allocated container IP.

    Raw Docker drops precede our filter rules. Do not remove those drops, accept
    a timeout instead of a matching counter, or contact a live app to work around
    that ordering. Reject an unsuitable diagnostic destination before startup.
    """
    ids = docker("network", "ls", "-q").split()
    networks = json.loads(docker("network", "inspect", *ids)) if ids else []
    allocated = {str(ipaddress.ip_interface(container["IPv4Address"]).ip)
        for network in networks for container in (network.get("Containers") or {}).values()
        if container.get("IPv4Address")}
    raw = run(["iptables", "--wait", "5", "-t", "raw", "-S"])
    dropped = []
    for line in raw.splitlines():
        fields = shlex.split(line)
        if (fields[:2] == ["-A", "PREROUTING"] and "-d" in fields and "-j" in fields
                and fields[fields.index("-j") + 1] in ("DROP", "REJECT")):
            dropped.append(ipaddress.ip_network(fields[fields.index("-d") + 1], strict=False))
    for name, address, _port, _chain, _destination in targets:
        if address in allocated:
            raise ValueError("Probe target " + name + " is allocated to a Docker application; use an unused destination")
        if any(ipaddress.ip_address(address) in network for network in dropped):
            raise ValueError("Probe target " + name + " is intercepted by raw PREROUTING before the scoped counter")


def firewall_fingerprint(verify=False):
    plan = proposal()["apply_after_approval"]
    if verify:
        for original in plan:
            command = original.copy()
            if command[3] == "-N":
                continue
            if command[3] == "-I":
                del command[5]
            command[3] = "-C"
            run(command)
    lines = run(["iptables", "--wait", "5", "-S"]).splitlines()
    selected = [line for line in lines if line.startswith("-A NCZQA_EGRESS ")]
    if len(selected) != sum("-A" in command for command in plan):
        raise ValueError("Dedicated firewall chain has missing or extra rules")
    for chain, target in (("FORWARD", "DOCKER-USER"), ("INPUT", "REJECT"), ("DOCKER-USER", "NCZQA_EGRESS")):
        rules = [line for line in lines if line.startswith("-A " + chain + " ")]
        first = shlex.split(rules[0]) if rules else []
        if ("-j" not in first or first[first.index("-j") + 1] != target
                or chain != "FORWARD" and ("-i" not in first or first[first.index("-i") + 1] != "nccz-qa0")):
            raise ValueError("Isolation hooks are not first in the existing chains")
        selected.append(rules[0])
    return hashlib.sha256("\n".join(selected).encode()).hexdigest()


def reject_counter(chain, destination):
    rows = []
    output = run(["iptables", "--wait", "5", "-L", chain, "-n", "-v", "-x", "--line-numbers"])
    for line in output.splitlines():
        f = line.split()
        if len(f) >= 10 and f[0].isdigit():
            rows.append({"packets": int(f[1]), "target": f[3], "in": f[6], "dest": f[9]})
    if destination == "last":
        assert rows[-1]["target"] == "REJECT"
        return rows[-1]["packets"]
    rows = [r for r in rows if r["target"] == "REJECT" and
            (r["in"] == "nccz-qa0" if destination is None else r["dest"] == destination)]
    if len(rows) != 1:
        raise ValueError("Missing unique worker-only rejection counter")
    return rows[0]["packets"]


def container_state_file(info, name):
    pid = info["State"]["Pid"]
    if not info["State"].get("Running") or pid <= 0:
        return {}
    try:
        return json.loads((Path("/proc") / str(pid) / "root/run/worker" / name).read_text())
    except (OSError, ValueError):
        return {}


class API:
    """Existing file secret, no credential values in reports or command lines."""
    def __init__(self):
        info = KEY.lstat()
        if KEY.is_symlink() or info.st_uid != 0 or info.st_gid != 62001 or info.st_mode & 0o777 != 0o440:
            raise ValueError("Existing credential file permissions changed; do not replace it")
        self.headers = server_headers(KEY.read_bytes())

    def call(self, path, body=None):
        request = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
            headers={**self.headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    def rows(self, table, **params):
        return self.call("/rest/v1/" + table + "?" + urllib.parse.urlencode(params))

    def rpc(self, name, **body):
        if name.startswith("worker_claim") or name.startswith("worker_heartbeat"):
            raise ValueError("Host controller never claims jobs or sends worker heartbeats")
        return self.call("/rest/v1/rpc/" + name, body)
