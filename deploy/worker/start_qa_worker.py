"""Unseal the existing key and start ONE fixed-window, owner-scoped QA worker.

Operator-only, existing host/image/network/assets. No image build/pull, migrations,
global claims, host service changes or public ports. Never log credential data.
"""

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import shlex
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from credential_envelope import server_headers, unseal
from network_preflight import DOCKER, IMAGE, INSTANCE, NETWORK, POLICY_SHA, QUOTA_SHA, run, service_snapshot
from prepare_qa_assets import CONFIG, ROOT, COMPOSE_SHA, MODEL, REVISION, WHISPER, prepare_paths, require_network, write_new

QA_SHA = "783f90824b850c821718de9460e1269c31eb0ed3f7710f3a4dbfa06cc94bf558"
PROJECT = "https://zxdnjnsghdnviflahvry.supabase.co"


def require_profile(profile, owner, deadline, trial):
    env = profile["environment"]
    wanted = {"NC_AI_PROVIDER": "local", "GEMINI_FREE_TIER_VERIFIED": "false",
              "NC_GLOBAL_QUEUE_APPROVED": "false", "NC_DEPLOY_MODE": "qa",
              "NC_WORKER_OWNER_ID": owner, "NC_QA_STOP_AT": str(deadline), "NC_QA_TRIAL_ID": trial,
              "SUPABASE_URL": PROJECT, "NC_SUPABASE_KEY_FILE": "/run/secrets/supabase_key"}
    if any(env.get(key) != value for key, value in wanted.items()):
        raise ValueError("QA provider/owner/deadline configuration mismatch")
    if any(key not in wanted for key in env):
        raise ValueError("Unexpected environment variable in QA profile")
    if (profile.get("image") != IMAGE or profile.get("platform") != "linux/amd64"
            or profile.get("pull_policy") != "never" or float(profile.get("cpus", 0)) != 2
            or int(profile.get("mem_limit", 0)) != 8 * 1024**3
            or int(profile.get("memswap_limit", 0)) != 8 * 1024**3
            or profile.get("pids_limit") != 256 or profile.get("user") != "62001:62001"
            or not profile.get("read_only") or not profile.get("init")
            or profile.get("ports") or profile.get("privileged") or profile.get("network_mode")
            or profile.get("restart") != "on-failure:3" or profile.get("cap_drop") != ["ALL"]
            or profile.get("entrypoint") != ["python", "/run/qa-deadline.py"]):
        raise ValueError("QA resource, image or process isolation mismatch")
    expected = {"/models": (str(ROOT / "models"), True),
                "/data/cache": (str(ROOT / "cache"), False),
                "/data/tmp": (str(ROOT / "tmp"), False),
                "/run/qa-deadline.py": (str(CONFIG / "qa-deadline.py"), True),
                "/run/qa-limits.py": (str(CONFIG / "qa-limits.py"), True)}
    actual = {v["target"]: (v["source"], v.get("read_only", False)) for v in profile["volumes"]}
    if actual != expected or len(profile["volumes"]) != len(expected):
        raise ValueError("Unexpected QA filesystem mount")
    if profile.get("secrets") != [{"source": "supabase_key", "target": "/run/secrets/supabase_key"}]:
        raise ValueError("Unexpected QA secret mount")
    if set(profile["networks"]) != {"worker-egress"} or profile.get("dns") != ["172.31.0.2"]:
        raise ValueError("Unexpected QA network")
    if (profile.get("security_opt") != ["no-new-privileges:true"]
            or profile.get("sysctls") != {"net.ipv6.conf.all.disable_ipv6": "1", "net.ipv6.conf.default.disable_ipv6": "1"}):
        raise ValueError("Unexpected QA namespace security settings")


def require_container(info, owner, trial):
    config, host = info["Config"], info["HostConfig"]
    env = dict(value.split("=", 1) for value in config["Env"])
    if (config.get("Image") != IMAGE or info["Image"] not in (
            IMAGE, "sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5")
            or config["Labels"].get("io.noetharaclipz.trial") != trial
            or config["Labels"].get("com.docker.compose.project") != "noetharaclipz-isolated"
            or config["User"] != "62001:62001"
            or config["Entrypoint"] != ["python", "/run/qa-deadline.py"]
            or host["Memory"] != 8 * 1024**3 or host["MemorySwap"] != 8 * 1024**3
            or host["NanoCpus"] != 2_000_000_000 or host["PidsLimit"] != 256
            or not host["ReadonlyRootfs"] or host["Privileged"] or host.get("PortBindings")
            or host["RestartPolicy"] != {"Name": "on-failure", "MaximumRetryCount": 3}
            or env.get("NC_WORKER_OWNER_ID") != owner or env.get("NC_DEPLOY_MODE") != "qa"
            or env.get("NC_AI_PROVIDER") != "local" or env.get("GEMINI_FREE_TIER_VERIFIED") != "false"
            or env.get("NC_GLOBAL_QUEUE_APPROVED") != "false"):
        raise ValueError("Actual Docker configuration differs from the approved QA profile")
    for name in ("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY", "NVIDIA_API_KEY"):
        if name in env:
            raise ValueError("Account credential must be a file secret, not Docker environment metadata")
    if set(info["NetworkSettings"]["Networks"]) != {NETWORK}:
        raise ValueError("Actual container network differs")


