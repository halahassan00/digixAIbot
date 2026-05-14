"""
backend/tests/unit/test_collector.py

Unit tests for the lead collection state machine (collector.py).

All tests call process_turn() directly with pre-built LeadSession objects.
No mocking of external systems is required — process_turn() is pure.
"""

from backend.leads.collector import LeadSession, process_turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ar(**kwargs) -> LeadSession:
    return LeadSession(language="ar", **kwargs)

def _en(**kwargs) -> LeadSession:
    return LeadSession(language="en", **kwargs)


# ---------------------------------------------------------------------------
# IDLE → OFFERED
# ---------------------------------------------------------------------------

def test_idle_to_offered_appends_offer_arabic():
    """Trigger fires: offer is appended to rag_response; offered_this_session=True."""
    lead = _ar(stage="IDLE")
    msg, updated = process_turn(
        user_input="بدي أسجل",
        lead_session=lead,
        rag_response="تقدم Digix AI برامج تدريب متعددة.",
        triggering_interest="Power BI",
    )
    assert updated.stage == "OFFERED"
    assert updated.offered_this_session is True
    assert "تقدم Digix AI" in msg          # original answer preserved
    assert "يتواصل معك فريقنا" in msg or "هل تودّ" in msg  # offer appended


def test_idle_to_offered_sets_interest():
    """Interest is pre-filled from triggering_interest, not from user input."""
    lead = _en(stage="IDLE")
    _, updated = process_turn(
        user_input="I want to enroll in Power BI",
        lead_session=lead,
        rag_response="We offer Power BI training.",
        triggering_interest="Power BI",
    )
    assert updated.interest == "Power BI"


# ---------------------------------------------------------------------------
# OFFERED → COLLECTING_NAME
# ---------------------------------------------------------------------------

def test_offered_acceptance_arabic_transitions_to_collecting_name():
    lead = _ar(stage="OFFERED", interest="Power BI", offered_this_session=True)
    msg, updated = process_turn("نعم", lead, "")
    assert updated.stage == "COLLECTING_NAME"
    assert "اسم" in msg


def test_offered_acceptance_english_transitions_to_collecting_name():
    lead = _en(stage="OFFERED", interest="Power BI", offered_this_session=True)
    msg, updated = process_turn("sure", lead, "")
    assert updated.stage == "COLLECTING_NAME"
    assert "name" in msg.lower()


# ---------------------------------------------------------------------------
# OFFERED → DECLINED
# ---------------------------------------------------------------------------

def test_offered_refusal_arabic_transitions_to_declined():
    lead = _ar(stage="OFFERED", offered_this_session=True)
    msg, updated = process_turn("لا", lead, "")
    assert updated.stage == "DECLINED"
    assert "مشكلة" in msg or "لا مشكلة" in msg


def test_declined_no_re_offer():
    """Once DECLINED, the trigger must not fire an offer again."""
    lead = _ar(stage="DECLINED", offered_this_session=True)
    rag = "تقدم Digix AI برامج تدريب متعددة."
    msg, updated = process_turn("بدي أسجل", lead, rag, triggering_interest="Power BI")
    # Stage stays DECLINED; no offer appended
    assert updated.stage == "DECLINED"
    assert "يتواصل معك" not in msg


# ---------------------------------------------------------------------------
# COLLECTING_NAME → COLLECTING_CONTACT
# ---------------------------------------------------------------------------

def test_name_accepted_and_transitions_to_collecting_contact():
    lead = _ar(stage="COLLECTING_NAME", interest="Power BI")
    msg, updated = process_turn("هالة حسن", lead, "")
    assert updated.stage == "COLLECTING_CONTACT"
    assert updated.name == "هالة حسن"
    assert "بريد" in msg or "هاتف" in msg


def test_name_accepted_english():
    lead = _en(stage="COLLECTING_NAME", interest="AI course")
    msg, updated = process_turn("Hala Hassan", lead, "")
    assert updated.stage == "COLLECTING_CONTACT"
    assert updated.name == "Hala Hassan"


# ---------------------------------------------------------------------------
# COLLECTING_CONTACT → COLLECTING_ORG
# ---------------------------------------------------------------------------

def test_valid_email_accepted_transitions_to_collecting_org():
    lead = _ar(stage="COLLECTING_CONTACT", name="هالة", interest="Power BI")
    msg, updated = process_turn("hala@example.com", lead, "")
    assert updated.stage == "COLLECTING_ORG"
    assert updated.contact == "hala@example.com"
    assert "شركة" in msg or "مؤسسة" in msg


