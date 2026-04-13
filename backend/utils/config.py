"""
backend/utils/config.py

Loads all environment variables from .env in one place.

Every other module imports what it needs from here — nothing reads
os.environ directly outside this file.  This makes it easy to see
every external dependency the backend has and to validate them at
startup rather than discovering a missing key mid-request.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (two levels above this file)
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]   # required — raises KeyError if missing
OPENAI_MODEL:   str = os.getenv("OPENAI_MODEL", "gpt-4o")

# ---------------------------------------------------------------------------
# Whisper STT (self-hosted)
# ---------------------------------------------------------------------------

# Model size trade-off — "medium" balances Arabic accuracy vs. RAM (≈5 GB).
# Options: tiny | base | small | medium | large
# Change to "large" for best Arabic quality if the server has ≥10 GB RAM.
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "medium")

# ---------------------------------------------------------------------------
# Azure TTS
# ---------------------------------------------------------------------------

AZURE_TTS_KEY:    str = os.getenv("AZURE_TTS_KEY", "")
AZURE_TTS_REGION: str = os.getenv("AZURE_TTS_REGION", "eastus")

# Azure neural voice names — ar-JO-ZariyahNeural is the Jordanian Arabic female voice
AZURE_VOICE_AR: str = os.getenv("AZURE_VOICE_AR", "ar-JO-ZariyahNeural")
AZURE_VOICE_EN: str = os.getenv("AZURE_VOICE_EN", "en-US-JennyNeural")

# ---------------------------------------------------------------------------
# Google Sheets (lead data)
# ---------------------------------------------------------------------------

GOOGLE_SHEET_ID:             str = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# ---------------------------------------------------------------------------
# App / CORS
# ---------------------------------------------------------------------------

BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

_origins_raw: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _origins_raw.split(",")]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_UNANSWERED: bool = os.getenv("LOG_UNANSWERED", "true").lower() == "true"
