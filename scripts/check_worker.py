"""Safe, independent readiness checks. Never runs inference or reveals key values."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from noetharaclipz.config import Settings
from noetharaclipz.backend import Backend
from noetharaclipz.providers import Gemini

NAMES = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SECRET_KEY",
    "GEMINI_API_KEY",
    "GEMINI_FREE_TIER_VERIFIED",
    "GEMINI_VERIFIED_RPM",
    "GEMINI_VERIFIED_RPD",
    "GEMINI_VERIFIED_TPM",
    "NVIDIA_API_KEY",
    "ANYMODEL_API_KEY",
)


def main():
    report = {
        "variables": {
            name: "bound" if os.getenv(name, "").strip() else "not_bound"
            for name in NAMES
        },
        "generation_requested": False,
    }
    try:
        settings = Settings()
    except ValueError as e:
        report["configuration"] = str(e)
        print(json.dumps(report, indent=2))
        return 1
    try:
        backend = Backend(settings)
        backend.rows("projects", select="id", limit=1)
        report["supabase"] = (
            "server credential accepted for intended project; queue consumption not attempted"
        )
    except Exception:
        report["supabase"] = (
            "not validated; check runtime bindings and server-key format/permissions"
        )
    if settings.gemini_key:
        try:
            metadata = Gemini(settings).inspect_access()
            report["gemini_model_access"] = {
                "name": metadata.get("name"),
                "generation_method_supported": True,
            }
        except Exception:
            report["gemini_model_access"] = (
                "not validated; model/key metadata lookup failed"
            )
    else:
        report["gemini_model_access"] = "key not bound to current runtime"
    try:
        settings.check_ai()
        report["gemini_inference"] = (
            "configuration permits inference ONLY if actual account eligibility and quotas have been independently confirmed"
        )
    except ValueError:
        report["gemini_inference"] = (
            "disabled; false/unconfirmed free-tier flag is intentional and is not evidence of an invalid key"
        )
    report["eligibility"] = (
        "API model metadata and environment flags do not confirm billing tier, remaining quota, age, region, or API-client eligibility. Verify in the provider account."
    )
    print(json.dumps(report, indent=2))
    return (
        0 if report.get("supabase", "").startswith("server credential accepted") else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