def test_invalid_contact_first_attempt_asks_to_clarify():
    lead = _ar(stage="COLLECTING_CONTACT", name="هالة", interest="Power BI",
               contact_attempts=0)
    msg, updated = process_turn("not-valid", lead, "")
    assert updated.stage == "COLLECTING_CONTACT"   # still collecting
    assert updated.contact_attempts == 1
    assert "عذراً" in msg or "مرة أخرى" in msg


def test_invalid_contact_second_attempt_accepted_anyway():
    """Accept on second attempt regardless — don't block the flow."""
    lead = _ar(stage="COLLECTING_CONTACT", name="هالة", interest="Power BI",
               contact_attempts=1)
    _, updated = process_turn("stillnotvalid", lead, "")
    assert updated.stage == "COLLECTING_ORG"
    assert updated.contact == "stillnotvalid"


# ---------------------------------------------------------------------------
# COLLECTING_ORG → CONFIRMING
# ---------------------------------------------------------------------------

def test_org_individual_signal_sets_empty_org():
    lead = _ar(stage="COLLECTING_ORG", name="هالة", contact="079123",
               interest="Power BI")
    msg, updated = process_turn("شخصي", lead, "")
    assert updated.stage == "CONFIRMING"
    assert updated.org == ""


def test_org_name_stored():
    lead = _en(stage="COLLECTING_ORG", name="Hala", contact="hala@ex.com",
               interest="AI")
    _, updated = process_turn("Digix AI Ltd", lead, "")
    assert updated.org == "Digix AI Ltd"


# ---------------------------------------------------------------------------
# CONFIRMING → SUBMITTED
# ---------------------------------------------------------------------------

def test_confirming_acceptance_transitions_to_submitted():
    """Acceptance in CONFIRMING sets stage to SUBMITTED (no Sheets call here)."""
    lead = _ar(stage="CONFIRMING", name="هالة", contact="079123", org="",
               interest="Power BI")
    msg, updated = process_turn("نعم", lead, "")
    assert updated.stage == "SUBMITTED"
    assert "شكراً" in msg or "سيتواصل" in msg


# ---------------------------------------------------------------------------
# CONFIRMING → COLLECTING_NAME (restart)
# ---------------------------------------------------------------------------

def test_confirming_refusal_restarts_collection():
    lead = _ar(stage="CONFIRMING", name="هالة", contact="079123", org="",
               interest="Power BI")
    _, updated = process_turn("لا", lead, "")
    assert updated.stage == "COLLECTING_NAME"
    assert updated.name == ""
    assert updated.contact == ""


# ---------------------------------------------------------------------------
# Mid-flow interruption
# ---------------------------------------------------------------------------

def test_interruption_during_collecting_name_exits_to_idle():
    """Question during COLLECTING_NAME exits flow; RAG response is returned as-is."""
    lead = _ar(stage="COLLECTING_NAME", offered_this_session=True)
    rag = "تقدم Digix AI تدريباً على Power BI."
    msg, updated = process_turn("ما هي مدة الكورس؟", lead, rag)
    assert updated.stage == "IDLE"
    assert updated.offered_this_session is True   # NOT reset
    assert msg == rag


def test_interruption_during_collecting_contact_exits_to_idle():
    lead = _en(stage="COLLECTING_CONTACT", name="Hala", offered_this_session=True)
    rag = "The Power BI course lasts 3 months."
    msg, updated = process_turn("How long is the course?", lead, rag)
    assert updated.stage == "IDLE"
    assert msg == rag


# ---------------------------------------------------------------------------
# Language consistency
# ---------------------------------------------------------------------------

def test_arabic_flow_stays_arabic():
    """All messages in an Arabic flow use Arabic text."""
    lead = _ar(stage="OFFERED", offered_this_session=True)
    msg, updated = process_turn("نعم", lead, "")
    assert updated.language == "ar"
    # Arabic response should not be in English
    assert "name" not in msg.lower() and "great" not in msg.lower()


def test_english_flow_stays_english():
    """All messages in an English flow use English text."""
    lead = _en(stage="OFFERED", offered_this_session=True)
    msg, updated = process_turn("sure", lead, "")
    assert updated.language == "en"
    assert "name" in msg.lower() or "great" in msg.lower()
