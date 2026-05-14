"""
backend/rag/pipeline.py

Core RAG logic — ties retriever + GPT-4o + lead collection together.

This is the single function the /chat route calls. Everything else
(embedding, retrieval, prompt building, language detection, LLM call,
lead state machine) is delegated to the appropriate module.

Call flow per user message
--------------------------
  1. Lead session routing:
     - If mid-flow (not IDLE/DECLINED/SUBMITTED) AND not an interrupting question:
       → Collector handles the turn entirely; RAG is skipped.
     - If mid-flow AND interrupting question:
       → Reset to IDLE; fall through to full RAG path (answer the question).
  2. Language — use the language passed by the API layer if present;
                fall back to detector.detect() if not.
  3. retriever.py  — embed query, fetch top 4 chunks from ChromaDB
  4. prompts.py    — build message list (system + context + history + query)
  5. llm/client.py — send to GPT-4o, return response text
  6. Parse [CHUNK_ID: ...] tag from response; build sources payload
  7. Lead trigger check — if trigger fires and not already offered:
     → Append offer to RAG answer via collector.process_turn()
  8. If stage transitioned to SUBMITTED:
     → Await google_sheets.submit_lead()

API contract (POST /chat)
-------------------------
Request:  { "message": "...", "session_id": "...", "language": "ar",
            "lead_session": {...} or null }
Response: { "response": "...", "language": "ar", "collect_lead": false,
            "lead_stage": "IDLE", "lead_session": {...},
            "sources": [{"source_file": "...", "url": "..."}] }
"""

import dataclasses
import logging
import re
from typing import Optional

from backend.language.detector import detect
from backend.leads.collector import LeadSession, process_turn
from backend.leads.google_sheets import LeadSubmissionError, submit_lead
from backend.leads.validators import is_interrupting_question
from backend.llm.client import chat
from backend.rag.prompts import build_messages
from backend.rag.retriever import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_N_RESULTS = 4   # per CONTEXT.md: "return top 4 most relevant chunks"

# Lead-trigger keywords — if the user's message contains any of these,
# the collector is invited to append an offer to the RAG answer.
_LEAD_TRIGGERS_AR = [
    # Pricing
    "سعر", "تكلفة", "كم يكلف", "بكم", "قديش", "كم بكلف", "شو السعر",
    # Registration / enrolment
    "تسجيل", "كيف أسجل", "بدي أسجل", "كيف أشترك", "وين أسجل",
    "اشتراك", "التحاق",
    # Joining / participation
    "أريد الانضمام", "بدي أنضم", "بدي أشارك", "بدي آخذ الكورس",
    "بدي أحضر", "مشاركة",
    # Interest signals
    "مهتم", "يهمني", "هاد الشي يهمني", "بدي أعرف أكثر",
    "ممكن تفاصيل أكثر", "تفاصيل إضافية",
    # Contact
    "تواصل", "تواصلوا", "كيف أتواصل", "في رقم", "في واتساب",
    "ابعتلي", "أرسل لي",
    "حجز", "بدي أحجز", "في حجز",
    # Next steps
    "كيف أبدأ", "شو الخطوات", "إيش اللي بعده", "شو اللي بدي أعمله",
    # Schedule / timing
    "متى تبدأ", "إيمتى تبدأ", "مواعيد", "جدول", "الدورة القادمة",
    "الدفعة الجاية",
]

_LEAD_TRIGGERS_EN = [
    "price", "cost", "how much", "fee", "fees",
    "enroll", "enrolment", "register", "sign up", "sign me up",
    "contact", "interested", "get in touch", "reach out",
    "join", "book", "booking", "reserve",
    "get started", "next steps", "how do i start",
    "when does it start", "schedule", "upcoming", "next batch",
    "tell me more", "more details", "more information",
    "can i get", "i want to",
]

# ---------------------------------------------------------------------------
# Chunk-tag parsing
# ---------------------------------------------------------------------------

# Tolerant of extra whitespace and optional surrounding quotes.
# Anchored to end-of-string (after optional trailing whitespace/newlines).
_CHUNK_TAG_RE = re.compile(
    r'\[CHUNK_ID:\s*"?([^\]"]+?)"?\s*\]\s*$',
    re.IGNORECASE | re.MULTILINE,
)


def _parse_chunk_tag(answer: str) -> tuple[str, Optional[str]]:
    """Strip the [CHUNK_ID: ...] tag from the end of the answer.

    Returns (cleaned_answer, chunk_id) where chunk_id is None if absent.
    """
    m = _CHUNK_TAG_RE.search(answer)
    if not m:
        return answer, None
    chunk_id = m.group(1).strip()
    cleaned = answer[:m.start()].rstrip()
    return cleaned, chunk_id


