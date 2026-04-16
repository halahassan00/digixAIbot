"""
backend/voice/stt.py

Whisper speech-to-text via OpenAI Whisper API.

Called by:
  backend/api/routes/voice.py → POST /transcribe

Interface:
  transcribe(audio_bytes: bytes, filename: str) -> {"text": str, "language": str}
"""

from openai import OpenAI
from backend.utils.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=(filename, audio_bytes),
        response_format="verbose_json",
    )
    language = "ar" if result.language == "ar" else "en"
    return {"text": result.text.strip(), "language": language}
