"""Operator-only asset preparation after a passed, owned network preflight.

Never starts a worker or accesses the queue. Downloads only the reviewed 500M
and Whisper-small revisions under actual seed cgroup limits. The temporary RSA
private key stays root-only on EC2; only its public half is returned for a later
encrypted transfer of the EXISTING Supabase credential.
"""

import argparse
import grp
import hashlib
import importlib.util
import json
import os
import pwd
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from network_preflight import DOCKER, IMAGE, INSTANCE, NETWORK, POLICY_SHA, QUOTA_SHA, run, service_snapshot

ROOT = Path("/var/lib/noetharaclipz-isolated")
CONFIG = Path("/etc/noetharaclipz-isolated")
COMPOSE_SHA = "fea0b3893ccda93e6273fb511b14412be948593d6efd0ab6c76c78a0d357e2bf"
MODEL = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
REVISION = "7b375e1b73b11138ff12fe22c8f2822d8fe03467"
WHISPER = "536b0662742c02347bc0e980a01041f333bce120"


def require_network(receipt, network):
    if (receipt.get("network_preflight_passed") is not True
            or receipt.get("diagnostic_removed") is not True
            or receipt.get("existing_services_unchanged") is not True
            or receipt.get("policy_sha256") != POLICY_SHA):
        raise ValueError("A successful owned network receipt is required")
    if (network["Id"] != receipt.get("network_id") or network["Name"] != NETWORK
            or network["Labels"].get("io.noetharaclipz.preflight") != receipt.get("probe_id")
            or network["Options"].get("com.docker.network.bridge.name") != "nccz-qa0"
            or network.get("EnableIPv6") or network.get("Containers")):
        raise ValueError("Network changed ownership/configuration or has active consumers")
    if [x["Subnet"] for x in network["IPAM"]["Config"]] != ["172.20.0.0/24"]:
        raise ValueError("Unexpected dedicated subnet")


def require_seed_profile(seed):
    if (seed.get("image") != IMAGE or float(seed.get("cpus", 0)) != 2
            or int(seed.get("mem_limit", 0)) != 8 * 1024**3
            or int(seed.get("memswap_limit", 0)) != 8 * 1024**3
            or seed.get("pids_limit") != 256 or seed.get("user") != "62001:62001"
            or seed.get("secrets") or seed.get("ports") or seed.get("pull_policy") != "never"):
        raise ValueError("Seed profile violates resource/credential/isolation restrictions")
    volumes = seed.get("volumes", [])
    if len(volumes) != 1 or volumes[0]["source"] != str(ROOT / "models") or volumes[0]["target"] != "/models":
        raise ValueError("Seed may mount only its private model directory")
    if any("KEY" in k or "TOKEN" in k or "SECRET" in k for k in seed.get("environment", {})):
        raise ValueError("Seed must not receive account credentials")


def write_new(path, value, uid=0, gid=0, mode=0o600):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), "w") as stream:
        stream.write(value)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def seed_program(quota_source):
    return ("import json\nscope={'__name__':'quota_only'}\nexec(" + repr(quota_source)
            + ",scope)\nresult=scope['evaluate'](scope['read_limits']())\nprint(json.dumps(result),flush=True)\n"
            + "if result.get('passed') is not True: raise SystemExit('Seed kernel limits failed; download blocked')\n"
            + "print('Downloading pinned SmolVLM2-500M and Whisper-small assets only',flush=True)\n"
            + "from noetharaclipz_deploy.assets import main\nmain()\n")