def _build_sources(
    chunk_id: Optional[str],
    chunks: list[RetrievedChunk],
) -> list[dict]:
    """Resolve a chunk ID to a sources entry using the retrieved chunks list."""
    if not chunk_id:
        return []
    for chunk in chunks:
        if chunk.id == chunk_id:
            entry: dict = {"source_file": chunk.source}
            if chunk.url:
                entry["url"] = chunk.url
            return [entry]
    logger.warning(
        "GPT-4o cited unknown chunk ID %r — sources will be empty", chunk_id
    )
    return []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_collect_lead(query: str, language: str) -> bool:
    """Return True if the query contains a lead-trigger keyword."""
    q = query.lower()
    triggers = _LEAD_TRIGGERS_AR if language == "ar" else _LEAD_TRIGGERS_EN
    return any(trigger in q for trigger in triggers)


def _extract_interest(query: str) -> str:
    """Return a short description of what the user is interested in."""
    return query[:80]


def _build_result(
    response: str,
    lead_session: LeadSession,
    sources: list[dict],
) -> dict:
    return {
        "response":     response,
        "language":     lead_session.language,
        "collect_lead": lead_session.stage == "OFFERED",
        "lead_stage":   lead_session.stage,
        "lead_session": dataclasses.asdict(lead_session),
        "sources":      sources,
    }

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run(
    query: str,
    chat_history: Optional[list[dict]] = None,
    language: Optional[str] = None,
    n_results: int = DEFAULT_N_RESULTS,
    lead_session: Optional[LeadSession] = None,
    session_id: str = "",
) -> dict:
    """
    Run the full RAG pipeline for a single user message.

    Parameters
    ----------
    query        : the user's message text (Arabic or English)
    chat_history : prior turns as [{"role": "user"/"assistant", "content": "..."}].
                   Pass None or [] for the first message in a session.
    language     : "ar" or "en" — if provided by the API layer, use it directly.
                   If None, auto-detect.
    n_results    : number of chunks to retrieve (default 4)
    lead_session : current lead collection state (None = fresh session)
    session_id   : used when submitting lead to Google Sheets

    Returns
    -------
    dict with keys: response, language, collect_lead, lead_stage,
                    lead_session (dict), sources
    """
    if chat_history is None:
        chat_history = []

    # Initialise session if this is the first turn
    if lead_session is None:
        lead_session = LeadSession(language=language or "ar")

    # ------------------------------------------------------------------
    # 1. Lead session routing
    # ------------------------------------------------------------------
    _mid_flow_stages = {"OFFERED", "COLLECTING_NAME", "COLLECTING_CONTACT",
                        "COLLECTING_ORG", "CONFIRMING"}
    mid_flow = lead_session.stage in _mid_flow_stages

    if mid_flow and not is_interrupting_question(query):
        # Collector owns this turn — skip the RAG pipeline entirely
        prev_stage = lead_session.stage
        response_text, lead_session = process_turn(
            user_input=query,
            lead_session=lead_session,
            rag_response="",
        )
        # Fire Sheets submission when CONFIRMING → SUBMITTED
        if lead_session.stage == "SUBMITTED" and prev_stage == "CONFIRMING":
            try:
                await submit_lead(lead_session, session_id)
            except LeadSubmissionError:
                pass  # already logged inside submit_lead
        return _build_result(response_text, lead_session, sources=[])

    if mid_flow and is_interrupting_question(query):
        # Interruption: answer the question via RAG, then reset stage
        lead_session.stage = "IDLE"
        # offered_this_session stays True — do NOT re-offer this turn

    # ------------------------------------------------------------------
    # 2. Language detection
    # ------------------------------------------------------------------
    if not language:
        language = detect(query)
    lead_session.language = language

    # ------------------------------------------------------------------
    # 3. Retrieve
    # ------------------------------------------------------------------
    chunks: list[RetrievedChunk] = retrieve(
        query=query,
        language=language,
        n_results=n_results,
    )

    # ------------------------------------------------------------------
    # 4. Build message list and call GPT-4o
    # ------------------------------------------------------------------
    messages = build_messages(
        query=query,
        chunks=chunks,
        language=language,
        chat_history=chat_history,
    )
    answer = chat(messages)

    # ------------------------------------------------------------------
    # 5. Source attribution — parse and strip [CHUNK_ID: ...] tag
    # ------------------------------------------------------------------
    answer, chunk_id = _parse_chunk_tag(answer)
    if chunk_id is None:
        logger.warning(
            "GPT-4o returned an answer with no [CHUNK_ID] tag — possible prompt drift"
        )
    sources = _build_sources(chunk_id, chunks)

    # ------------------------------------------------------------------
    # 6. Lead trigger check + optional offer appending
    # ------------------------------------------------------------------
    trigger = _should_collect_lead(query, language)
    interrupted = mid_flow  # True if we just handled an interruption

    if trigger and not lead_session.offered_this_session and not interrupted:
        interest = _extract_interest(query)
        answer, lead_session = process_turn(
            user_input=query,
            lead_session=lead_session,
            rag_response=answer,
            triggering_interest=interest,
        )
    elif interrupted:
        # Return the RAG answer as-is; process_turn not needed (stage already reset)
        pass

    return _build_result(answer, lead_session, sources)
