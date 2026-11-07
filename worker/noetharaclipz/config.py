import os
from dataclasses import dataclass, field

PROJECT = "zxdnjnsghdnviflahvry"


def quota(name):
    value = os.getenv(name, "0").strip()
    if not value.isdecimal():
        raise ValueError(name + " must be a non-negative integer; inference remains disabled")
    return int(value)


def server_key_headers(key):
    """Modern secret keys are opaque API keys, never bearer JWTs."""
    if key.startswith("sb_secret_") and len(key) > 20 and not any(c.isspace() for c in key):
        return {"apikey": key}
    if key.startswith("eyJ"):
        import base64
        import json

        try:
            payload = key.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (ValueError, IndexError):
            raise ValueError("Malformed Supabase worker JWT") from None
        if not isinstance(claims, dict) or claims.get("role") != "service_role":
            raise ValueError("Supabase worker requires a server secret or service_role credential")
        # Decoding is a format check only. Supabase must verify the signature remotely.
        return {"apikey": key, "Authorization": "Bearer " + key}
    raise ValueError("Supabase worker credential is not a recognized server key")


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(
        default_factory=lambda: os.getenv("SUPABASE_URL", f"https://{PROJECT}.supabase.co").strip()
    )
    service_key: str = field(
        default_factory=lambda: (
            os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        ).strip()
    )
    gemini_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    model: str = "gemini-3.8-flash"
    free_verified: bool = field(
        default_factory=lambda: os.getenv("GEMINI_FREE_TIER_VERIFIED", "false").strip().lower()
        == "true"
    )
    # These must come from the actual AI Studio project, not a published example quota.
    rpm: int = field(default_factory=lambda: quota("GEMINI_VERIFIED_RPM"))
    rpd: int = field(default_factory=lambda: quota("GEMINI_VERIFIED_RPD"))
    tpm: int = field(default_factory=lambda: quota("GEMINI_VERIFIED_TPM"))
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "small"))
    max_input_tokens: int = 50000

    def check_project(self):
        if self.supabase_url.rstrip("/") != f"https://{PROJECT}.supabase.co":
            raise ValueError("Refusing to use an unrelated Supabase project")
        if not self.service_key:
            raise ValueError(
                "Supabase worker credential is not bound to this runtime (SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY)"
            )
        server_key_headers(self.service_key)

    def check_ai(self):
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is missing. No AI request was made.")
        if not self.free_verified or min(self.rpm, self.rpd, self.tpm) < 1:
            raise ValueError(
                "Verify the FREE tier and actual RPM/RPD/TPM in AI Studio first. No request was made."
            )
