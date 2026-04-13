"""
backend/rag/pipeline.py

Core RAG logic — ties retriever + GPT-4o together.

This is the single function the /chat route calls. Everything else
(embedding, retrieval, prompt building, language detection, LLM call)
is delegated to the appropriate module.

Call flow per user message
--------------------------
  1. Language — use the language passed by the API layer if present;
                fall back to detector.detect() if not.
  2. retriever.py  — embed query, fetch top 4 chunks from ChromaDB
  3. prompts.py    — build message list (system + context + history + query)
  4. llm/client.py — send to GPT-4o, return response text
  5. leads/        — check whether the response should trigger lead collection

API contract (POST /chat)
-------------------------
Request:  { "message": "...", "session_id": "...", "language": "ar" }
Response: { "response": "...", "language": "ar", "collect_lead": false }
"""

from typing import Optional

from backend.language.detector import detect
from backend.llm.client import chat
from backend.rag.prompts import build_messages
from backend.rag.retriever import RetrievedChunk, retrieve

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_N_RESULTS = 4   # per CONTEXT.md: "return top 4 most relevant chunks"

# Lead-trigger keywords — if the user's message contains any of these,
# the frontend should prompt the lead collection form.
# collector.py will own the full conversational lead flow once built;
# this covers the simple trigger detection used here.
_LEAD_TRIGGERS_AR = [
    "سعر", "تكلفة", "كم يكلف", "اشتراك", "تسجيل", "كيف أسجل",
    "تواصل", "تواصلوا", "أريد الانضمام", "مهتم", "حجز",
]
_LEAD_TRIGGERS_EN = [
    "price", "cost", "how much", "enroll", "register", "sign up",
    "contact", "interested", "join", "book", "get in touch",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _should_collect_lead(query: str, language: str) -> bool:
    """
    Return True if the query contains a lead-trigger keyword.

    This is a lightweight check — collector.py will own the full
    conversational lead flow (name → email → org → interest) once built.
    """
    q = query.lower()
    triggers = _LEAD_TRIGGERS_AR if language == "ar" else _LEAD_TRIGGERS_EN
    return any(trigger in q for trigger in triggers)

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(
    query: str,
    chat_history: Optional[list[dict]] = None,
    language: Optional[str] = None,
    n_results: int = DEFAULT_N_RESULTS,
) -> dict:
    """
    Run the full RAG pipeline for a single user message.

    Parameters
    ----------
    query        : the user's message text (Arabic or English)
    chat_history : prior turns as [{"role": "user"/"assistant", "content": "..."}].
                   Pass None or [] for the first message in a session.
    language     : "ar" or "en" — if provided by the API layer (from the
                   request body), use it directly.  If None, auto-detect.
    n_results    : number of chunks to retrieve (default 4)

    Returns
    -------
    dict matching the /chat response contract:
      "response"     : str   — the LLM's answer
      "language"     : str   — "ar" or "en"
      "collect_lead" : bool  — True if the frontend should open the lead form
    """
    if chat_history is None:
        chat_history = []

    # 1. Language — prefer the value passed in by the API layer (already
    #    validated upstream); fall back to auto-detection if absent.
    if not language:
        language = detect(query)

    # 2. Retrieve — filter by detected/declared language so Arabic questions
    #    get Arabic chunks and English questions get English chunks.
    chunks: list[RetrievedChunk] = retrieve(
        query=query,
        language=language,
        n_results=n_results,
    )

    # 3. Build message list (system prompt + context + history + query)
    messages = build_messages(
        query=query,
        chunks=chunks,
        language=language,
        chat_history=chat_history,
    )

    # 4. Call GPT-4o
    answer = chat(messages)

    # 5. Lead trigger check
    collect_lead = _should_collect_lead(query, language)

    return {
        "response": answer,
        "language": language,
        "collect_lead": collect_lead,
    }