def existing_services_unchanged(before):
    # Do not include the new container's initial Docker health "starting" state.
    ids = [line.split()[0] for line in before]
    template = '{{.Id}} {{.State.StartedAt}} {{.RestartCount}} {{with index .State "Health"}}{{.Status}}{{else}}none{{end}}'
    return sorted(run(DOCKER + ["inspect", "--format", template, *ids]).splitlines()) == before


def firewall(config):
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
            raise ValueError("Live dedicated firewall ordering changed")
    expected = sum("-A" in x for x in policy.proposal()["apply_after_approval"])
    if sum(x.startswith("-A ") for x in run(["iptables", "--wait", "5", "-S", "NCZQA_EGRESS"]).splitlines()) != expected:
        raise ValueError("Unexpected dedicated egress rules")


def verified_key(payload):
    key = unseal(payload["credential_envelope"], CONFIG / "transport.key")
    request = urllib.request.Request(PROJECT + "/rest/v1/rpc/worker_protocol", data=b"{}",
        headers={**server_headers(key), "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        protocol = json.load(response)
    if (protocol.get("version") != 1 or "local-smolvlm2" not in protocol.get("providers", [])
            or not protocol.get("scoped_claim") or not protocol.get("scoped_health")):
        raise ValueError("Authorized hosted worker protocol is not ready for scoped local QA")
    return key


def save_bytes(path, value, gid=62001):
    if os.path.lexists(path):
        stat = path.lstat()
        if (path.is_symlink() or not path.is_file() or stat.st_uid != 0 or stat.st_gid != gid
                or stat.st_mode & 0o777 != 0o440 or not hmac.compare_digest(path.read_bytes(), value)):
            raise ValueError("Existing private QA file differs; refusing to replace it")
    else:
        write_new(path, value.decode(), gid=gid, mode=0o440)


def trial_override(trial, deadline):
    return {"services": {"worker": {
        "entrypoint": ["python", "/run/qa-deadline.py"],
        "labels": {"io.noetharaclipz.trial": trial},
        "environment": {"NC_QA_STOP_AT": str(deadline), "NC_QA_TRIAL_ID": trial},
        "volumes": [{"type": "bind", "source": str(CONFIG / source), "target": target,
                     "read_only": True, "bind": {"create_host_path": False}}
                    for source, target in (("qa-deadline.py", "/run/qa-deadline.py"), ("qa-limits.py", "/run/qa-limits.py"))]
    }}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or Path("/sys/devices/virtual/dmi/id/board_asset_tag").read_text().strip() != INSTANCE:
        raise ValueError("Run only on the authorized EC2 host through existing sudo")
    # Clear only this controller's inherited endpoint/Compose/interpolation selectors.
    for name in list(os.environ):
        if name.startswith(("NC_", "COMPOSE_", "DOCKER_")):
            os.environ.pop(name)
    config = args.config_root.resolve()
    payload = json.loads(args.payload.read_text())
    owner = str(UUID(payload["credential_envelope"]["owner_id"]))
    trial = str(UUID(payload["credential_envelope"]["trial_id"]))
    for name, digest in (("compose.yaml", COMPOSE_SHA), ("compose.qa.yaml", QA_SHA),
                         ("egress_policy.py", POLICY_SHA), ("check_cgroup_limits.py", QUOTA_SHA)):
        if hashlib.sha256((config / "deploy/worker" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Reviewed deployment source hash mismatch: " + name)
    receipt = json.loads((config.parent / "network-preflight.json").read_text())
    require_network(receipt, json.loads(run(DOCKER + ["network", "inspect", NETWORK]))[0])
    firewall(config)
    if run(DOCKER + ["ps", "-aq", "--filter", "label=com.docker.compose.project=noetharaclipz-isolated"]):
        raise ValueError("A dedicated project container already exists; do not start another trial")
    if run(DOCKER + ["image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Os}}|{{.Architecture}}|{{.Config.User}}"] ) != IMAGE + "|linux|amd64|62001:62001":
        raise ValueError("Reviewed image identity changed")
    ram = int(next(x.split()[1] for x in Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:"))) * 1024
    if ram < 10 * 1024**3 or shutil.disk_usage("/var/lib").free < 20 * 1024**3:
        raise ValueError("Host no longer has approved spare capacity")
    before = service_snapshot()
    env_file = prepare_paths()
    if json.loads((ROOT / "models/manifest.json").read_text()) != {"video_model": MODEL, "video_revision": REVISION, "whisper_revision": WHISPER}:
        raise ValueError("Pinned model assets are not ready")
    state_path = CONFIG / "qa-trial.json"
    if os.path.lexists(state_path):
        raise ValueError("A trial receipt already exists; never reset its fixed deadline")
    key = verified_key(payload)
    save_bytes(CONFIG / "supabase-key", key.strip() + b"\n")
    del key
    save_bytes(CONFIG / "qa-owner.env", ("NC_QA_OWNER_ID=" + owner + "\n").encode())
    save_bytes(CONFIG / "qa-deadline.py", Path(__file__).with_name("qa_deadline.py").read_bytes())
    save_bytes(CONFIG / "qa-limits.py", (config / "deploy/worker/check_cgroup_limits.py").read_bytes())
    deadline = int(time.time()) + 1800
    override = trial_override(trial, deadline)
    override_path = CONFIG / "compose.trial.json"
    save_bytes(override_path, json.dumps(override).encode())
    compose = DOCKER + ["compose", "--project-name", "noetharaclipz-isolated", "--env-file", str(env_file),
        "--env-file", str(CONFIG / "qa-owner.env"), "-f", str(config / "deploy/worker/compose.yaml"),
        "-f", str(config / "deploy/worker/compose.qa.yaml"), "-f", str(override_path)]
    merged = json.loads(run(compose + ["config", "--format", "json"]))
    require_profile(merged["services"]["worker"], owner, deadline, trial)
    if merged["secrets"]["supabase_key"]["file"] != str(CONFIG / "supabase-key"):
        raise ValueError("Unexpected credential source")
    state = {"trial_id": trial, "owner_id": owner, "stop_at": deadline, "image": IMAGE,
             "started": False, "ready": False, "global_consumption": False, "gemini_enabled": False}
    write_new(state_path, json.dumps(state))
    cid = None
    try:
        # No depends_on exists; create just this worker, never seed or other apps.
        run(compose + ["create", "--no-build", "--pull", "never", "worker"], timeout=90)
        ids = run(compose + ["ps", "--all", "-q", "worker"]).split()
        if len(ids) != 1:
            raise ValueError("Expected exactly one QA worker container")
        cid = ids[0]
        info = json.loads(run(DOCKER + ["inspect", cid]))[0]
        require_container(info, owner, trial)
        if not existing_services_unchanged(before):
            raise ValueError("Existing service state changed before startup")
        run(DOCKER + ["start", cid])
        state.update(started=True, container_id=cid)
        state_path.write_text(json.dumps(state))
        print(json.dumps({"phase": "qa_worker_started_waiting_for_local_model", "container_id": cid,
                          "maximum_seconds": 1800, "global_consumption": False}), flush=True)
        wait_until = time.monotonic() + 300
        ready = False
        while time.monotonic() < wait_until:
            status = json.loads(run(DOCKER + ["inspect", cid, "--format", "{{json .State}}"] ))
            if not status.get("Running"):
                raise ValueError("QA worker exited before readiness; inspect only its bounded logs")
            # This local probe never loads models or claims jobs.
            probe = "import json,pathlib; p=pathlib.Path('/run/worker/health.json'); print(p.read_text() if p.exists() else '{}')"
            health = json.loads(run(DOCKER + ["exec", cid, "python", "-c", probe]))
            if health.get("ai_ready") is True and health.get("mode") == "qa" and 0 <= time.time() - health.get("at", 0) < 90:
                ready = True
                break
            time.sleep(3)
        if not ready:
            raise ValueError("QA worker failed its model/credential/readiness gate within 300 seconds")
        # Compare the exact original services, excluding only this new QA container.
        if not existing_services_unchanged(before):
            raise ValueError("Existing service state changed; stop only QA")
        state.update(ready=True, existing_services_unchanged=True,
                     stop_at_utc=datetime.fromtimestamp(deadline, timezone.utc).isoformat(),
                     remaining_seconds=max(0, deadline - int(time.time())), provider="local-smolvlm2")
        state_path.write_text(json.dumps(state))
        (CONFIG / "transport.key").unlink()
        print(json.dumps(state, indent=2), flush=True)
    except Exception:
        if cid:
            labels = json.loads(run(DOCKER + ["inspect", cid, "--format", "{{json .Config.Labels}}"] ))
            if labels.get("io.noetharaclipz.trial") == trial:
                run(DOCKER + ["stop", "--time", "95", cid], timeout=105)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"failed": True, "reason": str(error), "qa_startup_stopped": True}), file=sys.stderr)
        raise SystemExit(1) from None
