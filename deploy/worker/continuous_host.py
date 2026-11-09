"""Dedicated pilot controller. Deployment commands require a reviewed manifest.

Not run by imports, build, tests, or bundle preparation. All Docker mutations
check the exact deployment label. No legacy/global claims, schema changes,
shared-chain flushes, old-trial operations or credential output.
"""

import argparse
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
import shlex
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

from continuous_metrics import DurableMetrics, atomic
from continuous_policy import digest, manifest_hash, restart_delay, validate_manifest
from egress_policy import proposal
from reliability_metrics import cgroup_path, read_sample
from reliability_platform import (
    API,
    DOCKER,
    IMAGE,
    KEY,
    MODELS,
    NETWORK,
    container_state_file,
    docker,
    firewall_fingerprint,
    inspect,
    mkdir,
    reject_counter,
    require_host,
    run,
    service_snapshot,
    verify_network,
    verify_probe_destinations,
)
from reliability_probe import TARGETS

ETC = Path("/etc/noetharaclipz-isolated/continuous")
DATA = Path("/var/lib/noetharaclipz-isolated/continuous")
log = logging.getLogger("nccz.continuous")


def available_ram():
    return (
        int(
            next(
                x.split()[1]
                for x in Path("/proc/meminfo").read_text().splitlines()
                if x.startswith("MemAvailable:")
            )
        )
        * 1024
    )


def load(path, active=True):
    info = path.lstat()
    if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError("Manifest must be root-owned and not writable by the worker")
    m = json.loads(path.read_text())
    validate_manifest(m, time.time() if active else m["not_before"])
    cfg = ETC / m["deployment_id"]
    if path.resolve() != cfg / "public/manifest.json":
        raise ValueError("Manifest outside its dedicated immutable deployment")
    for name, expected in m["files"].items():
        file = cfg / "code" / name
        info = file.lstat()
        if (
            file.is_symlink()
            or info.st_uid != 0
            or info.st_mode & 0o022
            or digest(file.read_bytes()) != expected
        ):
            raise ValueError("Reviewed application/configuration bundle changed")
    actual = {str(p.relative_to(cfg / "code")) for p in (cfg / "code").rglob("*.py")}
    if actual != set(m["files"]):
        raise ValueError("Unreviewed Python module in immutable bundle")
    for name, expected in m["unit_sha256"].items():
        file = cfg / "systemd" / name
        if (
            file.is_symlink()
            or file.stat().st_uid != 0
            or file.stat().st_mode & 0o022
            or digest(file.read_bytes()) != expected
        ):
            raise ValueError("Reviewed unit configuration changed")
    return m, cfg, DATA / m["deployment_id"]


