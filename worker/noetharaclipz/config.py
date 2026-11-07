import os
from dataclasses import dataclass

PROJECT = "zxdnjnsghdnviflahvry"


@dataclass(frozen=True)
class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", f"https://{PROJECT}.supabase.co")
    service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    gemini_key: str = os.getenv("GEMINI_API_KEY", "")
    model: str = "gemini-3.8-flash"
    free_verified: bool = os.getenv("GEMINI_FREE_TIER_VERIFIED", "false") == "true"
    # These must come from the actual AI Studio project, not a published example quota.
    rpm: int = int(os.getenv("GEMINI_VERIFIED_RPM", "0"))
    rpd: int = int(os.getenv("GEMINI_VERIFIED_RPD", "0"))
    tpm: int = int(os.getenv("GEMINI_VERIFIED_TPM", "0"))
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")
    max_input_tokens: int = 50000

    def check_project(self):
        if self.supabase_url.rstrip("/") != f"https://{PROJECT}.supabase.co":
            raise ValueError("Refusing to use an unrelated Supabase project")
        if not self.service_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is missing; provision it securely")

    def check_ai(self):
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY is missing. No AI request was made.")
        if not self.free_verified or min(self.rpm, self.rpd, self.tpm) < 1:
            raise ValueError(
                "Verify the FREE tier and actual RPM/RPD/TPM in AI Studio first. No request was made."
            )
