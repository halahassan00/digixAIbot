"""
backend/leads/validators.py

Input validation helpers for the lead collection state machine.

All functions are pure — no I/O, no state.
"""

import re

# ---------------------------------------------------------------------------
# Pattern sets
# ---------------------------------------------------------------------------

ACCEPTANCE_AR = {
    "نعم", "اي", "اه", "أكيد", "يلا", "تمام", "موافق",
    "ليش لا", "طبعا", "حبيبي يلا","ماشي","أجل","اجل",
}

ACCEPTANCE_EN = {
    "yes", "sure", "ok", "okay", "why not",
    "sounds good", "go ahead", "please",
}

REFUSAL_AR = {
    "لا", "لأ", "مو هلق", "بعدين", "مش مهتم", "شكراً بس لا",
}

REFUSAL_EN = {
    "no", "not now", "maybe later", "no thanks", "nope",
}

# Arabic and English interrogative words that start a question sentence
_INTERROGATIVES = {
    # Arabic
    "ما", "هل", "كيف", "أين", "متى", "من", "ماذا", "لماذا", "وين", "شو", "إيش",
    # English
    "what", "how", "where", "when", "who", "why",
    "is", "are", "does", "do", "can", "could", "would", "should",
}

# Regex: email has @ with a dot after it
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Regex: 7–15 digits, optionally prefixed with +, internal spaces/dashes OK
_PHONE_RE = re.compile(r"^\+?[\d\s\-]{7,20}$")
_DIGIT_RE = re.compile(r"\d")

# ---------------------------------------------------------------------------
# Public validators
# ---------------------------------------------------------------------------

def is_valid_contact(value: str) -> bool:
    """
    Return True if value looks like an email address OR a phone number.

    Email: contains @ and a dot after the @.
    Phone: 7–15 digits, optionally prefixed with +, spaces, or dashes.
    """
    v = value.strip()
    if _EMAIL_RE.match(v):
        return True
    if _PHONE_RE.match(v):
        digit_count = len(_DIGIT_RE.findall(v))
        return 7 <= digit_count <= 15
    return False


def is_valid_name(value: str) -> bool:
    """
    Return True if value is a plausible name.
    - At least 2 characters.
    - Not purely numeric.
    - Not a known refusal keyword.
    """
    v = value.strip()
    if len(v) < 2:
        return False
    if v.isdigit():
        return False
    if v.lower() in REFUSAL_EN or v in REFUSAL_AR:
        return False
    return True


def is_acceptance(text: str, language: str) -> bool:
    """Return True if text matches acceptance patterns for the given language."""
    t = text.strip().lower()
    # Check against the exact-match sets
    patterns = ACCEPTANCE_AR if language == "ar" else ACCEPTANCE_EN
    if t in patterns:
        return True
    # Also accept short messages (< 6 words) that contain no refusal keyword
    words = t.split()
    if len(words) < 6:
        refusals = REFUSAL_AR if language == "ar" else REFUSAL_EN
        if not any(r in t for r in refusals):
            return True
    return False


def is_refusal(text: str, language: str) -> bool:
    """Return True if text matches refusal patterns for the given language."""
    t = text.strip().lower()
    patterns = REFUSAL_AR if language == "ar" else REFUSAL_EN
    return any(r in t for r in patterns)


def is_interrupting_question(text: str) -> bool:
    """
    Return True if the message looks like a new question rather than a
    response within the lead flow.

    Heuristic: length > 10 chars AND
      (ends with ؟ or ? OR first word is an interrogative).
    """
    t = text.strip()
    if len(t) <= 10:
        return False
    if t.endswith("؟") or t.endswith("?"):
        return True
    first_word = t.split()[0].lower().rstrip("؟?")
    return first_word in _INTERROGATIVES
