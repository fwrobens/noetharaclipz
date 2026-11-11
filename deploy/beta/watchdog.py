"""Independent, bounded beta alerts. No queue API or worker/service mutations.

Install/start only under a separately approved beta manifest. Root/Docker access
does not make this script a sandbox: the reviewed code deliberately exposes only
two fixed read-only commands. External delivery defaults off and requires an
existing, approved private HTTPS webhook file. No cloud resource is provisioned.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import socket
import ssl
import stat
import subprocess
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID

ETC = Path("/etc/noetharaclipz-isolated/continuous")
DATA = Path("/var/lib/noetharaclipz-isolated/continuous")
ALERTS = Path("/var/lib/noetharaclipz-isolated/beta-alerts")
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]
UNIT = "noetharaclipz-continuous.service"
EXPIRED = {
    "11865b83-9836-4ff3-a99e-dfac4df71f34",
    "c25d8492-56fb-4c56-a519-e9a9e4246525",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def secure_read(path, limit=262144, private=False):
    # O_NOFOLLOW protects the final component; installation must also verify
    # every parent is root-owned, non-writable and not a symlink.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & (0o077 if private else 0o022)
        ):
            raise ValueError("Untrusted beta file permissions")
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Beta file exceeds read limit")
        return raw


def validate(config, manifest, now):
    deployment = config["deployment_id"]
    if str(UUID(deployment)) != deployment or deployment in EXPIRED:
        raise ValueError("New canonical beta deployment required")
    if (
        config.get("schema") != 1
        or config.get("operator_approved") is not True
        or config.get("manifest_sha256") != sha(canonical(manifest))
        or manifest.get("deployment_id") != deployment
        or manifest.get("operator_approved") is not True
        or manifest.get("global_processing") is not False
        or manifest.get("gemini_enabled") is not False
        or manifest.get("memory_bytes") != 8 * 1024**3
        or manifest.get("cpus") != 2
        or manifest.get("active_jobs") != 1
        or manifest.get("model") != "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
        or not 0 < manifest["valid_until"] - manifest["not_before"] <= 7200
        or not manifest["not_before"] - 120 <= now < manifest["valid_until"]
        or not isinstance(config.get("delivery_enabled"), bool)
    ):
        raise ValueError("Missing beta approval or unsafe scope")
    if config["delivery_enabled"] and (
        config.get("destination_file") != "/etc/noetharaclipz-isolated/beta-webhook"
        or len(config.get("destination_sha256", "")) != 64
        or not config.get("destination_host")
        or config.get("payload_format") not in ("generic", "slack", "discord")
    ):
        raise ValueError("Approved existing notification destination required")


def allowed_read(command):
    inspect_prefix = DOCKER + [
        "inspect",
        "--format",
        '{"state":{{json .State}},"labels":{{json .Config.Labels}}}',
    ]
    return command == ["systemctl", "is-active", UNIT] or (
        command[:-1] == inspect_prefix
        and len(command[-1]) == 64
        and all(c in "0123456789abcdef" for c in command[-1])
    )


def command_read(command):
    if not allowed_read(command):
        raise ValueError("Watchdog permits only fixed scoped read operations")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
    )
    if result.returncode and command[0] != "systemctl":
        raise RuntimeError("Read-only Docker observation failed")
    return result.stdout.strip()


def observe(deployment):
    reports = DATA / deployment / "reports"
    status = json.loads(secure_read(reports / "status.json"))
    record = json.loads(secure_read(reports / "container.json"))
    if record.get("deployment_id") != deployment:
        raise ValueError("Container record belongs to another deployment")
    info = json.loads(
        command_read(
            DOCKER
            + [
                "inspect",
                "--format",
                '{"state":{{json .State}},"labels":{{json .Config.Labels}}}',
                record["id"],
            ]
        )
    )
    if info["labels"].get("io.noetharaclipz.continuous") != deployment:
        raise ValueError("Cannot observe another application's container")
    return {
        "status": status,
        "state": info["state"],
        "unit": command_read(["systemctl", "is-active", UNIT]),
    }


def faults(snapshot, manifest, now):
    """Pure assessment. A safe security halt can be exit zero and still alert."""
    if snapshot is None:
        return (
            {"observer_unavailable": "critical"}
            if now > manifest["not_before"] + 180
            else {}
        )
    status, state = snapshot["status"], snapshot["state"]
    running = state.get("Running") is True
    if now >= manifest["valid_until"]:
        return (
            {"deadline_overrun": "critical"}
            if running and now > manifest["valid_until"] + 30
            else {}
        )
    result = {}
    if status.get("stage") == "blocked_security_or_consent":
        result["security_or_consent_halt"] = "critical"
    elif status.get("stage") == "backoff":
        result["worker_recovery"] = "warning"
    elif status.get("stage") == "closed" and now < manifest["valid_until"] - 90:
        result["unexpected_shutdown"] = "critical"
    if now > manifest["not_before"] + 180 and now < manifest["valid_until"] - 90:
        age = now - status.get("at", 0)
        if age < -5 or age > 45:
            result["controller_status_stale"] = "critical"
        if snapshot["unit"] != "active":
            result["controller_inactive"] = "critical"
        if not running and status.get("stage") != "backoff":
            result["worker_not_running"] = "critical"
        if (
            running
            and status.get("ai_ready") is not True
            and status.get("stage") != "backoff"
        ):
            result["worker_not_ready"] = "warning"
    peak = status.get("metrics", {}).get("peak_memory_bytes", 0)
    if peak > 0.9 * manifest["memory_bytes"]:
        result["memory_headroom_low"] = "warning"
    return result


def send_webhook(config, event):
    """No redirects/proxies/private IPs; pin resolved IP with TLS host verification."""
    raw = secure_read(Path(config["destination_file"]), limit=4096, private=True)
    if sha(raw) != config["destination_sha256"]:
        raise ValueError("Notification destination changed")
    endpoint = urlsplit(raw.decode().strip())
    if (
        endpoint.scheme != "https"
        or endpoint.username
        or endpoint.password
        or endpoint.fragment
        or endpoint.port not in (None, 443)
        or endpoint.hostname != config["destination_host"]
    ):
        raise ValueError("Unapproved notification endpoint")
    addresses = {
        item[4][0]
        for item in socket.getaddrinfo(endpoint.hostname, 443, type=socket.SOCK_STREAM)
    }
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Notification endpoint is not public HTTPS")
    payload = event
    text = f"NoetharaClipz beta {event['event']}: {event['code']} ({event['severity']}); deployment {event['deployment_id']} at {event['utc']}"
    if config["payload_format"] == "slack":
        payload = {"text": text}
    elif config["payload_format"] == "discord":
        payload = {"content": text, "allowed_mentions": {"parse": []}}
    conn = http.client.HTTPSConnection(
        endpoint.hostname, 443, timeout=5, context=ssl.create_default_context()
    )
    address = sorted(addresses, key=lambda ip: (ipaddress.ip_address(ip).version, ip))[
        0
    ]
    conn._create_connection = lambda *a, **k: socket.create_connection(
        (address, 443), timeout=5
    )
    try:
        conn.request(
            "POST",
            endpoint.path + ("?" + endpoint.query if endpoint.query else ""),
            body=canonical(payload),
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        if not 200 <= response.status < 300:
            raise RuntimeError("Notification delivery rejected")
        response.read(4096)
    finally:
        conn.close()


def atomic(path, value):
    temporary = path.with_suffix(".new")
    with os.fdopen(
        os.open(
            temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        ),
        "wb",
    ) as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def reconcile(state, current, deployment, now):
    """Stable deduplication/recovery outbox persists through watchdog restarts."""
    previous = state.get("active", {})
    events = []
    for code in sorted(set(previous) | set(current)):
        if previous.get(code) == current.get(code):
            continue
        event = {
            "deployment_id": deployment,
            "code": code,
            "event": "fault" if code in current else "recovered",
            "severity": current.get(code, "info"),
            "utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        }
        event["id"] = sha(canonical(event))
        events.append({"event": event, "attempts": 0, "last_try": 0})
    state["active"] = current
    state["outbox"] = (state.get("outbox", []) + events)[-32:]
    return events


def deliver(state, config, now, sender=send_webhook):
    if not config["delivery_enabled"]:
        state["outbox"] = []
        return
    for item in state.get("outbox", []):
        if item["attempts"] >= 3 or now - item["last_try"] < 60:
            continue
        item["attempts"] += 1
        item["last_try"] = now
        try:
            sender(config, item["event"])
            item["delivered"] = True
        except Exception:
            # The exception may include a private URL. Retain only the outcome.
            logging.error(
                "beta_alert_delivery_failed event=%s attempt=%s",
                item["event"]["id"],
                item["attempts"],
            )
    state["outbox"] = [
        item for item in state.get("outbox", []) if not item.get("delivered")
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--approved-config-sha256", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("Root-managed installation required")
    os.umask(0o077)
    raw = secure_read(args.config)
    if sha(raw) != args.approved_config_sha256:
        raise ValueError("Watchdog configuration differs from separate approval")
    config = json.loads(raw)
    deployment = config["deployment_id"]
    if str(UUID(deployment)) != deployment:
        raise ValueError("Canonical deployment ID required")
    manifest_path = ETC / deployment / "public/manifest.json"
    manifest = json.loads(secure_read(manifest_path))
    validate(config, manifest, time.time())
    directory = ALERTS / deployment
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (
        directory.is_symlink()
        or directory.stat().st_uid != 0
        or directory.stat().st_mode & 0o077
    ):
        raise ValueError("Private watchdog state directory required")
    logger = logging.getLogger("nccz.beta.alerts")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        directory / "alerts.jsonl", maxBytes=1024**2, backupCount=3
    )
    logger.addHandler(handler)
    state_path = directory / "state.json"
    state = (
        json.loads(secure_read(state_path, private=True)) if state_path.exists() else {}
    )
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set() and time.time() < manifest["valid_until"] + 120:
        try:
            if (
                sha(secure_read(args.config)) != args.approved_config_sha256
                or sha(canonical(json.loads(secure_read(manifest_path))))
                != config["manifest_sha256"]
            ):
                raise ValueError("Pinned beta configuration changed")
        except Exception:
            current = {"configuration_changed": "critical"}
        else:
            try:
                current = faults(observe(deployment), manifest, time.time())
            except Exception:
                current = faults(None, manifest, time.time())
        now = time.time()
        for item in reconcile(state, current, deployment, now):
            logger.info(canonical(item["event"]).decode())
            logging.warning(
                "beta_alert event=%s code=%s severity=%s",
                item["event"]["event"],
                item["event"]["code"],
                item["event"]["severity"],
            )
        # At-least-once outbox: preserve before sending. A crash after delivery
        # can repeat the same event ID; receivers may deduplicate that ID.
        atomic(state_path, state)
        deliver(state, config, now)
        state["last_checked_unix"] = now
        atomic(state_path, state)
        stop.wait(15)
    print(
        json.dumps(
            {
                "watchdog_closed": True,
                "worker_action_taken": False,
                "delivery_enabled": config["delivery_enabled"],
            }
        )
    )


if __name__ == "__main__":
    main()
