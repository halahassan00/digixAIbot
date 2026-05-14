"""
backend/tests/integration/test_lead_flow.py

Integration tests for the lead collection flow.

These tests run pipeline.run() end-to-end across multiple turns.
Google Sheets is mocked at the module boundary.
The RAG pipeline (ChromaDB + embedder) is also mocked here so these
tests run without requiring a populated ChromaDB index.

For tests against a *real* ChromaDB index, populate it first with:
    python -m backend.vectorstore.chroma_store
then run with: pytest backend/tests/integration/ -v --real-rag
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.leads.collector import LeadSession
from backend.rag.retriever import RetrievedChunk

# ---------------------------------------------------------------------------
# Shared fixtures
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

_RAG_ANSWER = "تقدم Digix AI حلول الذكاء الاصطناعي وبرامج التدريب.\n[CHUNK_ID: services_ar_chunk_0]"


def _patch_rag():
    """Context manager that patches retrieve + chat + language detect."""
    return (
        patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]),
        patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER),
        patch("backend.rag.pipeline.detect", return_value="ar"),
    )


# ---------------------------------------------------------------------------
# Test 1 — Full happy path: trigger → offer → name → contact → org → submit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_happy_path():
    """5-turn conversation from trigger to SUBMITTED. Sheets is mocked."""
    mock_submit = AsyncMock()

    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER), \
         patch("backend.rag.pipeline.detect", return_value="ar"), \
         patch("backend.rag.pipeline.submit_lead", mock_submit):

        from backend.rag.pipeline import run

        # Turn 1: user asks about registration — trigger fires
        result = await run(
            query="بدي أسجل في الكورس",
            language="ar",
            session_id="sess1",
        )
        assert result["lead_stage"] == "OFFERED"
        lead = LeadSession(**result["lead_session"])

        # Turn 2: user accepts
        result = await run(
            query="نعم",
            language="ar",
            lead_session=lead,
            session_id="sess1",
        )
        assert result["lead_stage"] == "COLLECTING_NAME"
        lead = LeadSession(**result["lead_session"])

        # Turn 3: user gives name
        result = await run(
            query="هالة حسن",
            language="ar",
            lead_session=lead,
            session_id="sess1",
        )
        assert result["lead_stage"] == "COLLECTING_CONTACT"
        lead = LeadSession(**result["lead_session"])

        # Turn 4: user gives email
        result = await run(
            query="hala@example.com",
            language="ar",
            lead_session=lead,
            session_id="sess1",
        )
        assert result["lead_stage"] == "COLLECTING_ORG"
        lead = LeadSession(**result["lead_session"])

        # Turn 5a: user gives org
        result = await run(
            query="شخصي",
            language="ar",
            lead_session=lead,
            session_id="sess1",
        )
        assert result["lead_stage"] == "CONFIRMING"
        lead = LeadSession(**result["lead_session"])

        # Turn 5b: user confirms
        result = await run(
            query="نعم",
            language="ar",
            lead_session=lead,
            session_id="sess1",
        )
        assert result["lead_stage"] == "SUBMITTED"
        mock_submit.assert_called_once()
        # Verify row data passed to submit_lead
        call_args = mock_submit.call_args
        submitted_lead = call_args[0][0]
        assert submitted_lead.name == "هالة حسن"
        assert submitted_lead.contact == "hala@example.com"


# ---------------------------------------------------------------------------
# Test 2 — Refusal path: trigger → offer → decline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refusal_path_no_sheets_call():
    mock_submit = AsyncMock()

    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER), \
         patch("backend.rag.pipeline.detect", return_value="ar"), \
         patch("backend.rag.pipeline.submit_lead", mock_submit):

        from backend.rag.pipeline import run

        result = await run(query="بدي أسجل", language="ar", session_id="sess2")
        lead = LeadSession(**result["lead_session"])
        assert result["lead_stage"] == "OFFERED"

        result = await run(query="لا", language="ar", lead_session=lead, session_id="sess2")
        assert result["lead_stage"] == "DECLINED"
        mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3 — Interruption: mid-collection question exits to IDLE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interruption_exits_collection_and_answers_rag():
    mock_submit = AsyncMock()

    with patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=_RAG_ANSWER), \
         patch("backend.rag.pipeline.detect", return_value="ar"), \
         patch("backend.rag.pipeline.submit_lead", mock_submit):

        from backend.rag.pipeline import run

        # Get to COLLECTING_NAME
        result = await run(query="بدي أسجل", language="ar", session_id="sess3")
        lead = LeadSession(**result["lead_session"])
        result = await run(query="نعم", language="ar", lead_session=lead, session_id="sess3")
        lead = LeadSession(**result["lead_session"])
        assert lead.stage == "COLLECTING_NAME"

        # Interrupt with a question
        result = await run(
            query="ما هي مدة كورس Power BI؟",
            language="ar",
            lead_session=lead,
            session_id="sess3",
        )
        assert result["lead_stage"] == "IDLE"
        # RAG answer should be present
        assert "Digix" in result["response"] or "تقدم" in result["response"]
        mock_submit.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4 — Mid-flow turn: RAG pipeline is NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mid_flow_skips_rag_pipeline():
    mock_rag_chat = MagicMock(return_value="should not appear")

    with patch("backend.rag.pipeline.chat", mock_rag_chat), \
         patch("backend.rag.pipeline.retrieve", return_value=[_DUMMY_CHUNK]), \
         patch("backend.rag.pipeline.submit_lead", AsyncMock()):

        from backend.rag.pipeline import run

        lead = LeadSession(
            stage="COLLECTING_NAME",
            language="ar",
            offered_this_session=True,
        )
        result = await run(
            query="هالة حسن",
            language="ar",
            lead_session=lead,
            session_id="sess4",
        )
        mock_rag_chat.assert_not_called()
        assert result["lead_stage"] == "COLLECTING_CONTACT"


# ---------------------------------------------------------------------------
# Test 5 — Google Sheets submission: correct column order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sheets_submission_column_order():
    """Mock at the _sync_submit level to verify exact column order."""
    captured_args = {}

    def _fake_sync_submit(name, contact, org, interest, language, session_id):
        captured_args.update(dict(
            name=name, contact=contact, org=org,
            interest=interest, language=language, session_id=session_id,
        ))

    with patch("backend.leads.google_sheets._sync_submit", side_effect=_fake_sync_submit):
        from backend.leads.google_sheets import submit_lead
        from backend.leads.collector import LeadSession as LS

        lead = LS(
            name="Test User",
            contact="test@test.com",
            org="ACME",
            interest="Power BI",
            language="en",
            stage="SUBMITTED",
        )
        await submit_lead(lead, session_id="sess-test")

    assert captured_args["name"]      == "Test User"
    assert captured_args["contact"]   == "test@test.com"
    assert captured_args["org"]       == "ACME"
    assert captured_args["interest"]  == "Power BI"
    assert captured_args["language"]  == "en"
    assert captured_args["session_id"] == "sess-test"
