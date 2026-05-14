"""
backend/api/routes/chat.py

POST /chat — the main chatbot endpoint.

The backend is stateless between requests. The frontend persists
lead_session and sends it back with every request so the lead
collection state machine can continue across turns.

API contract (from CONTEXT.md — do not change without team discussion):
  Request:
    {
      "message":      "ما هي خدماتكم؟",
      "session_id":   "abc123",
      "language":     "ar",
      "lead_session": { ...LeadSession fields } | null
    }
  Response:
    {
      "response":     "...",
      "language":     "ar",
      "collect_lead": false,
      "lead_stage":   "IDLE",
      "lead_session": { ...updated LeadSession fields },
      "sources":      [{"source_file": "services_ar.txt", "url": "..."}]
    }

Session history
---------------
Conversation history is stored in memory keyed by session_id.  This is
sufficient for a dev/demo deployment.  Each session keeps the last
MAX_HISTORY_TURNS turns to bound the context window sent to GPT-4o.
"""

from collections import OrderedDict
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.leads.collector import LeadSession
from backend.rag.pipeline import run
from backend.utils.logger import get_logger, log_unanswered

router = APIRouter()
logger = get_logger("api.chat")

# ---------------------------------------------------------------------------
# Session store (in-memory)
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS = 6     # keep last 6 turns (3 user + 3 assistant)
MAX_SESSIONS      = 1000  # evict oldest sessions beyond this limit

# OrderedDict gives O(1) LRU eviction when MAX_SESSIONS is reached
_sessions: OrderedDict[str, list[dict]] = OrderedDict()


def _get_history(session_id: str) -> list[dict]:
    return _sessions.get(session_id, [])


def _update_history(session_id: str, user_msg: str, assistant_msg: str) -> None:
    history = _sessions.get(session_id, [])
    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})

    # Trim to MAX_HISTORY_TURNS (each turn = 2 messages)
    if len(history) > MAX_HISTORY_TURNS * 2:
        history = history[-(MAX_HISTORY_TURNS * 2):]

    # Evict oldest session if store is full
    if session_id not in _sessions and len(_sessions) >= MAX_SESSIONS:
        _sessions.popitem(last=False)

    _sessions[session_id] = history
    _sessions.move_to_end(session_id)   # mark as recently used

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class LeadSessionModel(BaseModel):
    stage:                str  = "IDLE"
    name:                 str  = ""
    contact:              str  = ""
    org:                  str  = ""
    interest:             str  = ""
    language:             str  = "ar"
    offered_this_session: bool = False
    contact_attempts:     int  = 0


class ChatRequest(BaseModel):
    message:      str = Field(..., min_length=1, max_length=2000)
    session_id:   str = Field(..., min_length=1, max_length=64)
    language:     str = Field("ar", pattern="^(ar|en)$")
    lead_session: Optional[LeadSessionModel] = None


class ChatResponse(BaseModel):
    response:     str
    language:     str
    collect_lead: bool
    lead_stage:   str
    lead_session: dict
    sources:      list[dict] = []
    # TODO (Person 3): render source under each bot message in the React widget.
    # Format: "📄 Source: <source_file>" with an optional hyperlink when url is present.
    # lead_stage lets you optionally render a progress indicator during lead collection.

# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    logger.info("session=%s lang=%s msg=%r", req.session_id, req.language, req.message[:80])

    history = _get_history(req.session_id)

    # Reconstruct the LeadSession dataclass from the Pydantic model sent by the client
    ls: Optional[LeadSession] = (
        LeadSession(**req.lead_session.model_dump()) if req.lead_session else None
    )

    result = await run(
        query=req.message,
        chat_history=history,
        language=req.language,
        lead_session=ls,
        session_id=req.session_id,
    )

    _update_history(req.session_id, req.message, result["response"])

    # Log if the bot had no grounded answer (heuristic: response contains
    # "لا أعلم" / "I don't know" / "not in" — refine as needed)
    _no_answer_signals = ["لا أعلم", "لا تتوفر", "i don't know", "not in the context"]
    if any(s in result["response"].lower() for s in _no_answer_signals):
        log_unanswered(req.message, session_id=req.session_id)

    return ChatResponse(
        response=result["response"],
        language=result["language"],
        collect_lead=result["collect_lead"],
        lead_stage=result["lead_stage"],
        lead_session=result["lead_session"],
        sources=result.get("sources", []),
    )
