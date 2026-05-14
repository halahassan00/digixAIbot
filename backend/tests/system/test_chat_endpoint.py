"""
backend/tests/system/test_chat_endpoint.py

System tests for POST /chat via FastAPI TestClient.

The RAG pipeline (LLM + ChromaDB) and Google Sheets are mocked at the
module boundary. These tests verify the HTTP contract and session-state
threading through the API layer.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.rag.retriever import RetrievedChunk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DUMMY_CHUNK = RetrievedChunk(
    id="services_ar_chunk_0",
    text="تقدم Digix AI حلول الذكاء الاصطناعي.",
    score=0.9,
    source="services_ar.txt",
    category="services",
    language="ar",
    url="https://digix-ai.com/ar/services",
)

_RAG_ANSWER_AR = "تقدم Digix AI حلول متعددة.\n[CHUNK_ID: services_ar_chunk_0]"


def _async_client():
    """Return an async HTTPX client wired to the FastAPI app via ASGI transport."""
    from backend.main import app
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Test 1 — Pricing query returns collect_lead=True and lead_stage=OFFERED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pricing_query_triggers_offer():
    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER_AR), \
         patch("backend.rag.pipeline.detect", return_value="ar"):

        async with _async_client() as client:
            resp = await client.post("/chat", json={
                "message": "كم سعر كورس Power BI؟",
                "session_id": "sys-test-1",
                "language": "ar",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["collect_lead"] is True
    assert data["lead_stage"] == "OFFERED"
    assert "lead_session" in data
    assert data["lead_session"]["stage"] == "OFFERED"


# ---------------------------------------------------------------------------
# Test 2 — Acceptance transitions to COLLECTING_NAME
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acceptance_transitions_to_collecting_name():
    offered_session = {
        "stage": "OFFERED",
        "name": "",
        "contact": "",
        "org": "",
        "interest": "Power BI",
        "language": "ar",
        "offered_this_session": True,
        "contact_attempts": 0,
    }

    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER_AR), \
         patch("backend.rag.pipeline.detect", return_value="ar"):

        async with _async_client() as client:
            resp = await client.post("/chat", json={
                "message": "نعم",
                "session_id": "sys-test-2",
                "language": "ar",
                "lead_session": offered_session,
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["lead_stage"] == "COLLECTING_NAME"
    assert data["lead_session"]["stage"] == "COLLECTING_NAME"


# ---------------------------------------------------------------------------
# Test 3 — First turn with no lead_session does not crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_turn_no_lead_session_ok():
    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER_AR), \
         patch("backend.rag.pipeline.detect", return_value="ar"):

        async with _async_client() as client:
            resp = await client.post("/chat", json={
                "message": "ما هي خدمات الشركة؟",
                "session_id": "sys-test-3",
                "language": "ar",
                # no lead_session field
            })

    assert resp.status_code == 200
    data = resp.json()
    assert "lead_stage" in data
    assert "lead_session" in data


# ---------------------------------------------------------------------------
# Test 4 — Full 5-turn happy path through the HTTP endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_5_turn_http_path():
    mock_submit = AsyncMock()

    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER_AR), \
         patch("backend.rag.pipeline.detect", return_value="ar"), \
         patch("backend.rag.pipeline.submit_lead", mock_submit):

        async with _async_client() as client:

            # Turn 1: trigger
            r = await client.post("/chat", json={
                "message": "بدي أسجل في كورس Power BI",
                "session_id": "sys-5turn",
                "language": "ar",
            })
            assert r.json()["lead_stage"] == "OFFERED"
            ls = r.json()["lead_session"]

            # Turn 2: accept
            r = await client.post("/chat", json={
                "message": "نعم", "session_id": "sys-5turn",
                "language": "ar", "lead_session": ls,
            })
            assert r.json()["lead_stage"] == "COLLECTING_NAME"
            ls = r.json()["lead_session"]

            # Turn 3: name
            r = await client.post("/chat", json={
                "message": "هالة حسن", "session_id": "sys-5turn",
                "language": "ar", "lead_session": ls,
            })
            assert r.json()["lead_stage"] == "COLLECTING_CONTACT"
            ls = r.json()["lead_session"]

            # Turn 4: contact
            r = await client.post("/chat", json={
                "message": "hala@digix.com", "session_id": "sys-5turn",
                "language": "ar", "lead_session": ls,
            })
            assert r.json()["lead_stage"] == "COLLECTING_ORG"
            ls = r.json()["lead_session"]

            # Turn 5a: org
            r = await client.post("/chat", json={
                "message": "شخصي", "session_id": "sys-5turn",
                "language": "ar", "lead_session": ls,
            })
            assert r.json()["lead_stage"] == "CONFIRMING"
            ls = r.json()["lead_session"]

            # Turn 5b: confirm
            r = await client.post("/chat", json={
                "message": "نعم", "session_id": "sys-5turn",
                "language": "ar", "lead_session": ls,
            })
            assert r.json()["lead_stage"] == "SUBMITTED"
            mock_submit.assert_called_once()


# ===========================================================================
# Tests 5–11 — HTTP-boundary mocking via pytest-httpx + FastAPI TestClient
#
# These tests use real ChromaDB retrieval and the real retriever/embedder.
# Only outbound HTTP calls (OpenAI, Google Sheets) are intercepted.
# Existing tests 1–4 above mock at the module boundary and are kept as-is.
# ===========================================================================

import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _oai_envelope(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


_AR = "تقدم Digix AI حلول الذكاء الاصطناعي المتعددة.\n[CHUNK_ID: services_ar_chunk_0]"
_EN = "Power BI is a business analytics tool by Microsoft.\n[CHUNK_ID: services_chunk_0]"


def _tc():
    from backend.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 5 — Basic Arabic query: response schema and language field
# ---------------------------------------------------------------------------

def test_basic_arabic_query(mock_openai_ar):
    r = _tc().post("/chat", json={
        "message": "ما هي خدمات DIGIX AI؟",
        "session_id": "sys-ar-1",
        "language": "ar",
    })
    assert r.status_code == 200
    data = r.json()
    assert {"response", "language", "collect_lead", "lead_stage", "sources"} <= set(data)
    assert data["language"] == "ar"
    assert isinstance(data["response"], str) and data["response"]


# ---------------------------------------------------------------------------
# Test 6 — Basic English query: language propagated correctly
# ---------------------------------------------------------------------------

def test_basic_english_query(mock_openai_en):
    r = _tc().post("/chat", json={
        "message": "What is Power BI?",
        "session_id": "sys-en-1",
        "language": "en",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["language"] == "en"
    assert isinstance(data["response"], str) and data["response"]


# ---------------------------------------------------------------------------
# Test 7 — Full 6-turn lead collection via HTTP endpoint
#
# lead_session is extracted from each response and passed back verbatim in
# the next request (backend is stateless — the frontend owns that dict).
#
# OpenAI is called exactly once (Turn 1, IDLE → full RAG path).
# Turns 2–6 are mid-flow: the collector owns them; RAG is skipped entirely.
# Google Sheets _sync_submit is patched to prevent real network calls.
# ---------------------------------------------------------------------------

def test_http_full_lead_flow(httpx_mock):
    httpx_mock.add_response(url=_OPENAI_URL, method="POST", json=_oai_envelope(_AR))
    mock_submit = MagicMock()

    with patch("backend.leads.google_sheets._sync_submit", mock_submit):
        c = _tc()

        # Turn 1: pricing trigger → OFFERED
        r = c.post("/chat", json={
            "message": "كم سعر دورة Power BI؟",
            "session_id": "sys-lead-full",
            "language": "ar",
        })
        assert r.status_code == 200
        assert r.json()["lead_stage"] == "OFFERED"
        ls = r.json()["lead_session"]

        # Turn 2: acceptance → COLLECTING_NAME
        r = c.post("/chat", json={
            "message": "نعم",
            "session_id": "sys-lead-full",
            "language": "ar",
            "lead_session": ls,
        })
        assert r.status_code == 200
        assert r.json()["lead_stage"] == "COLLECTING_NAME"
        ls = r.json()["lead_session"]

        # Turn 3: name → COLLECTING_CONTACT
        r = c.post("/chat", json={
            "message": "أحمد محمد",
            "session_id": "sys-lead-full",
            "language": "ar",
            "lead_session": ls,
        })
        assert r.status_code == 200
        assert r.json()["lead_stage"] == "COLLECTING_CONTACT"
        ls = r.json()["lead_session"]

        # Turn 4: contact → COLLECTING_ORG
        r = c.post("/chat", json={
            "message": "ahmed@example.com",
            "session_id": "sys-lead-full",
            "language": "ar",
            "lead_session": ls,
        })
        assert r.status_code == 200
        assert r.json()["lead_stage"] == "COLLECTING_ORG"
        ls = r.json()["lead_session"]

        # Turn 5: org → CONFIRMING
        r = c.post("/chat", json={
            "message": "شركة ديناراك",
            "session_id": "sys-lead-full",
            "language": "ar",
            "lead_session": ls,
        })
        assert r.status_code == 200
        assert r.json()["lead_stage"] == "CONFIRMING"
        ls = r.json()["lead_session"]

        # Turn 6: confirm → SUBMITTED; Sheets mock must be called exactly once
        r = c.post("/chat", json={
            "message": "نعم",
            "session_id": "sys-lead-full",
            "language": "ar",
            "lead_session": ls,
        })
        assert r.status_code == 200
        assert r.json()["lead_stage"] == "SUBMITTED"

    mock_submit.assert_called_once()


# ---------------------------------------------------------------------------
# Test 8 — Out-of-scope query: no lead offered, sources empty
#
# Uses "من هو رئيس الأردن؟" which has no lead-trigger keyword, so the
# pipeline will not append an offer regardless of the GPT-4o response.
# ---------------------------------------------------------------------------

def test_out_of_scope_no_lead(mock_openai_refusal):
    r = _tc().post("/chat", json={
        "message": "من هو رئيس الأردن؟",
        "session_id": "sys-oos-1",
        "language": "ar",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["collect_lead"] is False
    assert isinstance(data["sources"], list)


# ---------------------------------------------------------------------------
# Test 9 — Language auto-detection (no language field in request)
#
# ChatRequest.language defaults to "ar" per the Pydantic model definition.
# The pipeline receives "ar" and passes it through to the response.
# ---------------------------------------------------------------------------

def test_language_autodetection(mock_openai_ar):
    r = _tc().post("/chat", json={
        "message": "ما هي خدمات الشركة؟",
        "session_id": "sys-lang-1",
        # language intentionally omitted — Pydantic defaults to "ar"
    })
    assert r.status_code == 200
    assert r.json()["language"] == "ar"


# ---------------------------------------------------------------------------
# Test 10 — Source attribution schema is always a list; entries have source_file
#
# The mocked GPT-4o response cites services_ar_chunk_0. If ChromaDB is
# populated and that chunk is in the top-4 results, sources will be non-empty.
# The test validates the schema in either case.
# ---------------------------------------------------------------------------

def test_source_attribution_schema(mock_openai_ar):
    r = _tc().post("/chat", json={
        "message": "ما هي دورة Power BI؟",
        "session_id": "sys-src-1",
        "language": "ar",
    })
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["sources"], list)
    for src in data["sources"]:
        assert "source_file" in src


# ---------------------------------------------------------------------------
# Test 11 — Response latency: 20 sequential requests complete in < 60 s
# ---------------------------------------------------------------------------

def test_response_latency(httpx_mock):
    for _ in range(20):
        httpx_mock.add_response(
            url=_OPENAI_URL, method="POST", json=_oai_envelope(_AR)
        )
    c = _tc()
    start = time.time()
    for i in range(20):
        r = c.post("/chat", json={
            "message": "ما هي خدمات DIGIX AI؟",
            "session_id": f"lat-{i}",
            "language": "ar",
        })
        assert r.status_code == 200
    assert time.time() - start < 60
