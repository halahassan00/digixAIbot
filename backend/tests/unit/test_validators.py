"""
backend/tests/unit/test_validators.py

Unit tests for backend/leads/validators.py.
Pure functions — no I/O, no mocking required.
"""

import pytest

from backend.leads.validators import (
    is_acceptance,
    is_interrupting_question,
    is_refusal,
    is_valid_contact,
    is_valid_name,
)


# ---------------------------------------------------------------------------
# is_valid_contact
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("email", [
    "hala@example.com",
    "user.name+tag@digix-ai.com",
    "test@sub.domain.org",
])
def test_valid_email_accepted(email):
    assert is_valid_contact(email)


@pytest.mark.parametrize("bad", [
    "notanemail",
    "missing@dot",
    "@nodomain.com",
    "",
])
def test_invalid_email_rejected(bad):
    assert not is_valid_contact(bad)


@pytest.mark.parametrize("phone", [
    "0791234567",        # Jordanian 10-digit
    "+962791234567",     # Jordanian international
    "07 91 23 45 67",    # spaces allowed
    "079-123-4567",      # dashes allowed
    "12345678",          # 8-digit generic
])
def test_valid_phone_accepted(phone):
    assert is_valid_contact(phone)


@pytest.mark.parametrize("bad", [
    "123456",      # too short (6 digits)
    "abc",
    "12 34",       # only 4 digits
])
def test_invalid_phone_rejected(bad):
    assert not is_valid_contact(bad)


# ---------------------------------------------------------------------------
# is_valid_name
# ---------------------------------------------------------------------------

def test_valid_name_arabic():
    assert is_valid_name("هالة حسن")

def test_valid_name_english():
    assert is_valid_name("Hala Hassan")

def test_name_too_short_rejected():
    assert not is_valid_name("A")

def test_numeric_name_rejected():
    assert not is_valid_name("12345")

def test_refusal_keyword_as_name_rejected():
    assert not is_valid_name("no")


# ---------------------------------------------------------------------------
# is_acceptance / is_refusal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,lang", [
    ("نعم", "ar"),
    ("أكيد", "ar"),
    ("تمام", "ar"),
    ("yes", "en"),
    ("sure", "en"),
    ("ok", "en"),
    ("okay", "en"),
    ("sounds good", "en"),
])
def test_acceptance_patterns(text, lang):
    assert is_acceptance(text, lang)


@pytest.mark.parametrize("text,lang", [
    ("لا", "ar"),
    ("مو هلق", "ar"),
    ("مش مهتم", "ar"),
    ("no", "en"),
    ("not now", "en"),
    ("no thanks", "en"),
])
def test_refusal_patterns(text, lang):
    assert is_refusal(text, lang)


# ---------------------------------------------------------------------------
# is_interrupting_question
# ---------------------------------------------------------------------------

def test_arabic_question_ending_with_mark():
    assert is_interrupting_question("ما هي خدمات الشركة؟")

def test_english_question_ending_with_mark():
    assert is_interrupting_question("What services do you offer?")

def test_interrogative_start_no_mark():
    assert is_interrupting_question("How can I register for this course")

def test_short_message_not_an_interruption():
    assert not is_interrupting_question("نعم")

def test_short_message_with_question_mark_not_interruption():
    # ≤ 10 chars — length check fails first
    assert not is_interrupting_question("أكيد؟")

def test_plain_statement_not_an_interruption():
    assert not is_interrupting_question("أنا مهتم بالكورس هذا")
