"""
backend/leads/collector.py

Conversational lead collection state machine.

The state machine runs across multiple chat turns, collecting the user's
name, contact info, and organisation before submitting to Google Sheets.
It is intentionally kept separate from the LLM — the system prompt
explicitly forbids the LLM from asking for personal information.

State diagram
-------------
  IDLE
    ↓ (trigger fires)
  OFFERED
    ↓ accept              ↓ refuse
  COLLECTING_NAME        DECLINED (terminal for session)
    ↓
  COLLECTING_CONTACT
    ↓
  COLLECTING_ORG
    ↓
  CONFIRMING
    ↓ accept              ↓ refuse
  SUBMITTED (terminal)  COLLECTING_NAME (restart)

Any stage in {COLLECTING_NAME, COLLECTING_CONTACT, COLLECTING_ORG}:
  If user sends a question → exit to IDLE (interruption).

Public API
----------
  process_turn(user_input, lead_session, rag_response, triggering_interest)
    → (bot_message: str, updated_lead_session: LeadSession)

This function is purely synchronous and side-effect-free.
Google Sheets submission is triggered by pipeline.py after this function
returns stage == "SUBMITTED".
"""

from dataclasses import dataclass

from backend.leads.validators import (
    is_acceptance,
    is_interrupting_question,
    is_refusal,
    is_valid_contact,
)

# ---------------------------------------------------------------------------
# LeadSession dataclass
# ---------------------------------------------------------------------------

@dataclass
class LeadSession:
    stage: str = "IDLE"
    name: str = ""
    contact: str = ""
    org: str = ""
    interest: str = ""
    language: str = "ar"
    offered_this_session: bool = False
    contact_attempts: int = 0   # counts validation failures in COLLECTING_CONTACT


# ---------------------------------------------------------------------------
# Bot message constants
# ---------------------------------------------------------------------------

_OFFER_AR = "يبدو أنك مهتم — هل تودّ أن يتواصل معك فريقنا لمزيد من التفاصيل؟"
_OFFER_EN = "It sounds like you're interested — would you like our team to reach out with more details?"

_ASK_NAME_AR = "ممتاز! ما اسمك الكريم؟"
_ASK_NAME_EN = "Great! What's your name?"

_DECLINE_AR = "بالتأكيد! لا مشكلة. هل يمكنني مساعدتك بأي شيء آخر؟"
_DECLINE_EN = "Of course! No problem. Can I help you with anything else?"

_ASK_CONTACT_AR = "شكراً {name}! ما هو بريدك الإلكتروني أو رقم هاتفك؟"
_ASK_CONTACT_EN = "Thanks {name}! What's your email or phone number?"

_INVALID_CONTACT_AR = "عذراً، لم أتعرّف على هذه المعلومات. هل يمكنك إدخال بريدك الإلكتروني أو رقم هاتفك مرة أخرى؟"
_INVALID_CONTACT_EN = "Sorry, I didn't recognise that. Could you enter your email address or phone number again?"

_ASK_ORG_AR = "هل تمثّل شركة أو مؤسسة، أم التسجيل بصفة شخصية؟"
_ASK_ORG_EN = "Are you registering on behalf of an organisation, or as an individual?"

_CONFIRM_AR = (
    "ممتاز! سأسجّل بياناتك:\n"
    "• الاسم: {name}\n"
    "• التواصل: {contact}\n"
    "• الاهتمام: {interest}\n"
    "هل المعلومات صحيحة؟"
)
_CONFIRM_EN = (
    "Perfect! Let me confirm your details:\n"
    "• Name: {name}\n"
    "• Contact: {contact}\n"
    "• Interest: {interest}\n"
    "Is this correct?"
)

_SUBMITTED_AR = "شكراً {name}! سيتواصل معك فريقنا قريباً. هل يمكنني مساعدتك بأي شيء آخر؟"
_SUBMITTED_EN = "Thank you {name}! Our team will be in touch soon. Is there anything else I can help you with?"

_RESTART_AR = "لا بأس! هل تريد تصحيح معلوماتك؟"
_RESTART_EN = "No problem! Would you like to correct your details?"

# Individual signals — if the user uses these, org is set to ""
_INDIVIDUAL_SIGNALS_AR = {"شخصي", "فردي", "لحالي", "بصفتي الشخصية", "لا شركة"}
_INDIVIDUAL_SIGNALS_EN = {"individual", "personal", "just me", "myself", "no company", "no org"}

# ---------------------------------------------------------------------------
# Private handlers (one per stage)
# ---------------------------------------------------------------------------

def _msg(template_ar: str, template_en: str, language: str, **kwargs) -> str:
    tpl = template_ar if language == "ar" else template_en
    return tpl.format(**kwargs) if kwargs else tpl


def _handle_idle(
    user_input: str,
    lead: LeadSession,
    rag_response: str,
    triggering_interest: str,
) -> tuple[str, LeadSession]:
    """IDLE: offer is appended to the RAG response when a trigger fires."""
    lead.interest = triggering_interest or user_input[:80]
    lead.offered_this_session = True
    lead.stage = "OFFERED"
    offer = _msg(_OFFER_AR, _OFFER_EN, lead.language)
    return f"{rag_response}\n\n{offer}", lead


def _handle_offered(user_input: str, lead: LeadSession) -> tuple[str, LeadSession]:
    """OFFERED: accept → COLLECTING_NAME, refuse → DECLINED."""
    if is_refusal(user_input, lead.language):
        lead.stage = "DECLINED"
        return _msg(_DECLINE_AR, _DECLINE_EN, lead.language), lead

    if is_acceptance(user_input, lead.language):
        lead.stage = "COLLECTING_NAME"
        return _msg(_ASK_NAME_AR, _ASK_NAME_EN, lead.language), lead

    # Ambiguous — treat as acceptance
    lead.stage = "COLLECTING_NAME"
    return _msg(_ASK_NAME_AR, _ASK_NAME_EN, lead.language), lead