def install(bundle_path, manifest_path):
    """Future preparation only: install private files, never start/enable anything."""
    require_host()
    bundle, m = (
        json.loads(bundle_path.read_text()),
        json.loads(manifest_path.read_text()),
    )
    validate_manifest(m, time.time())
    if (
        m["files"] != bundle["sha256"]
        or bundle.get("base_image") != IMAGE
        or bundle.get("source_dirty") is not False
        or set(bundle["files"]) != set(m["files"])
        or bundle.get("unit_sha256") != m["unit_sha256"]
        or set(bundle.get("units", {})) != set(m["unit_sha256"])
    ):
        raise ValueError("Manifest must refer to a committed reviewed source bundle")
    if any(
        digest(text.encode()) != m["files"][name]
        for name, text in bundle["files"].items()
    ):
        raise ValueError("Incomplete or changed source bundle")
    if any(
        digest(text.encode()) != m["unit_sha256"][name]
        for name, text in bundle["units"].items()
    ):
        raise ValueError("Changed unit files in source bundle")
    cfg, data = ETC / m["deployment_id"], DATA / m["deployment_id"]
    if cfg.exists() or data.exists():
        raise ValueError("Never overwrite an existing deployment, budget or evidence")
    verify_network()
    firewall_fingerprint(verify=True)
    service_snapshot()
    for root in (ETC, DATA):
        mkdir(root)
    mkdir(cfg, gid=62001, mode=0o750)
    for name in ("code", "public", "gates", "systemd"):
        mkdir(cfg / name, gid=62001, mode=0o750)
    for name, text in bundle["units"].items():
        unit = cfg / "systemd" / name
        unit.write_text(text)
        os.chown(unit, 0, 62001)
        unit.chmod(0o440)
    for name, text in bundle["files"].items():
        if name not in m["files"] or digest(text.encode()) != m["files"][name]:
            raise ValueError("Source bundle checksum mismatch")
        path = cfg / "code" / name
        for parent in reversed(path.parent.relative_to(cfg).parents):
            if str(parent) != ".":
                mkdir(cfg / parent, gid=62001, mode=0o750)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chown(path.parent, 0, 62001)
        path.parent.chmod(0o750)
        path.write_text(text)
        os.chown(path, 0, 62001)
        path.chmod(0o440)
    atomic(cfg / "public/manifest.json", m, gid=62001, mode=0o440)
    mkdir(data)
    for name in ("cache", "tmp"):
        mkdir(data / name, uid=62001, gid=62001)
    mkdir(data / "reports")
    return {
        "installed": True,
        "worker_started": False,
        "unit_enabled": False,
        "manifest_sha256": manifest_hash(m),
    }


def owned(info, m):
    if (
        info["Config"].get("Labels", {}).get("io.noetharaclipz.continuous")
        != m["deployment_id"]
        or info["Name"].lstrip("/") != "nccz-continuous-" + m["deployment_id"][:8]
    ):
        raise ValueError(
            "Refusing a mutation on another container or an earlier QA trial"
        )


def create_command(m, cfg, data):
    args = DOCKER + [
        "create",
        "--name",
        "nccz-continuous-" + m["deployment_id"][:8],
        "--pull=never",
        "--platform=linux/amd64",
        "--network",
        NETWORK,
        "--dns",
        "172.31.0.2",
        "--user",
        "62001:62001",
        "--init",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--memory",
        "8g",
        "--memory-swap",
        "8g",
        "--cpus",
        "2",
        "--cpu-shares",
        "256",
        "--pids-limit",
        "256",
        "--oom-score-adj",
        "500",
        "--restart",
        "no",
        "--stop-timeout",
        "95",
        "--log-driver",
        "json-file",
        "--log-opt",
        "max-size=10m",
        "--log-opt",
        "max-file=5",
        "--log-opt",
        "compress=true",
        "--sysctl",
        "net.ipv6.conf.all.disable_ipv6=1",
        "--sysctl",
        "net.ipv6.conf.default.disable_ipv6=1",
        "--label",
        "io.noetharaclipz.continuous=" + m["deployment_id"],
    ]
    env = {
        "NC_DEPLOY_MODE": "continuous",
        "NC_QUEUE_MODE": "consented",
        "NC_AI_PROVIDER": "local",
        "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_GLOBAL_QUEUE_APPROVED": "false",
        "NC_WORKER_OWNER_ID": m["owner_id"],
        "NC_OWNER_CONSENT_ID": m["consent_id"],
        "PYTHONPATH": "/run/continuous/code/host:/app/worker:/app/deploy/worker",
    }
    for key, value in env.items():
        args += ["--env", key + "=" + value]
    for src, dst, ro in (
        (MODELS, "/models", True),
        (data / "cache", "/data/cache", False),
        (data / "tmp", "/data/tmp", False),
        (cfg, "/run/continuous", True),
        (cfg / "code/worker", "/app/worker", True),
        (
            cfg / "code/runtime/noetharaclipz_deploy",
            "/app/deploy/worker/noetharaclipz_deploy",
            True,
        ),
        (KEY, "/run/secrets/supabase_key", True),
    ):
        args += [
            "--mount",
            "type=bind,src=" + str(src) + ",dst=" + dst + (",readonly" if ro else ""),
        ]
    for dst in ("/tmp", "/run/worker"):
        args += [
            "--tmpfs",
            dst + ":rw,noexec,nosuid,nodev,size=16m,uid=62001,gid=62001,mode=0700",
        ]
    return args + [
        "--entrypoint",
        "python",
        IMAGE,
        "/run/continuous/code/host/continuous_entry.py",
    ]


