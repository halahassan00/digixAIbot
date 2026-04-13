"""
backend/api/routes/chat.py

POST /chat — the main chatbot endpoint.

API contract (from CONTEXT.md — do not change without team discussion):
  Request:  { "message": "ما هي خدماتكم؟", "session_id": "abc123", "language": "ar" }
  Response: { "response": "...", "language": "ar", "collect_lead": false }

Session history
---------------
Conversation history is stored in memory keyed by session_id.  This is
sufficient for a dev/demo deployment.  Each session keeps the last
MAX_HISTORY_TURNS turns to bound the context window sent to GPT-4o.
"""

from collections import OrderedDict

from fastapi import APIRouter
from pydantic import BaseModel, Field

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

class ChatRequest(BaseModel):
    message:    str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1, max_length=64)
    language:   str = Field("ar", pattern="^(ar|en)$")


class ChatResponse(BaseModel):
    response:     str
    language:     str
    collect_lead: bool

# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    logger.info("session=%s lang=%s msg=%r", req.session_id, req.language, req.message[:80])

    history = _get_history(req.session_id)

    result = run(
        query=req.message,
        chat_history=history,
        language=req.language,
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
    )
