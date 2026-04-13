"""
backend/language/detector.py

Detects whether a message is Arabic or English.

Returns "ar" or "en" — no other values.  The rest of the backend
(pipeline, retriever, prompts, TTS voice selection) branches on these
two values only.

Default on failure: "ar"
Arabic is the primary language of the DIGIX AI chatbot. If langdetect
is uncertain or raises an exception (too-short text, mixed script),
defaulting to Arabic is the safer choice for this deployment.

Called by:
  pipeline.py — to set the language when the API layer does not provide it
"""

from langdetect import LangDetectException
from langdetect import detect as _langdetect

def detect(text: str) -> str:
    """
    Return "ar" if the text is Arabic, "en" otherwise.

    Parameters
    ----------
    text : the user's raw message

    Returns
    -------
    "ar" or "en"
    """
    if not text or not text.strip():
        return "ar"

    try:
        lang = _langdetect(text.strip())
        return "ar" if lang == "ar" else "en"
    except LangDetectException:
        # Too short, ambiguous, or unrecognised script — default to Arabic
        return "ar"
