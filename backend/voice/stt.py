"""
backend/voice/stt.py

Whisper speech-to-text (self-hosted, runs on the backend server).

Why self-hosted Whisper and not the OpenAI Whisper API?
  - Free — no per-minute cost, runs entirely on the backend server
  - Best Arabic ASR available (Whisper large/medium trained on Arabic)
  - No audio data leaves the server — privacy for user voice input

Model is loaded once at first call and cached for the process lifetime.
Loading takes ~10 s and uses ~5 GB RAM for "medium" — acceptable for a
server, unacceptable to do on every request.

Called by:
  backend/api/routes/voice.py → POST /transcribe

Interface:
  transcribe(audio_bytes: bytes, filename: str) -> {"text": str, "language": str}
"""

import tempfile
from pathlib import Path

import whisper

from backend.utils.config import WHISPER_MODEL
from backend.utils.logger import get_logger

logger = get_logger("voice.stt")

# ---------------------------------------------------------------------------
# Singleton model
# ---------------------------------------------------------------------------

_model: whisper.Whisper | None = None


def _get_model() -> whisper.Whisper:
    global _model
    if _model is None:
        logger.info("Loading Whisper model: %s", WHISPER_MODEL)
        _model = whisper.load_model(WHISPER_MODEL)
        logger.info("Whisper model loaded.")
    return _model

# ---------------------------------------------------------------------------
# Language mapping
# ---------------------------------------------------------------------------

# Whisper returns ISO 639-1 codes; map to the two values the rest of
# the backend understands. Any non-Arabic language is treated as English.
def _map_language(whisper_lang: str | None) -> str:
    return "ar" if whisper_lang == "ar" else "en"

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def transcribe(audio_bytes: bytes, filename: str = "audio") -> dict:
    """
    Transcribe audio bytes to text using self-hosted Whisper.

    Whisper requires a file path, not a byte stream, so we write to a
    temporary file and clean it up immediately after transcription.

    Parameters
    ----------
    audio_bytes : raw audio file content (wav, mp3, webm, ogg)
    filename    : original filename — used only to preserve the extension
                  so Whisper's format detection works correctly

    Returns
    -------
    {"text": str, "language": str}  — language is "ar" or "en"
    """
    model = _get_model()

    # Preserve the file extension so Whisper detects the format correctly
    suffix = Path(filename).suffix or ".webm"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        logger.info("Transcribing %s (%d bytes)", filename, len(audio_bytes))

        # fp16=False: CPU-safe. On a GPU server, remove this flag for speed.
        result = model.transcribe(tmp_path, fp16=False)

        text     = result.get("text", "").strip()
        language = _map_language(result.get("language"))

        logger.info("Transcription done | lang=%s | text=%r", language, text[:80])
        return {"text": text, "language": language}

    finally:
        # Always clean up the temp file, even if transcription raises
        Path(tmp_path).unlink(missing_ok=True)
