"""
backend/voice/tts.py

Azure Cognitive Services text-to-speech.

Why Azure TTS?
  - Free tier: 500,000 characters/month — sufficient for a demo/graduation project
  - Best natural Arabic neural voices available:
      ar-JO-ZariyahNeural  (Jordanian Arabic, female) — default
      ar-JO-HamedNeural    (Jordanian Arabic, male)
  - Jordanian Arabic accent matches DIGIX AI's target audience

Voice names are set in .env (AZURE_VOICE_AR / AZURE_VOICE_EN) and
loaded via config.py. Defaults are ar-JO-ZariyahNeural / en-US-JennyNeural.

Output format: Audio16Khz128KBitRateMonoMp3
  — good quality, reasonable file size, plays natively in all browsers.

Called by:
  backend/api/routes/voice.py → POST /tts

Interface:
  synthesize(text: str, language: str) -> bytes  (mp3 audio)
"""

import azure.cognitiveservices.speech as speechsdk

from backend.utils.config import (
    AZURE_TTS_KEY,
    AZURE_TTS_REGION,
    AZURE_VOICE_AR,
    AZURE_VOICE_EN,
)
from backend.utils.logger import get_logger

logger = get_logger("voice.tts")

# ---------------------------------------------------------------------------
# Voice selection
# ---------------------------------------------------------------------------

def _voice_for(language: str) -> str:
    return AZURE_VOICE_AR if language == "ar" else AZURE_VOICE_EN

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def synthesize(text: str, language: str = "ar") -> bytes:
    """
    Convert text to speech using Azure TTS and return mp3 bytes.

    Parameters
    ----------
    text     : the text to speak (Arabic or English)
    language : "ar" or "en" — selects the appropriate neural voice

    Returns
    -------
    bytes — mp3 audio data, ready to stream directly to the client

    Raises
    ------
    RuntimeError if Azure TTS fails or credentials are invalid
    """
    if not AZURE_TTS_KEY:
        raise RuntimeError(
            "AZURE_TTS_KEY is not set. Add it to .env to enable voice output."
        )

    voice = _voice_for(language)
    logger.info("TTS | lang=%s voice=%s chars=%d", language, voice, len(text))

    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_TTS_KEY,
        region=AZURE_TTS_REGION,
    )
    speech_config.speech_synthesis_voice_name = voice
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
    )

    # audio_config=None → synthesize to memory, not to a speaker or file
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None,
    )

    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        logger.info("TTS success | %d bytes", len(result.audio_data))
        return result.audio_data

    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        raise RuntimeError(
            f"Azure TTS canceled: {details.reason} — {details.error_details}"
        )

    raise RuntimeError(f"Azure TTS failed with reason: {result.reason}")
