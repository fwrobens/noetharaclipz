"""Prepare a new immutable trial; launch ONLY with a later approval receipt.

No image build/pull, old-container restart/removal, global claims, schema edits,
firewall writes or host-wide Docker changes. Monitor is a dedicated transient
systemd unit after authorization; preparation never starts a container or unit.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import sys
import threading
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from reliability_metrics import Measurements, append_sample, cgroup_path, read_sample
from reliability_platform import (API, DATA, DOCKER, ETC, IMAGE, INSTANCE, KEY, MODELS, NETWORK, OLD_CID,
    atomic, container_state_file, docker, firewall_fingerprint, inspect, mkdir, reject_counter,
    require_host, run, service_snapshot, verify_network, write_once)
from reliability_policy import PROTECTED_HASH, PROTECTED_JOB, validate_approval, validate_fresh_owner
from reliability_probe import TARGETS

OLD_TRIAL = "9563aeb9-2620-4e05-acf2-1e69ce18b819"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def paths(trial):
    trial = str(UUID(trial))
    if trial == OLD_TRIAL:
        raise ValueError("The expired trial is immutable and cannot be reused")
    return ETC / trial, DATA / trial


def validate_plan(plan):
    paths(plan["trial_id"])
    if (plan.get("instance") != INSTANCE or plan.get("image") != IMAGE
            or plan.get("maximum_seconds") != 1800 or plan.get("memory_bytes") != 8 * 1024**3
            or plan.get("cpus") != 2 or plan.get("active_jobs") != 1
            or plan.get("global_processing") is not False or plan.get("gemini_enabled") is not False
            or plan.get("owner_policy") != "fresh_empty_owner_after_separate_approval"
            or plan.get("requires_future_approval") is not True
            or plan.get("model") != "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
            or plan.get("model_revision") != "7b375e1b73b11138ff12fe22c8f2822d8fe03467"
            or not 120 <= plan["sample"]["duration_seconds"] <= 300
            or plan["sample"]["bytes"] > 45_000_000 or plan["sample"].get("looped_or_concatenated") is not False):
        raise ValueError("Plan violates the approved preparation scope")


def load_trial(trial):
    cfg, data = paths(trial)
    plan_raw = (cfg / "public/plan.json").read_bytes()
    plan = json.loads(plan_raw)
    validate_plan(plan)
    for name, expected in plan["code_sha256"].items():
        path = cfg / "code" / name
        if path.is_symlink() or digest(path.read_bytes()) != expected:
            raise ValueError("Reviewed trial code changed")
    return cfg, data, plan, digest(plan_raw)


def admission():
    old = inspect(OLD_CID)
    if old["State"].get("Running") or old["State"].get("Restarting") or old["State"].get("ExitCode") != 0:
        raise ValueError("Old QA container is not cleanly stopped; never restart or replace it")
    if docker("image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Os}}|{{.Architecture}}|{{.Config.User}}") != IMAGE + "|linux|amd64|62001:62001":
        raise ValueError("Reviewed existing image identity changed")
    expected = {"video_model": "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
        "video_revision": "7b375e1b73b11138ff12fe22c8f2822d8fe03467",
        "whisper_revision": "536b0662742c02347bc0e980a01041f333bce120"}
    if json.loads((MODELS / "manifest.json").read_text()) != expected:
        raise ValueError("Pinned local assets changed; do not download another model")
    key_info = KEY.lstat()
    if KEY.is_symlink() or key_info.st_uid != 0 or key_info.st_gid != 62001 or key_info.st_mode & 0o777 != 0o440:
        raise ValueError("Existing file-secret metadata is not ready; no credential value was read")
    ram = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))) * 1024
    if ram < 10 * 1024**3 or shutil.disk_usage("/var/lib").free < 20 * 1024**3:
        raise ValueError("Insufficient spare host RAM or disk")
    verify_network()
    return {"firewall_fingerprint": firewall_fingerprint(verify=True), "services": service_snapshot(),
            "available_ram_bytes": ram, "free_disk_bytes": shutil.disk_usage("/var/lib").free}


def prepare(bundle_path):
    bundle = json.loads(bundle_path.read_text())
    plan = bundle["plan"]
    validate_plan(plan)
    for name, source in bundle["code"].items():
        if Path(name).name != name or not name.endswith(".py") or digest(source.encode()) != plan["code_sha256"].get(name):
            raise ValueError("Invalid reviewed code manifest")
    if set(bundle["code"]) != set(plan["code_sha256"]):
        raise ValueError("Incomplete code bundle")
    for name, source in bundle["previous_evidence"].items():
        if Path(name).name != name or digest(source.encode()) != plan["previous_evidence_sha256"].get(name):
            raise ValueError("Expired trial evidence changed")
    if set(bundle["previous_evidence"]) != set(plan["previous_evidence_sha256"]):
        raise ValueError("Incomplete expired-trial evidence archive")
    snapshot = admission()  # Read-only; no key, queue, unit or container startup.
    cfg, data = paths(plan["trial_id"])
    mkdir(ETC)
    mkdir(DATA)
    encoded_plan = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    if cfg.exists():
        _, _, old_plan, old_hash = load_trial(plan["trial_id"])
        if old_plan != plan or (cfg / "activation.json").exists():
            raise ValueError("Existing or already activated plan must not be replaced")
        return {"prepared": True, "ready_for_approval": True, "plan_sha256": old_hash,
                "worker_started": False, "reused_identical_preparation": True}
    mkdir(cfg, gid=62001, mode=0o750)
    for name in ("code", "public", "gates"):
        mkdir(cfg / name, gid=62001, mode=0o750)
    mkdir(cfg / "previous-evidence")
    mkdir(data)
    for name in ("cache", "tmp"):
        mkdir(data / name, uid=62001, gid=62001)
    mkdir(data / "reports")
    for name, source in bundle["code"].items():
        write_once(cfg / "code" / name, source, gid=62001, mode=0o440)
    for name, source in bundle["previous_evidence"].items():
        write_once(cfg / "previous-evidence" / name, source, mode=0o440)
    write_once(cfg / "public/plan.json", encoded_plan, gid=62001, mode=0o440)
    write_once(data / "reports/preparation.json", snapshot)
    write_once(data / "reports/status.json", {"stage": "prepared_not_authorized", "worker_started": False})
    return {"prepared": True, "ready_for_approval": True, "trial_id": plan["trial_id"],
            "plan_sha256": digest(encoded_plan.encode()), "worker_started": False,
            "approval_receipt_created": False, "new_qa_account_created": False,
            "old_evidence_preserved": True, "network_rules_changed": False}


def verify_approval_file(path, expected_sha, plan, plan_sha):
    raw = path.read_bytes()
    info = path.lstat()
    if (path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077 or digest(raw) != expected_sha):
        raise ValueError("Approval must be a hash-verified root-private file issued after separate authorization")
    approval = json.loads(raw)
    if approval.get("plan_sha256") != plan_sha:
        raise ValueError("Approval refers to another immutable plan")
    validate_approval(plan, approval, time.time())
    if approval["stop_at_unix"] - time.time() < 600:
        raise ValueError("Too little authorized time remains; never reset the deadline")
    return approval


def protected(api):
    row = api.rows("processing_jobs", id="eq." + PROTECTED_JOB)[0]
    hashes = [digest(json.dumps(row, sort_keys=True, **kw).encode()) for kw in ({}, {"separators": (",", ":")})]
    if PROTECTED_HASH not in hashes or row["status"] != "queued" or row["attempts"] != 0:
        raise ValueError("Protected upload invariant changed; no queue access is allowed")
    project = api.rows("projects", id="eq." + row["project_id"], select="owner_id")[0]
    return project["owner_id"]


def verify_fresh_identity(api, plan, approval):
    protected_owner = protected(api)
    user = api.call("/auth/v1/admin/users/" + approval["owner_id"])
    projects = api.rows("projects", owner_id="eq." + approval["owner_id"], select="id")
    validate_fresh_owner(plan, approval, user, projects, protected_owner)


def launch(trial, approval_path, approval_sha):
    cfg, data, plan, plan_sha = load_trial(trial)
    # Missing approval aborts BEFORE reading a key or any Docker mutation.
    approval = verify_approval_file(approval_path, approval_sha, plan, plan_sha)
    if (cfg / "activation.json").exists():
        raise ValueError("Trial was already activated; preserve its immutable deadline and receipt")
    snapshot = admission()
    api = API()
    verify_fresh_identity(api, plan, approval)
    protocol = api.rpc("worker_protocol")
    if (protocol.get("version") != 1 or not protocol.get("scoped_claim") or not protocol.get("scoped_health")
            or "local-smolvlm2" not in protocol.get("providers", [])):
        raise ValueError("Scoped local-worker protocol unavailable")
    now = datetime.now(timezone.utc).isoformat()
    if api.rows("processing_jobs", select="id", status="not.in.(completed,failed,cancelled)", lease_until="gt." + now):
        raise ValueError("Another job has an active lease; leave it untouched")
    activation = {key: approval[key] for key in ("trial_id", "owner_id", "approved_at_unix", "stop_at_unix", "plan_sha256")}
    write_once(cfg / "activation.json", approval)  # Never overwritten or reopened.
    write_once(cfg / "public/activation.json", activation, gid=62001, mode=0o440)
    write_once(data / "reports/admission.json", snapshot)
    unit = "nccz-reliability-" + UUID(trial).hex[:12]
    # Dedicated transient unit only; no daemon, networking or existing app units.
    run(["systemd-run", "--unit=" + unit, "--property=Type=exec", "--property=Restart=no",
        "--property=RuntimeMaxSec=" + str(max(1, int(approval["stop_at_unix"] - time.time()) + 110)),
        "--property=TimeoutStopSec=100", "--property=KillMode=control-group", "--property=UMask=0077",
        "/usr/bin/python3", str(cfg / "code/reliability_host.py"), "monitor", "--trial-id", trial])
    return {"launch_requested": True, "trial_id": trial, "unit": unit,
            "immutable_stop_at_unix": approval["stop_at_unix"], "global_processing": False}


def create_command(plan, activation, cfg, data):
    project = "nccz-reliability-" + UUID(plan["trial_id"]).hex[:12]
    command = DOCKER + ["create", "--name", project + "-worker", "--pull=never", "--platform=linux/amd64",
        "--network", NETWORK, "--dns", "172.31.0.2", "--user", "62001:62001", "--init", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--memory", "8g", "--memory-swap", "8g",
        "--cpus", "2", "--cpu-shares", "256", "--pids-limit", "256", "--oom-score-adj", "500",
        "--restart", "on-failure:3", "--stop-timeout", "95", "--log-driver", "json-file",
        "--log-opt", "max-size=10m", "--log-opt", "max-file=5", "--log-opt", "compress=true",
        "--sysctl", "net.ipv6.conf.all.disable_ipv6=1", "--sysctl", "net.ipv6.conf.default.disable_ipv6=1",
        "--label", "com.docker.compose.project=" + project,
        "--label", "io.noetharaclipz.trial=" + plan["trial_id"]]
    env = {"NC_DEPLOY_MODE": "qa", "NC_AI_PROVIDER": "local", "GEMINI_FREE_TIER_VERIFIED": "false",
           "NC_GLOBAL_QUEUE_APPROVED": "false", "NC_WORKER_OWNER_ID": activation["owner_id"],
           "NC_QA_STOP_AT": str(activation["stop_at_unix"]), "NC_QA_TRIAL_ID": plan["trial_id"],
           "SUPABASE_URL": "https://zxdnjnsghdnviflahvry.supabase.co", "NC_SUPABASE_KEY_FILE": "/run/secrets/supabase_key"}
    for key, value in env.items():
        command += ["--env", key + "=" + value]
    for source, target, readonly in ((MODELS, "/models", True), (data / "cache", "/data/cache", False),
        (data / "tmp", "/data/tmp", False), (cfg / "code", "/run/trial-code", True),
        (cfg / "public", "/run/trial-config", True), (cfg / "gates", "/run/trial-gate", True),
        (KEY, "/run/secrets/supabase_key", True)):
        command += ["--mount", "type=bind,src=" + str(source) + ",dst=" + target + (",readonly" if readonly else "")]
    for target in ("/tmp", "/run/worker"):
        command += ["--tmpfs", target + ":rw,noexec,nosuid,nodev,size=16m,uid=62001,gid=62001,mode=0700"]
    return command + ["--entrypoint", "python", IMAGE, "/run/trial-code/reliability_entry.py"]


def owned(info, plan):
    labels = info["Config"].get("Labels") or {}
    if info["Id"] == OLD_CID or labels.get("io.noetharaclipz.trial") != plan["trial_id"]:
        raise ValueError("Refusing any action on the expired trial or another application's container")


def validate_created(info, plan, activation):
    owned(info, plan)
    host, config = info["HostConfig"], info["Config"]
    env = dict(item.split("=", 1) for item in config["Env"])
    if (config["Image"] != IMAGE or config["User"] != "62001:62001"
            or config["Entrypoint"] != ["python"] or config["Cmd"] != ["/run/trial-code/reliability_entry.py"]
            or host["Memory"] != 8 * 1024**3 or host["MemorySwap"] != 8 * 1024**3
            or host["NanoCpus"] != 2_000_000_000 or host["PidsLimit"] != 256
            or host["Privileged"] or not host["ReadonlyRootfs"] or host.get("PortBindings")
            or not host["Init"] or "ALL" not in host["CapDrop"]
            or not any(value in host["SecurityOpt"] for value in ("no-new-privileges", "no-new-privileges:true"))
            or host["Dns"] != ["172.31.0.2"]
            or host["Sysctls"].get("net.ipv6.conf.all.disable_ipv6") != "1"
            or host["Sysctls"].get("net.ipv6.conf.default.disable_ipv6") != "1"
            or host["NetworkMode"] != NETWORK or host["RestartPolicy"] != {"Name": "on-failure", "MaximumRetryCount": 3}
            or env.get("NC_GLOBAL_QUEUE_APPROVED") != "false" or env.get("NC_AI_PROVIDER") != "local"
            or env.get("GEMINI_FREE_TIER_VERIFIED") != "false" or env.get("NC_WORKER_OWNER_ID") != activation["owner_id"]
            or env.get("NC_QA_STOP_AT") != str(activation["stop_at_unix"])):
        raise ValueError("Created Docker profile violates immutable trial controls")


def prove_network(cid):
    proof = json.loads(docker("exec", cid, "python", "/run/trial-code/reliability_probe.py", "public", timeout=30))
    checks = []
    for index, target in enumerate(TARGETS):
        before = reject_counter(target[3], target[4])
        result = json.loads(docker("exec", cid, "python", "/run/trial-code/reliability_probe.py", "deny", str(index)))
        delta = reject_counter(target[3], target[4]) - before
        if not result["blocked"] or delta <= 0:
            raise ValueError("Network denial lacks a matching scoped rejection counter")
        checks.append({"target": target[0], "reject_counter_delta": delta})
    return {"public": proof, "denials": checks}


class Sampler:
    def __init__(self, cid, reports, gates):
        self.cid, self.reports, self.gates = cid, reports, gates
        self.metrics, self.lock, self.stop = Measurements(), threading.Lock(), threading.Event()

    def sample(self, final=False):
        with self.lock:
            info = inspect(self.cid)
            if not info["State"].get("Running"):
                return
            generation = str(info["RestartCount"]) + ":" + info["State"]["StartedAt"]
            values = read_sample(cgroup_path(info["State"]["Pid"]))
            row = self.metrics.add(generation, values, time.monotonic(), time.time())
            if final:
                self.metrics.generations[generation]["final_snapshot_captured"] = True
            append_sample(self.reports / "metrics.jsonl", row)
            atomic(self.reports / "metrics-summary.json", self.metrics.summary())

    def loop(self):
        while not self.stop.is_set():
            try:
                info = inspect(self.cid)
                state = container_state_file(info, "trial-state.json")
                final = state.get("phase") == "finalizing"
                self.sample(final=final)
                if final:
                    # Independent of network/API control-loop latency. Ack only
                    # AFTER the final model-workload high-water snapshot is saved.
                    atomic(self.gates / "finalized.json", {"nonce": state["nonce"]}, gid=62001, mode=0o440)
            except (OSError, ValueError, RuntimeError):
                # Generation teardown is a gap, not a fabricated zero reading.
                pass
            self.stop.wait(2)


def qa_job(api, owner):
    projects = api.rows("projects", owner_id="eq." + owner, select="id")
    if not projects:
        return None
    jobs = api.rows("processing_jobs", project_id="in.(" + ",".join(p["id"] for p in projects) + ")",
                   status="not.in.(completed,failed,cancelled)", order="created_at.asc")
    leased = [j for j in jobs if j.get("lease_until") and datetime.fromisoformat(j["lease_until"]) > datetime.now(timezone.utc)]
    if len(leased) > 1:
        raise ValueError("More than one active QA lease")
    return leased[0] if leased else None


def maybe_crash(api, plan, activation, info, state, reports):
    receipt = reports / "crash-private.json"
    if receipt.exists() or activation["stop_at_unix"] - time.time() < 600:
        return
    job = qa_job(api, activation["owner_id"])
    if not job or job["kind"] != "analysis" or job["status"] != "analyzing" or job["progress"] < 50 or job["cancel_requested"]:
        return
    video = api.rows("videos", project_id="eq." + job["project_id"], select="source_hash")[0]
    if video["source_hash"] != plan["sample"]["sha256"] or job["attempts"] != 1:
        return
    if time.time() - datetime.fromisoformat(info["State"]["StartedAt"].replace("Z", "+00:00")).timestamp() < 10:
        return
    health = container_state_file(info, "health.json")
    if not health.get("ai_ready") or health.get("mode") != "qa":
        return
    record = {"job_id": job["id"], "project_id": job["project_id"], "old_token": job["lease_token"],
              "initial_attempts": job["attempts"], "restart_count_before": info["RestartCount"],
              "generation_nonce": state["nonce"], "at_unix": time.time()}
    write_once(receipt, record)  # One injection maximum; uncertainty never retries the signal.
    result = json.loads(docker("exec", info["Id"], "python", "/run/trial-code/reliability_probe.py", "crash-runner", str(health["pid"])))
    atomic(reports / "crash-result.json", {"injected": result["runner_only_sigkill"], "job_id": job["id"],
        "injected_at_unix": record["at_unix"], "old_token_sha256": digest(job["lease_token"].encode()), "recovery_verified": False})


def expected_stale_rejection(error):
    try:
        body = json.load(error)
    except (ValueError, OSError):
        return False
    return error.code == 400 and body.get("code") == "P0001" and body.get("message") in ("Worker lease expired", "Job already finished")


def observe_recovery(api, activation, info, state, reports):
    private = reports / "crash-private.json"
    if not private.exists():
        return
    previous = json.loads(private.read_text())
    job = api.rows("processing_jobs", id="eq." + previous["job_id"])[0]
    if info["RestartCount"] <= previous["restart_count_before"] or state.get("nonce") == previous["generation_nonce"]:
        return
    if job["attempts"] < 2 or job["lease_token"] == previous["old_token"]:
        return
    public_file = reports / "crash-result.json"
    observed = json.loads(public_file.read_text()) if public_file.exists() else {}
    first_observed = observed.get("first_reclaim_observed_at_unix", time.time())
    result = {"injected": True, "job_id": job["id"], "container_restart_count": info["RestartCount"],
              "injected_at_unix": previous["at_unix"], "first_reclaim_observed_at_unix": first_observed,
              "recovery_observed_seconds": first_observed - previous["at_unix"],
              "new_generation_network_granted": state.get("phase") == "running", "attempts": job["attempts"],
              "new_token_sha256": digest(job["lease_token"].encode()), "status": job["status"], "recovery_verified": False}
    try:
        api.rpc("worker_tick", jid=job["id"], token=previous["old_token"], state="analyzing", pct=1, detail="Stale QA token must fail")
    except urllib.error.HTTPError as error:
        if not expected_stale_rejection(error):
            raise ValueError("Stale-token verification received an unrelated remote error") from None
        result["stale_token_rejected"] = True
    else:
        raise ValueError("Stale token unexpectedly updated the QA job")
    if job["status"] == "completed":
        usage = api.rows("provider_usage", project_id="eq." + job["project_id"])
        highlights = api.rows("highlights", project_id="eq." + job["project_id"])
        result["recovery_verified"] = (job["attempts"] == previous["initial_attempts"] + 1 and len(usage) == 1
            and info["RestartCount"] == previous["restart_count_before"] + 1
            and result["new_generation_network_granted"] and usage[0]["provider"] == "local-smolvlm2"
            and usage[0]["status"] == "completed" and usage[0]["estimated_cost"] == 0
            and bool(highlights) and result["stale_token_rejected"])
    atomic(reports / "crash-result.json", result)


def monitor(trial):
    cfg, data, plan, plan_sha = load_trial(trial)
    approval = json.loads((cfg / "activation.json").read_text())
    validate_approval(plan, approval, time.time())
    snapshot = admission()
    reports = data / "reports"
    api = API()
    verify_fresh_identity(api, plan, approval)
    baseline = snapshot["services"]
    cid = run(create_command(plan, approval, cfg, data))
    info = inspect(cid)
    validate_created(info, plan, approval)
    write_once(reports / "container.json", {"id": cid, "trial_id": trial, "plan_sha256": plan_sha})
    sampler = Sampler(cid, reports, cfg / "gates")
    thread = threading.Thread(target=sampler.loop, daemon=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    thread.start()  # Persistent host sampler exists before Docker starts.
    granted = set()
    last_api = 0
    error_type = None
    try:
        docker("start", cid)
        while time.time() < approval["stop_at_unix"] + 5:
            info = inspect(cid)
            owned(info, plan)
            state = container_state_file(info, "trial-state.json")
            if stop.is_set() or (reports / "stop-request.json").exists():
                break
            if service_snapshot(excluded=cid) != baseline:
                raise ValueError("Existing application state changed; stop only this new worker")
            if firewall_fingerprint() != snapshot["firewall_fingerprint"]:
                raise ValueError("Isolation changed; revoke startup/processing grant")
            if state.get("phase") == "finalizing":
                pass  # Independent sampler performs the final snapshot/ack.
            elif state.get("phase") in ("awaiting_network_grant", "running"):
                nonce = state["nonce"]
                if nonce not in granted:
                    verify_network()
                    proof = prove_network(cid)
                    write_once(reports / ("network-" + nonce + ".json"), proof)
                    granted.add(nonce)
                atomic(cfg / "gates/grant.json", {"trial_id": trial, "owner_id": approval["owner_id"], "nonce": nonce,
                    "stop_at_unix": approval["stop_at_unix"], "expires_at_unix": time.time() + 25,
                    "network_verified": True}, gid=62001, mode=0o440)
                if time.monotonic() - last_api > 5:
                    protected(api)
                    observe_recovery(api, approval, info, state, reports)
                    maybe_crash(api, plan, approval, info, state, reports)
                    last_api = time.monotonic()
            health = container_state_file(info, "health.json")
            current = {"stage": "monitoring", "container_id": cid, "running": info["State"].get("Running"),
                       "ai_ready": health.get("ai_ready") is True and 0 <= time.time() - health.get("at", 0) < 90,
                       "restart_count": info["RestartCount"], "phase": state.get("phase"), "at_unix": time.time(),
                       "fixed_stop_at_unix": approval["stop_at_unix"], "global_processing": False}
            atomic(reports / "status.json", current)
            if not info["State"].get("Running") and not info["State"].get("Restarting"):
                if info["State"].get("ExitCode") == 0 or info["RestartCount"] >= 3:
                    break
            stop.wait(1)
    except Exception as error:
        error_type = type(error).__name__
        raise
    finally:
        # Only this new trial's container. Preserve it and every evidence file.
        (cfg / "gates/grant.json").unlink(missing_ok=True)
        cleanup_error = None
        try:
            info = inspect(cid)
            owned(info, plan)
            if info["State"].get("Running") or info["State"].get("Restarting"):
                try:
                    sampler.sample()
                except (OSError, ValueError, RuntimeError):
                    pass
                docker("stop", "--time", "95", cid, timeout=105)
        except Exception as error:
            cleanup_error = type(error).__name__
        sampler.stop.set()
        thread.join(timeout=5)
        metrics = sampler.metrics.summary()
        atomic(reports / "metrics-summary.json", metrics)
        result = {"stage": "closed", "container_id": cid, "trial_id": trial,
                  "error_type": error_type, "cleanup_error_type": cleanup_error, "metrics": metrics,
                  "global_processing": False, "network_generations_verified": len(granted)}
        try:
            final = inspect(cid)
            result.update(state={k: final["State"].get(k) for k in
                ("Status", "Running", "ExitCode", "OOMKilled", "StartedAt", "FinishedAt")}, restart_count=final["RestartCount"])
            result["resource_coverage_complete"] = (len(metrics["generations"]) == final["RestartCount"] + 1
                                                    and metrics["final_snapshots_complete"])
            result["existing_services_unchanged"] = service_snapshot() == baseline
            result["old_container_untouched"] = inspect(OLD_CID)["State"]["ExitCode"] == 0
            protected(api)
            result["protected_upload_unchanged"] = True
        except Exception as error:
            result["final_verification_error_type"] = type(error).__name__
        crash = reports / "crash-result.json"
        result["crash_verification"] = json.loads(crash.read_text()) if crash.exists() else {"injected": False}
        atomic(reports / "final.json", result)


def request_stop(cfg, data, plan):
    reports = data / "reports"
    record = reports / "container.json"
    if not record.exists():
        return {"stopped": False, "reason": "No new trial worker was started"}
    atomic(reports / "stop-request.json", {"operator_requested_stop": True, "at_unix": time.time()})
    status = json.loads((reports / "status.json").read_text())
    if time.time() - status.get("at_unix", 0) > 15:
        # If the monitor has died, revoke its grant and explicitly stop ONLY the
        # labeled new container. Preserve an independent last resource snapshot.
        (cfg / "gates/grant.json").unlink(missing_ok=True)
        cid = json.loads(record.read_text())["id"]
        info = inspect(cid)
        owned(info, plan)
        if info["State"].get("Running") or info["State"].get("Restarting"):
            try:
                snapshot = read_sample(cgroup_path(info["State"]["Pid"]))
                atomic(reports / "rollback-last-counters.json", snapshot)
            except (OSError, ValueError):
                pass
            docker("stop", "--time", "95", cid, timeout=105)
            return {"new_container_stopped": True, "monitor_was_stale": True, "expired_trial_changed": False}
    return {"graceful_stop_requested": True, "expired_trial_changed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "launch", "monitor", "status", "stop"))
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--trial-id")
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--approval-sha256")
    args = parser.parse_args()
    os.umask(0o077)
    require_host()
    if args.action == "prepare":
        result = prepare(args.bundle)
    else:
        cfg, data, plan, _ = load_trial(args.trial_id)
        if args.action == "launch":
            if args.approval_file is None or args.approval_sha256 is None:
                raise ValueError("No launch without a separately issued approval file and hash")
            result = launch(args.trial_id, args.approval_file, args.approval_sha256)
        elif args.action == "monitor":
            monitor(args.trial_id)
            return
        elif args.action == "stop":
            result = request_stop(cfg, data, plan)
        else:
            target = data / "reports/final.json"
            result = json.loads((target if target.exists() else data / "reports/status.json").read_text())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"failed": True, "error_type": type(error).__name__, "details": str(error)[:200]}), file=sys.stderr)
        raise SystemExit(1) from None