def validate_container(info, m, cfg, data):
    owned(info, m)
    h, c = info["HostConfig"], info["Config"]
    expected_env = {
        "NC_DEPLOY_MODE": "continuous",
        "NC_QUEUE_MODE": "consented",
        "NC_AI_PROVIDER": "local",
        "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_GLOBAL_QUEUE_APPROVED": "false",
        "NC_WORKER_OWNER_ID": m["owner_id"],
        "NC_OWNER_CONSENT_ID": m["consent_id"],
    }
    actual_env = dict(v.split("=", 1) for v in c["Env"])
    if (
        c["Image"] != IMAGE
        or c["User"] != "62001:62001"
        or c["Entrypoint"] != ["python"]
        or c["Cmd"] != ["/run/continuous/code/host/continuous_entry.py"]
        or h["Memory"] != 8 * 1024**3
        or h["MemorySwap"] != 8 * 1024**3
        or h["NanoCpus"] != 2_000_000_000
        or h["PidsLimit"] != 256
        or not h["Init"]
        or h["Privileged"]
        or not h["ReadonlyRootfs"]
        or h.get("PortBindings")
        or h["RestartPolicy"]["Name"] != "no"
        or h["NetworkMode"] != NETWORK
        or h["Dns"] != ["172.31.0.2"]
        or "ALL" not in h["CapDrop"]
        or not any(x.startswith("no-new-privileges") for x in h["SecurityOpt"])
        or any(actual_env.get(k) != v for k, v in expected_env.items())
    ):
        raise ValueError("Container isolation/profile drift")
    mounts = {
        x["Destination"]: (x["Source"], x["RW"])
        for x in info["Mounts"]
        if x["Type"] == "bind"
    }
    expected = {
        "/models": (str(MODELS), False),
        "/data/cache": (str(data / "cache"), True),
        "/data/tmp": (str(data / "tmp"), True),
        "/run/continuous": (str(cfg), False),
        "/app/worker": (str(cfg / "code/worker"), False),
        "/app/deploy/worker/noetharaclipz_deploy": (
            str(cfg / "code/runtime/noetharaclipz_deploy"),
            False,
        ),
        "/run/secrets/supabase_key": (str(KEY), False),
    }
    if mounts != expected or any(
        h["Sysctls"].get("net.ipv6.conf." + k + ".disable_ipv6") != "1"
        for k in ("all", "default")
    ):
        raise ValueError("Dedicated mounts or IPv6 isolation changed")


def restore_isolation(m):
    """Future opt-in: restore only the exact approved worker chain/hooks."""
    validate_manifest(m, time.time())
    if m.get("restore_isolation") is not True:
        firewall_fingerprint(verify=True)
        return
    verify_network()
    commands = proposal()["apply_after_approval"]

    def normalize(line):
        fields = shlex.split(line)
        protocol = fields[fields.index("-p") + 1] if "-p" in fields else None
        for implied in ("tcp", "udp"):
            if protocol == implied:
                for index in range(len(fields) - 2, -1, -1):
                    if fields[index : index + 2] == ["-m", implied]:
                        del fields[index : index + 2]
        if "--ctstate" in fields:
            index = fields.index("--ctstate") + 1
            fields[index] = ",".join(sorted(fields[index].split(",")))
        return fields

    expected = [normalize(" ".join(c[3:])) for c in commands if c[3] == "-A"]
    current = run(["iptables", "--wait", "5", "-S"]).splitlines()
    if not next((x for x in current if x.startswith("-A FORWARD ")), "").startswith(
        "-A FORWARD -j DOCKER-USER"
    ):
        raise ValueError(
            "Docker forwarding prerequisite missing; do not alter shared forwarding"
        )
    present = [x for x in current if x.startswith("-A NCZQA_EGRESS ")]
    if [normalize(line) for line in present] != expected[: len(present)]:
        raise ValueError("Foreign or reordered rules in reserved worker chain")
    if "-N NCZQA_EGRESS" not in current:
        run(commands[0])
    for command in [c for c in commands if c[3] == "-A"][len(present) :]:
        run(command)
    for command in [c for c in commands if c[3] == "-I"]:
        chain = command[4]
        line = " ".join(["-A", chain] + command[6:])
        rules = [x for x in current if x.startswith("-A " + chain + " ")]
        normalized = [normalize(rule) for rule in rules]
        if normalize(line) in normalized and normalized[0] != normalize(line):
            raise ValueError(
                "Worker hook is not first; no shared rules will be rearranged"
            )
        if normalize(line) not in normalized:
            if any("nccz-qa0" in x for x in rules):
                raise ValueError("Foreign hook already targets the reserved bridge")
            run(command)
    firewall_fingerprint(verify=True)


