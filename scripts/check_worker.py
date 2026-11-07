"""Run from worker/: uv run python ../scripts/check_worker.py. No inference is performed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
from noetharaclipz.config import Settings
from noetharaclipz.backend import Backend
from noetharaclipz.providers import Gemini

settings = Settings()
settings.check_project()
backend = Backend(settings)
backend.rows("projects", select="id", limit=1)
settings.check_ai()
metadata = Gemini(settings).preflight()
print(
    "Supabase worker credential accepted. Gemini model access verified:",
    metadata.get("name"),
)
print(
    "Operator-verified free quotas: RPM",
    settings.rpm,
    "RPD",
    settings.rpd,
    "TPM",
    settings.tpm,
)
print(
    "No generation request made. Paid services and automatic fallbacks remain disabled."
)
