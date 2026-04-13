"""
backend/api/routes/voice.py

POST /transcribe — Whisper speech-to-text
POST /tts        — Azure TTS text-to-speech

API contract (from CONTEXT.md):
  POST /transcribe
    Request:  multipart/form-data — audio file (wav/mp3/webm)
    Response: { "text": "ما هي خدماتكم؟", "language": "ar" }

  POST /tts
    Request:  { "text": "مرحباً، كيف يمكنني مساعدتك؟", "language": "ar" }
    Response: audio/mpeg stream

Interfaces expected from voice modules (not yet built):
  backend/voice/stt.py  must export:
      transcribe(audio_bytes: bytes, filename: str) -> dict
          returns {"text": str, "language": str}

  backend/voice/tts.py  must export:
      synthesize(text: str, language: str) -> bytes
          returns raw audio bytes (mp3)
"""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.utils.logger import get_logger

# Voice deps are optional — server starts without them, endpoints return 503
try:
    from backend.voice.stt import transcribe
    _STT_AVAILABLE = True
except ImportError:
    _STT_AVAILABLE = False

try:
    from backend.voice.tts import synthesize
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False

router = APIRouter()
logger = get_logger("api.voice")

# Max audio upload size: 25 MB (Whisper's practical limit for webm/mp3)
MAX_AUDIO_BYTES = 25 * 1024 * 1024

ALLOWED_AUDIO_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/mp3",
    "audio/webm",
    "audio/ogg",
}

# ---------------------------------------------------------------------------
# /transcribe
# ---------------------------------------------------------------------------

@router.post("/transcribe")
async def transcribe_audio(file: UploadFile) -> dict:
    """
    Accept an audio file, run Whisper, return transcribed text and language.
    """
    if file.content_type and file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format.")

    audio_bytes = await file.read()

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB).")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    if not _STT_AVAILABLE:
        raise HTTPException(status_code=503, detail="STT not available — install openai-whisper.")

    logger.info("transcribe | file=%s size=%d", file.filename, len(audio_bytes))

    result = transcribe(audio_bytes, filename=file.filename or "audio")
    return {"text": result["text"], "language": result["language"]}

# ---------------------------------------------------------------------------
# /tts
# ---------------------------------------------------------------------------

class TTSRequest(BaseModel):
    text:     str = Field(..., min_length=1, max_length=3000)
    language: str = Field("ar", pattern="^(ar|en)$")


@router.post("/tts")
async def text_to_speech(req: TTSRequest) -> Response:
    """
    Convert text to speech via Azure TTS and stream back an mp3.
    """
    if not _TTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="TTS not available — install azure-cognitiveservices-speech.")

    logger.info("tts | lang=%s chars=%d", req.language, len(req.text))

    audio_bytes = synthesize(req.text, req.language)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
    )
