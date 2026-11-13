"""Gated wrapper for the existing genuine UI acceptance, not a scheduler/worker.

Requires a separately issued hash-bound approval, the reviewed HTTPS release,
the authenticated consenting owner and known licensed footage. This preparation
does not issue that approval. No fallback to localhost, Gemini or another owner.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"
PROJECT = "https://zxdnjnsghdnviflahvry.supabase.co"
EXPIRED = {
    "c25d8492-56fb-4c56-a519-e9a9e4246525",
    "11865b83-9836-4ff3-a99e-dfac4df71f34",
}


def validate_approval(a, sample_id, now):
    for key in ("deployment_id", "owner_id", "consent_id"):
        if str(UUID(a[key])) != a[key]:
            raise ValueError("Canonical approved identifiers required")
    origin = urlsplit(a["frontend_origin"])
    if (
        a["deployment_id"] in EXPIRED
        or a.get("operator_approved") is not True
        or a.get("workload_trial_authorized") is not True
        or a.get("global_processing") is not False
        or a.get("gemini_enabled") is not False
        or a.get("boot_start") is not False
        or a.get("provider") != "local-smolvlm2"
        or a.get("memory_bytes") != 8 * 1024**3
        or a.get("cpus") != 2
        or a.get("active_jobs") != 1
        or a["valid_until"] - a["not_before"] != 7200
        or not a["not_before"] <= now < a["valid_until"] - 900
        or origin.scheme != "https"
        or origin.netloc != "noetharaclipz.lovable.app"
        or origin.username
        or origin.password
        or origin.path not in ("", "/")
        or origin.query
        or origin.fragment
        or len(a.get("frontend_build", "")) != 40
        or any(c not in "0123456789abcdef" for c in a["frontend_build"])
        or sample_id not in "ABCDEF"
        or len(sample_id) != 1
        or (sample_id == "D" and a.get("cancellation_authorized") is not True)
    ):
        raise ValueError("Missing workload authorization or unsafe beta scope")
    schedule = {"A": 0, "B": 20, "C": 20, "D": 50, "E": 75, "F": 100}
    if now < a["not_before"] + schedule[sample_id] * 60:
        raise ValueError("Scheduled interval has not arrived; no foreground waiting")


def verify_owner(approval, login, consent, health):
    if (
        login.get("user", {}).get("id") != approval["owner_id"]
        or not isinstance(consent, dict)
        or consent.get("owner_id") != approval["owner_id"]
        or consent.get("consent_id") != approval["consent_id"]
        or not consent.get("approved_at")
        or consent.get("revoked_at")
        or not isinstance(health, dict)
        or health.get("online") is not True
        or health.get("ai_ready") is not True
    ):
        raise ValueError("Approved authenticated owner/consent/readiness required")
    from datetime import datetime

    if (
        datetime.fromisoformat(consent["expires_at"].replace("Z", "+00:00")).timestamp()
        != approval["valid_until"]
    ):
        raise ValueError("Server consent window differs from reviewed beta")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-file", type=Path, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--sample-id", choices=list("ABCDEF"), required=True)
    parser.add_argument("--media-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    info = args.approval_file.lstat()
    if (
        args.approval_file.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_mode & 0o077
    ):
        raise ValueError("Private reviewed approval file required")
    raw = args.approval_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.approval_sha256:
        raise ValueError("Approval hash mismatch")
    approval = json.loads(raw)
    validate_approval(approval, args.sample_id, time.time())
    corpus_raw = (ROOT / "docs/evidence/beta-corpus-preparation.json").read_bytes()
    if hashlib.sha256(corpus_raw).hexdigest() != approval.get("corpus_receipt_sha256"):
        raise ValueError("Licensed media receipt differs from approval")
    corpus = json.loads(corpus_raw)
    sample = next(s for s in corpus["samples"] if s["id"] == args.sample_id)
    path = (args.media_directory / sample["file"]).resolve(strict=True)
    if (
        path.stat().st_size != sample["bytes"]
        or path.stat().st_size > 15_000_000
        or hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]
    ):
        raise ValueError("Approved sample bytes changed")
    # Gate the public candidate before using any owner credentials or uploading.
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        release = client.get(approval["frontend_origin"].rstrip("/") + "/api/release")
        release.raise_for_status()
        identity = release.json()
        if {k: identity.get(k) for k in ("app", "mode", "build")} != {
            "app": "NoetharaClipz",
            "build": approval["frontend_build"],
            "mode": "owner-scoped-beta",
        }:
            raise ValueError("Published frontend is not the reviewed beta")
        if identity.get("access", {}).get("sha256") != approval.get(
            "frontend_access_sha256"
        ) or not approval.get("frontend_access_sha256"):
            raise ValueError("Published server access policy differs from approval")
    with httpx.Client(timeout=30, headers={"apikey": PUBLIC_KEY}) as api:
        response = api.post(
            PROJECT + "/auth/v1/token?grant_type=password",
            json={
                "email": os.environ["NC_TEST_EMAIL"],
                "password": os.environ["NC_TEST_PASSWORD"],
            },
        )
        response.raise_for_status()
        login = response.json()
        api.headers["Authorization"] = "Bearer " + login["access_token"]
        try:
            consent = api.post(PROJECT + "/rest/v1/rpc/processing_consent", json={})
            health = api.post(PROJECT + "/rest/v1/rpc/pipeline_health", json={})
            consent.raise_for_status()
            health.raise_for_status()
            verify_owner(approval, login, consent.json(), health.json())
        finally:
            api.post(PROJECT + "/auth/v1/logout?scope=local")
    # Local attempt latch shared by runs using this approval directory, including
    # crashes. Server consent/RLS remain the security boundary. Preserve failed
    # attempts for review; do not move the approval to bypass this latch.
    attempt = (
        args.approval_file.parent
        / "beta-attempts"
        / approval["deployment_id"]
        / args.sample_id
    )
    attempt.mkdir(mode=0o700, parents=True, exist_ok=False)
    (attempt / "attempt.json").write_text(
        json.dumps({"at": time.time(), "sample": args.sample_id})
    )
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (args.output / "attempt.json").write_text(
        json.dumps(
            {
                "sample": args.sample_id,
                "deployment_id": approval["deployment_id"],
                "at": time.time(),
            }
        )
    )
    validate_approval(approval, args.sample_id, time.time())
    permitted = {
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "LANG",
        "CI",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
        "CHROMIUM_PATH",
        "PLAYWRIGHT_BROWSERS_PATH",
        "NC_TEST_EMAIL",
        "NC_TEST_PASSWORD",
    }
    env = {k: v for k, v in os.environ.items() if k in permitted}
    env.update(
        NC_AI_PROVIDER="local",
        GEMINI_FREE_TIER_VERIFIED="false",
        NC_BASE_URL=approval["frontend_origin"].rstrip("/"),
        NC_SAMPLE_VIDEO=str(path),
        NC_WAIT_SECONDS="720",
        NC_ACCEPTANCE_OUTPUT_DIR=str(args.output.resolve()),
        NC_TEST_CANCEL_RETRY="1" if args.sample_id == "D" else "0",
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/acceptance.py")],
        env=env,
        check=True,
        timeout=max(1, approval["valid_until"] - time.time() - 90),
    )


if __name__ == "__main__":
    main()
