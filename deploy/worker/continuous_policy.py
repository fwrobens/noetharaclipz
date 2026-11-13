"""Pure policy for one explicitly approved continuous pilot; no side effects."""

import hashlib
import json
from uuid import UUID

IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"
MODEL = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
REQUIRED_CODE = {
    "host/continuous_host.py",
    "host/continuous_entry.py",
    "host/continuous_policy.py",
    "host/continuous_metrics.py",
    "host/reliability_platform.py",
    "host/reliability_probe.py",
    "host/reliability_metrics.py",
    "host/check_cgroup_limits.py",
    "host/credential_envelope.py",
    "host/egress_policy.py",
    "worker/noetharaclipz/runner.py",
    "worker/noetharaclipz/backend.py",
    "worker/noetharaclipz/config.py",
    "worker/noetharaclipz/consent.py",
    "runtime/noetharaclipz_deploy/healthcheck.py",
}
ARCHIVED_OWNERS = {
    "c7ade7f9-2003-4a38-ae19-393fffae8452",
    "3e593ddf-c6ce-4895-ae05-0eccb721d674",
    "07ad237e-669b-475d-871d-9bdb6e80f062",
}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def manifest_hash(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def validate_manifest(m, now):
    for key in ("deployment_id", "owner_id", "consent_id"):
        try:
            valid = str(UUID(m[key])) == m[key]
        except (KeyError, ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise ValueError(
                "Explicit canonical deployment/owner/consent identifiers required"
            )
    if (
        m["owner_id"] in ARCHIVED_OWNERS
        or m.get("schema") != 1
        or m.get("image") != IMAGE
        or m.get("model") != MODEL
        or m.get("memory_bytes") != 8 * 1024**3
        or m.get("cpus") != 2
        or m.get("active_jobs") != 1
        or m.get("global_processing") is not False
        or m.get("gemini_enabled") is not False
        or m.get("operator_approved") is not True
        or not m.get("approval_reference")
        or not m["not_before"] <= now < m["valid_until"]
        or not 0 < m["valid_until"] - m["not_before"] <= 7 * 86400
        or not REQUIRED_CODE.issubset(m.get("files", {}))
        or set(m.get("unit_sha256", {}))
        != {"noetharaclipz-isolation.service", "noetharaclipz-continuous.service"}
    ):
        raise ValueError("Missing/expired approval or unsafe continuous scope")
    for name, sha in m["files"].items():
        if (
            not name.endswith(".py")
            or name.startswith("/")
            or ".." in name.split("/")
            or "\\" in name
            or name.split("/")[0] not in ("host", "worker", "runtime")
            or len(sha) != 64
        ):
            raise ValueError("Invalid immutable source manifest")


def grant_valid(g, m, nonce, now):
    return (
        g.get("nonce") == nonce
        and g.get("deployment_id") == m["deployment_id"]
        and g.get("owner_id") == m["owner_id"]
        and g.get("consent_id") == m["consent_id"]
        and g.get("manifest_sha256") == manifest_hash(m)
        and g.get("security_verified") is True
        and now < g.get("expires_at", 0) <= min(now + 25, m["valid_until"])
    )


def restart_delay(failures, now):
    recent = [t for t in failures if 0 <= now - t < 900]
    if len(recent) >= 3:
        raise ValueError("Durable restart budget exhausted; operator review required")
    return (5, 15, 45)[len(recent)]