def _handle_name(
    user_input: str,
    lead: LeadSession,
    rag_response: str,
) -> tuple[str, LeadSession]:
    """COLLECTING_NAME → COLLECTING_CONTACT (or interrupt back to IDLE)."""
    if is_interrupting_question(user_input):
        lead.stage = "IDLE"
        return rag_response, lead

    # Any non-question input accepted as name (even if ends with ?)
    name = user_input.strip().rstrip("؟?").strip()
    if not name:
        return _msg(_ASK_NAME_AR, _ASK_NAME_EN, lead.language), lead

    lead.name = name
    lead.stage = "COLLECTING_CONTACT"
    return _msg(_ASK_CONTACT_AR, _ASK_CONTACT_EN, lead.language, name=lead.name), lead


def _handle_contact(
    user_input: str,
    lead: LeadSession,
    rag_response: str,
) -> tuple[str, LeadSession]:
    """COLLECTING_CONTACT → COLLECTING_ORG (or interrupt back to IDLE)."""
    if is_interrupting_question(user_input):
        lead.stage = "IDLE"
        return rag_response, lead

    contact = user_input.strip()

    if is_valid_contact(contact):
        lead.contact = contact
        lead.contact_attempts = 0
        lead.stage = "COLLECTING_ORG"
        return _msg(_ASK_ORG_AR, _ASK_ORG_EN, lead.language), lead

    lead.contact_attempts += 1
    if lead.contact_attempts >= 2:
        # Accept on second attempt regardless — don't block the flow
        lead.contact = contact
        lead.contact_attempts = 0
        lead.stage = "COLLECTING_ORG"
        return _msg(_ASK_ORG_AR, _ASK_ORG_EN, lead.language), lead

    return _msg(_INVALID_CONTACT_AR, _INVALID_CONTACT_EN, lead.language), lead


def _handle_org(
    user_input: str,
    lead: LeadSession,
    rag_response: str,
) -> tuple[str, LeadSession]:
    """COLLECTING_ORG → CONFIRMING (or interrupt back to IDLE)."""
    if is_interrupting_question(user_input):
        lead.stage = "IDLE"
        return rag_response, lead

    t = user_input.strip().lower()
    individual_signals = _INDIVIDUAL_SIGNALS_AR | _INDIVIDUAL_SIGNALS_EN
    if any(sig in t for sig in individual_signals):
        lead.org = ""
    else:
        lead.org = user_input.strip()

    lead.stage = "CONFIRMING"
    summary = _msg(
        _CONFIRM_AR, _CONFIRM_EN, lead.language,
        name=lead.name,
        contact=lead.contact,
        interest=lead.interest,
    )
    return summary, lead


def _handle_confirming(user_input: str, lead: LeadSession) -> tuple[str, LeadSession]:
    """
    CONFIRMING → SUBMITTED (accept) or COLLECTING_NAME (restart on refusal).

    NOTE: This function does NOT call Google Sheets.
    The pipeline detects stage == "SUBMITTED" and calls submit_lead().
    """
    if is_refusal(user_input, lead.language):
        # Restart collection — reset collected fields but keep language + interest
        lead.stage = "COLLECTING_NAME"
        lead.name = ""
        lead.contact = ""
        lead.org = ""
        lead.contact_attempts = 0
        restart = _msg(_RESTART_AR, _RESTART_EN, lead.language)
        ask_name = _msg(_ASK_NAME_AR, _ASK_NAME_EN, lead.language)
        return f"{restart}\n{ask_name}", lead

    # Accept (or ambiguous — treat as accept)
    lead.stage = "SUBMITTED"
    return _msg(_SUBMITTED_AR, _SUBMITTED_EN, lead.language, name=lead.name), lead


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_turn(
    user_input: str,
    lead_session: LeadSession,
    rag_response: str,
    triggering_interest: str = "",
) -> tuple[str, LeadSession]:
    """
    Given the user's input and the current lead session state,
    return (bot_message, updated_lead_session).

    - If stage is IDLE and no trigger: return rag_response unchanged.
    - If stage is IDLE and trigger fires: append offer to rag_response.
    - All other stages: return the next collector prompt (rag_response is
      only used for interruption handling in mid-flow stages).

    Parameters
    ----------
    user_input         : the user's raw message
    lead_session       : current state (a copy is returned — original is NOT mutated)
    rag_response       : the answer already generated by the RAG pipeline.
                         Used in IDLE (appended to) and for mid-flow interruptions
                         (returned as-is when the user asks a new question).
    triggering_interest: the topic that triggered the lead, e.g. "Power BI training"
    """
    # Work on a copy so the caller's original is not mutated on error
    from dataclasses import replace
    lead = replace(lead_session)

    stage = lead.stage

    if stage == "IDLE":
        if not triggering_interest and not rag_response:
            return rag_response, lead
        return _handle_idle(user_input, lead, rag_response, triggering_interest)

    if stage == "OFFERED":
        return _handle_offered(user_input, lead)

    if stage == "COLLECTING_NAME":
        return _handle_name(user_input, lead, rag_response)

    if stage == "COLLECTING_CONTACT":
        return _handle_contact(user_input, lead, rag_response)

    if stage == "COLLECTING_ORG":
        return _handle_org(user_input, lead, rag_response)

    if stage == "CONFIRMING":
        return _handle_confirming(user_input, lead)

    # SUBMITTED or DECLINED — no further collection this session
    return rag_response, lead
