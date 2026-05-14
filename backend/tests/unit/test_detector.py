"""
backend/tests/unit/test_detector.py

Unit tests for backend/language/detector.py (GROUP 6, tests 31-34).
"""

import pytest
from langdetect import DetectorFactory

from backend.language.detector import detect

# Seed for reproducible langdetect results across runs
DetectorFactory.seed = 0


def test_detect_arabic_returns_ar():
    """Pure Arabic sentence → 'ar' (test 31)."""
    assert detect("مرحباً، كيف يمكنني مساعدتك؟") == "ar"


def test_detect_english_returns_en():
    """Pure English sentence → 'en' (test 32)."""
    assert detect("Hello, how can I help you?") == "en"


def test_detect_empty_string_does_not_crash():
    """Empty string returns 'ar' or 'en' without raising (test 33)."""
    result = detect("")
    assert result in ("ar", "en")


def test_detect_mixed_arabic_majority_returns_ar():
    """Arabic-dominant mixed sentence → 'ar' (test 34)."""
    mixed = (
        "هذا النص يحتوي على كلمات عربية كثيرة جداً "
        "مع بعض English words فقط"
    )
    assert detect(mixed) == "ar"