class Platform:
    def __init__(self, path):
        self.path = path
        self.m, self.cfg, self.data = load(path)
        self.reports = self.data / "reports"
        self.api = None
        self.cid = None
        self.baseline = None
        self.metrics = DurableMetrics(self.reports)
        self.lock = threading.Lock()
        self.sampler_stop = threading.Event()
        self.sampling_fault = threading.Event()
        self.last_sample = 0
        self.last_stage = None
        self.fast_stop = False
        record = self.reports / "container.json"
        if record.exists():
            self.cid = json.loads(record.read_text())["id"]
            validate_container(inspect(self.cid), self.m, self.cfg, self.data)

    def status(self, stage, **fields):
        atomic(
            self.reports / "status.json",
            {"stage": stage, "at": time.time(), "global_processing": False, **fields},
        )
        if stage != self.last_stage:
            log.info("stage=%s", stage)
            self.last_stage = stage

    def preflight(self):
        if manifest_hash(load(self.path)[0]) != manifest_hash(self.m):
            raise ValueError(
                "Active manifest changed; stop before switching deployment"
            )
        if (self.data / "revoked.json").exists() or (
            self.data / "blocked.json"
        ).exists():
            raise ValueError("Deployment revoked or latched; do not reset its approval")
        verify_network()
        fingerprint = firewall_fingerprint(verify=True)
        verify_probe_destinations(TARGETS)
        if (
            docker(
                "image",
                "inspect",
                IMAGE,
                "--format",
                "{{.Id}}|{{.Os}}|{{.Architecture}}|{{.Config.User}}",
            )
            != IMAGE + "|linux|amd64|62001:62001"
        ):
            raise ValueError("Reviewed image identity changed")
        expected_assets = {
            "video_model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
            "video_revision": "7b375e1b73b11138ff12fe22c8f2822d8fe03467",
            "whisper_revision": "536b0662742c02347bc0e980a01041f333bce120",
        }
        if json.loads((MODELS / "manifest.json").read_text()) != expected_assets:
            raise ValueError("Pinned model assets changed")
        if shutil.disk_usage(self.data).free < 20 * 1024**3:
            raise ValueError("Host disk headroom insufficient")
        ram = available_ram()
        if ram < 10 * 1024**3:
            raise ValueError("Host RAM headroom insufficient")
        for name in ("cache", "tmp"):
            info = (self.data / name).lstat()
            if (self.data / name).is_symlink() or (
                info.st_uid,
                info.st_gid,
                info.st_mode & 0o777,
            ) != (62001, 62001, 0o700):
                raise ValueError("Dedicated writable volume metadata changed")
        services = service_snapshot(excluded=self.cid)
        others = docker(
            "ps", "-q", "--no-trunc", "--filter", "label=io.noetharaclipz.continuous"
        ).split()
        if any(x != self.cid for x in others):
            raise ValueError("Another continuous worker is running")
        if self.baseline is not None and services != self.baseline:
            raise ValueError("Existing services changed; stop only this worker")
        self.baseline, self.fingerprint = services, fingerprint
        # Only after host security: read existing private key for consent status.
        self.api = API()
        protocol = self.api.rpc("worker_continuous_protocol")
        if (
            protocol.get("version") != 2
            or protocol.get("contract") != "future-jobs-only-v1"
            or protocol.get("global_claim") is not False
            or protocol.get("provider") != "local-smolvlm2"
            or not all(
                protocol.get(k) is True
                for k in ("future_jobs_only", "revocable", "job_exclusions", "audit")
            )
        ):
            raise ValueError("Reviewed server consent contract is not deployed")
        self.consent()

    def consent(self):
        status = self.api.rpc(
            "worker_consent_status",
            owner=self.m["owner_id"],
            consent=self.m["consent_id"],
        )
        if (
            status.get("authorized") is not True
            or status.get("owner_id") != self.m["owner_id"]
            or status.get("consent_id") != self.m["consent_id"]
            or status.get("future_jobs_only") is not True
            or datetime.fromisoformat(status["expires_at"]).timestamp()
            < self.m["valid_until"]
        ):
            raise ValueError("Owner consent inactive, replaced or too short")
        return status

    def protected(self):
        row = self.api.rows(
            "processing_jobs", id="eq.9c5c8869-ec2e-4a3e-927d-697615bb58a3"
        )[0]
        hashes = [
            digest(json.dumps(row, sort_keys=True, **kw).encode())
            for kw in ({}, {"separators": (",", ":")})
        ]
        if (
            "deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb"
            not in hashes
        ):
            raise ValueError("Protected upload changed; do not process any job")

    def ensure_container(self):
        record = self.reports / "container.json"
        if record.exists():
            self.cid = json.loads(record.read_text())["id"]
            info = inspect(self.cid)
            validate_container(info, self.m, self.cfg, self.data)
            return
        self.cid = run(create_command(self.m, self.cfg, self.data))
        validate_container(inspect(self.cid), self.m, self.cfg, self.data)
        atomic(record, {"id": self.cid, "deployment_id": self.m["deployment_id"]})

    def revoke_grant(self):
        (self.cfg / "gates/grant.json").unlink(missing_ok=True)

    def stop_owned(self):
        self.revoke_grant()
        atomic(
            self.cfg / "gates/stop.json",
            {"fast": self.fast_stop},
            mode=0o440,
            gid=62001,
        )
        if self.cid:
            info = inspect(self.cid)
            owned(info, self.m)
            if info["State"].get("Running") or info["State"].get("Restarting"):
                grace = 15 if self.fast_stop else 95
                docker("stop", "--time", str(grace), self.cid, timeout=grace + 10)

    def sample(self):
        if not self.cid:
            return
        with self.lock:
            info = inspect(self.cid)
            if not info["State"].get("Running"):
                return
            path = cgroup_path(info["State"]["Pid"])
            values = read_sample(path)
            values["pids.max"] = (path / "pids.max").read_text().strip()
            values["memory.swap.max"] = (path / "memory.swap.max").read_text().strip()
            if (
                values.get("memory.max") != str(8 * 1024**3)
                or values.get("cpu.max") != "200000 100000"
                or values["pids.max"] != "256"
                or values["memory.swap.max"] != "0"
            ):
                self.revoke_grant()
                raise ValueError("Live kernel limits changed")
            state = container_state_file(info, "continuous-state.json")
            final = state.get("phase") == "finalizing"
            generation = info["State"]["StartedAt"]
            self.metrics.add(
                generation, values, time.monotonic(), time.time(), final=final
            )
            self.last_sample = time.monotonic()
            if final:
                atomic(
                    self.cfg / "gates/finalized.json",
                    {"nonce": state["nonce"]},
                    mode=0o440,
                    gid=62001,
                )

    def sampling(self):
        while not self.sampler_stop.wait(2):
            try:
                self.sample()
            except (OSError, RuntimeError, ValueError):
                # A missing sample is recorded as a gap; never fabricate zero.
                self.revoke_grant()
                self.sampling_fault.set()

    def prove(self):
        verify_probe_destinations(TARGETS)
        proof = {"passed": False, "denials": []}
        proof["public"] = json.loads(
            docker(
                "exec",
                self.cid,
                "python",
                "/run/continuous/code/host/reliability_probe.py",
                "public",
            )
        )
        for i, target in enumerate(TARGETS):
            before = reject_counter(target[3], target[4])
            result = json.loads(
                docker(
                    "exec",
                    self.cid,
                    "python",
                    "/run/continuous/code/host/reliability_probe.py",
                    "deny",
                    str(i),
                )
            )
            delta = reject_counter(target[3], target[4]) - before
            proof["denials"].append(
                {"target": target[0], "delta": delta, "blocked": result.get("blocked")}
            )
            atomic(self.reports / "network-attempt.json", proof)
            if (
                result.get("blocked") is not True
                or delta <= 0
                or result.get("target") != target[0]
                or result.get("address") != target[1]
                or result.get("port") != target[2]
            ):
                raise ValueError("Scoped network rejection proof failed")
        proof["passed"] = True
        return proof

    def cleanup_temp(self, now=None):
        now = time.time() if now is None else now
        for path in (self.data / "tmp").glob("noetharaclipz-*"):
            info = path.lstat()
            if (
                path.is_dir()
                and not path.is_symlink()
                and info.st_uid == 62001
                and now - info.st_mtime > 86400
            ):
                if not shutil.rmtree.avoids_symlink_attacks:
                    raise ValueError("Safe temporary-directory cleanup unavailable")
                shutil.rmtree(path)

    def run_generation(self, stop):
        self.fast_stop = False
        self.sampler_stop.clear()
        self.sampling_fault.clear()
        sampler = threading.Thread(target=self.sampling, daemon=True)
        sampler.start()
        verified = None
        last_check = 0
        last_cleanup = 0
        reason = "operator_stop"
        try:
            # Sample a still-running prior generation before stopping it.
            self.stop_owned()
            self.preflight()
            self.protected()
            self.cleanup_temp()
            self.ensure_container()
            docker("start", self.cid)
            while not stop.wait(1):
                if time.time() >= self.m["valid_until"] - 15:
                    reason = "approval_expired"
                    self.fast_stop = True
                    break
                if manifest_hash(load(self.path)[0]) != manifest_hash(self.m):
                    raise ValueError("Active manifest changed")
                if (self.data / "revoked.json").exists():
                    raise ValueError("Local authorization revoked")
                if (
                    service_snapshot(excluded=self.cid) != self.baseline
                    or firewall_fingerprint() != self.fingerprint
                ):
                    raise ValueError("Security or existing-service baseline changed")
                if shutil.disk_usage(self.data).free < 10 * 1024**3:
                    raise ValueError("Runtime disk reserve reached")
                if available_ram() < 4 * 1024**3:
                    raise ValueError(
                        "Shared host RAM reserve reached; stop only this worker"
                    )
                if time.monotonic() - last_check >= 5:
                    self.consent()
                    self.protected()
                    last_check = time.monotonic()
                if time.monotonic() - last_cleanup >= 3600:
                    self.cleanup_temp()
                    last_cleanup = time.monotonic()
                info = inspect(self.cid)
                owned(info, self.m)
                state = container_state_file(info, "continuous-state.json")
                if not info["State"].get("Running"):
                    raise RuntimeError("Worker generation ended unexpectedly")
                nonce = state.get("nonce")
                if state.get("phase") in ("awaiting_grant", "running"):
                    if verified != nonce:
                        self.sample()
                        proof = self.prove()
                        atomic(self.reports / ("network-" + nonce + ".json"), proof)
                        proofs = sorted(
                            self.reports.glob("network-*.json"),
                            key=lambda p: p.stat().st_mtime,
                        )
                        for old in proofs[:-64]:
                            old.unlink()
                        verified = nonce
                    if (
                        self.sampling_fault.is_set()
                        or time.monotonic() - self.last_sample > 6
                    ):
                        raise ValueError(
                            "Resource monitoring unavailable or security check failed"
                        )
                    atomic(
                        self.cfg / "gates/grant.json",
                        {
                            "nonce": nonce,
                            "deployment_id": self.m["deployment_id"],
                            "owner_id": self.m["owner_id"],
                            "consent_id": self.m["consent_id"],
                            "manifest_sha256": manifest_hash(self.m),
                            "security_verified": True,
                            "expires_at": min(
                                time.time() + 20, self.m["valid_until"] - 15
                            ),
                        },
                        mode=0o440,
                        gid=62001,
                    )
                health = container_state_file(info, "health.json")
                self.status(
                    "monitoring",
                    ai_ready=health.get("ai_ready") is True
                    and 0 <= time.time() - health.get("at", 0) < 90,
                    generation=info["State"]["StartedAt"],
                    metrics=self.metrics.summary(),
                )
        except Exception:
            self.fast_stop = True
            raise
        finally:
            try:
                self.stop_owned()
            finally:
                self.sampler_stop.set()
                sampler.join(timeout=5)
        return reason