def prepare_paths():
    expected = {"instance_id": INSTANCE, "image": IMAGE, "root": str(ROOT), "uid": 62001, "gid": 62001}
    marker = CONFIG / "ownership.json"
    if os.path.lexists(CONFIG) or os.path.lexists(ROOT):
        if (CONFIG.is_symlink() or ROOT.is_symlink() or not marker.is_file()
                or marker.is_symlink() or json.loads(marker.read_text()) != expected
                or marker.stat().st_uid != 0 or marker.stat().st_mode & 0o077
                or not CONFIG.is_dir() or CONFIG.stat().st_uid != 0
                or CONFIG.stat().st_gid != 62001 or CONFIG.stat().st_mode & 0o777 != 0o750):
            raise ValueError("Foreign or incomplete dedicated paths; review before changing them")
    else:
        CONFIG.mkdir(mode=0o750)
        os.chown(CONFIG, 0, 62001)
        os.chmod(CONFIG, 0o750)
        write_new(marker, json.dumps(expected))
        ROOT.mkdir(mode=0o700)
        os.chown(ROOT, 62001, 62001)
    for directory in (ROOT, ROOT / "models", ROOT / "cache", ROOT / "tmp"):
        if not os.path.lexists(directory):
            directory.mkdir(mode=0o700)
            os.chown(directory, 62001, 62001)
        info = directory.lstat()
        if directory.is_symlink() or not directory.is_dir() or info.st_uid != 62001 or info.st_gid != 62001 or info.st_mode & 0o077:
            raise ValueError("Dedicated volume ownership/mode changed")
    content = ("NC_SUPABASE_KEY_FILE=" + str(CONFIG / "supabase-key") + "\nNC_WORKER_ROOT=" + str(ROOT)
               + "\nNC_WORKER_IMAGE=" + IMAGE + "\nNC_DEPLOY_MODE=standby\nNC_WORKER_OWNER_ID=\n")
    env = CONFIG / "worker.env"
    if os.path.lexists(env):
        if env.is_symlink() or env.read_text() != content or env.stat().st_uid != 0:
            raise ValueError("Existing worker settings differ; do not overwrite")
    else:
        write_new(env, content, gid=62001, mode=0o440)
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip() != INSTANCE:
        raise ValueError("Run only on the authorized EC2 host through existing sudo")
    if not shutil.which("openssl"):
        raise ValueError("Existing OpenSSL is unavailable; do not install or change credentials")
    for lookup in (pwd.getpwuid, grp.getgrgid):
        try:
            lookup(62001)
        except KeyError:
            continue
        raise ValueError("Reserved numeric UID/GID is now assigned to a host account")
    config = args.config_root.resolve()
    for path, digest in ((config / "deploy/worker/compose.yaml", COMPOSE_SHA),
                         (config / "deploy/worker/egress_policy.py", POLICY_SHA),
                         (config / "deploy/worker/check_cgroup_limits.py", QUOTA_SHA)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Reviewed deployment source changed")
    receipt = json.loads((config.parent / "network-preflight.json").read_text())
    network = json.loads(run(DOCKER + ["network", "inspect", NETWORK]))[0]
    require_network(receipt, network)
    if run(DOCKER + ["ps", "-aq", "--filter", "label=com.docker.compose.project=noetharaclipz-isolated"]):
        raise ValueError("A project container already exists; do not run concurrent jobs")
    if run(DOCKER + ["image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Os}}|{{.Architecture}}|{{.Config.User}}"] ) != IMAGE + "|linux|amd64|62001:62001":
        raise ValueError("Reviewed image identity changed")
    spec = importlib.util.spec_from_file_location("approved_policy", config / "deploy/worker/egress_policy.py")
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    for original in policy.proposal()["apply_after_approval"]:
        command = original.copy()
        if command[3] == "-N":
            continue
        if command[3] == "-I":
            del command[5]
        command[3] = "-C"
        run(command)
    for chain, target in (("FORWARD", "DOCKER-USER"), ("INPUT", "REJECT"), ("DOCKER-USER", "NCZQA_EGRESS")):
        rules = [x for x in run(["iptables", "--wait", "5", "-S", chain]).splitlines() if x.startswith("-A ")]
        first = shlex.split(rules[0]) if rules else []
        if ("-j" not in first or first[first.index("-j") + 1] != target
                or chain != "FORWARD" and ("-i" not in first or first[first.index("-i") + 1] != "nccz-qa0")):
            raise ValueError("Live scoped firewall ordering changed")
    expected_count = sum("-A" in x for x in policy.proposal()["apply_after_approval"])
    if sum(x.startswith("-A ") for x in run(["iptables", "--wait", "5", "-S", "NCZQA_EGRESS"]).splitlines()) != expected_count:
        raise ValueError("Unexpected additional egress rules")
    ram = int(next(x.split()[1] for x in Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:"))) * 1024
    if ram < 10 * 1024**3 or shutil.disk_usage("/var/lib").free < 20 * 1024**3:
        raise ValueError("Insufficient spare host RAM/disk")
    before = service_snapshot()
    env = prepare_paths()
    compose = DOCKER + ["compose", "--project-name", "noetharaclipz-isolated", "--env-file", str(env),
                        "-f", str(config / "deploy/worker/compose.yaml"), "--profile", "tools"]
    profile = json.loads(run(compose + ["config", "--format", "json"]))["services"]["seed"]
    require_seed_profile(profile)
    code = seed_program((config / "deploy/worker/check_cgroup_limits.py").read_text())
    name = "nccz-assets-" + uuid.uuid4().hex
    try:
        result = subprocess.run(compose + ["run", "--rm", "--no-deps", "--name", name, "--interactive", "-T",
            "-e", "HF_HUB_DISABLE_PROGRESS_BARS=1", "--entrypoint", "python", "seed", "-"], input=code, text=True, timeout=1200)
        if result.returncode:
            raise ValueError("Asset seeding failed; keep worker stopped and preserve the private cache")
    finally:
        current = run(DOCKER + ["ps", "-aq", "--filter", "name=^/" + name + "$"]).split()
        if current:
            info = json.loads(run(DOCKER + ["inspect", current[0], "--format", "{{json .Config.Labels}}"] ))
            if info.get("com.docker.compose.project") != "noetharaclipz-isolated" or info.get("com.docker.compose.service") != "seed":
                raise ValueError("Seed container ownership mismatch; do not remove another service")
            run(DOCKER + ["rm", "-f", *current])
    if service_snapshot() != before:
        raise ValueError("Existing service health/start state changed; do not start a worker")
    manifest = json.loads((ROOT / "models/manifest.json").read_text())
    if manifest != {"video_model": MODEL, "video_revision": REVISION, "whisper_revision": WHISPER}:
        raise ValueError("Pinned asset manifest mismatch")
    private = CONFIG / "transport.key"
    if os.path.lexists(private):
        info = private.lstat()
        if private.is_symlink() or not private.is_file() or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("Unexpected encryption-key ownership")
    else:
        pending = CONFIG / ("transport-pending-" + uuid.uuid4().hex)
        write_new(pending, "")
        try:
            run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:4096", "-out", str(pending)], timeout=60)
            run(["openssl", "pkey", "-in", str(pending), "-pubout"])
            os.link(pending, private, follow_symlinks=False)  # Refuse to replace any existing key.
        finally:
            pending.unlink(missing_ok=True)
    public = run(["openssl", "pkey", "-in", str(private), "-pubout"])
    print(json.dumps({"assets_seeded": True, "asset_manifest": manifest, "existing_services_unchanged": True,
                      "worker_started": False, "queue_access": False, "provider": "local", "gemini_enabled": False,
                      "public_transport_key": public, "private_key_stays_on_ec2": True}, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"failed": True, "reason": str(error), "worker_started": False}), file=sys.stderr)
        raise SystemExit(1) from None
