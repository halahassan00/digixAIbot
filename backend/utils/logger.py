"""
backend/utils/logger.py

Centralised logging for the DIGIX AI chatbot backend.

Two concerns are tracked:
  - Unanswered queries — questions the bot couldn't ground in the knowledge
    base (useful for identifying knowledge gaps to fix)
  - General errors    — exceptions from any layer, with enough context to
    reproduce them

Logs go to stdout (visible in Railway/Render/Docker) and to a rotating
file under backend/logs/ so they survive container restarts during dev.

Usage
-----
from backend.utils.logger import log_unanswered, log_error, get_logger

log_unanswered("كيف أحصل على شهادة ISO؟", session_id="abc123")
log_error("Whisper timeout", context={"session_id": "abc123", "file_size": 2048})

app_logger = get_logger("api.chat")   # module-level structured logger
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.utils.config import LOG_UNANSWERED

# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Root backend logger
# ---------------------------------------------------------------------------

def _build_logger(name: str, log_file: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger   # already configured — avoid duplicate handlers

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # stdout handler
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    stream.setLevel(logging.INFO)

    # rotating file handler (5 MB × 3 backups)
    file_handler = RotatingFileHandler(
        _LOG_DIR / log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger


_main_logger      = _build_logger("digix", "app.log")
_unanswered_logger = _build_logger("digix.unanswered", "unanswered.log")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'digix' namespace."""
    return logging.getLogger(f"digix.{name}")


def log_unanswered(query: str, session_id: str = "") -> None:
    """
    Log a query the bot could not answer from the knowledge base.

    Only logs if LOG_UNANSWERED=true in .env (default: true).
    These entries are reviewed periodically to identify knowledge gaps.
    """
    if not LOG_UNANSWERED:
        return
    _unanswered_logger.warning(
        "UNANSWERED | session=%s | query=%r", session_id, query
    )


def log_error(message: str, context: dict | None = None) -> None:
    """Log an application error with optional context dict."""
    ctx = " | ".join(f"{k}={v}" for k, v in (context or {}).items())
    _main_logger.error("ERROR | %s | %s", message, ctx)