class Controller:
    """Core ordering/backoff state machine, exercised with inert platform doubles."""

    def __init__(self, platform, clock=time.time):
        self.p, self.clock = platform, clock

    def run(self, stop):
        budget = self.p.data / "restart-budget.json"
        failures = json.loads(budget.read_text())["failures"] if budget.exists() else []
        while not stop.is_set():
            try:
                restart_delay(failures, self.clock())
                reason = self.p.run_generation(stop)
                self.p.status("closed", reason=reason)
                return 0
            except ValueError:
                atomic(
                    self.p.data / "blocked.json", {"blocked": True, "at": self.clock()}
                )
                try:
                    self.p.stop_owned()
                except Exception:
                    log.error(
                        "Stop unavailable; grant remains revoked and container has no automatic restart"
                    )
                self.p.status("blocked_security_or_consent")
                return 0
            except Exception as error:
                failures = [t for t in failures if self.clock() - t < 900]
                delay = restart_delay(failures, self.clock())
                failures.append(self.clock())
                atomic(budget, {"failures": failures})
                try:
                    self.p.stop_owned()
                except Exception:
                    log.error(
                        "Docker unavailable; revoked grant stops model process independently"
                    )
                self.p.status(
                    "backoff", error_type=type(error).__name__, delay_seconds=delay
                )
                if stop.wait(delay):
                    return 0
        return 0


def main():
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        os.environ.pop(name, None)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("install", "isolation", "run", "revoke", "status")
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    require_host()
    if args.action == "install":
        print(json.dumps(install(args.bundle, args.manifest)))
        return
    m, cfg, data = load(args.manifest, active=args.action not in ("status", "revoke"))
    if args.action == "status":
        print(
            (data / "reports/status.json").read_text()
            if (data / "reports/status.json").exists()
            else '{"stage":"installed_not_started"}'
        )
        return
    if args.action == "isolation":
        restore_isolation(m)
        print('{"isolation_verified":true,"worker_started":false}')
        return
    if args.action == "revoke":
        atomic(data / "revoked.json", {"operator_revoked": True, "at": time.time()})
        (cfg / "gates/grant.json").unlink(missing_ok=True)
        print('{"revoked":true,"worker_will_stop_on_revocation":true}')
        return
    # One host-wide pilot controller, even across different deployment IDs.
    with (DATA / "controller.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        platform = Platform(args.manifest)
        handler = RotatingFileHandler(
            data / "reports/controller.log", maxBytes=5 * 1024**2, backupCount=3
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        try:
            raise SystemExit(Controller(platform).run(stop))
        finally:
            platform.stop_owned()


if __name__ == "__main__":
    main()
