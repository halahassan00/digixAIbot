"""
backend/tests/unit/test_pipeline.py

GROUP 7 (tests 35-40): _should_collect_lead keyword matching
GROUP 8 (tests 41-43): [CHUNK_ID] tag parsing and source attribution
"""

import logging
from unittest.mock import patch

import pytest

from backend.rag.pipeline import _parse_chunk_tag, _should_collect_lead
from backend.rag.retriever import RetrievedChunk

# ---------------------------------------------------------------------------
# GROUP 7: Lead trigger keyword matching (tests 35-40)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query,lang,expected", [
    ("كم سعر الدورة؟",        "ar", True),   # 35 — "سعر" in triggers
    ("بدي أسجل",              "ar", True),   # 36 — "بدي أسجل" in triggers
    ("قديش",                  "ar", True),   # 37 — "قديش" in triggers
    ("what is Power BI?",     "en", False),  # 38 — no English trigger matched
    ("how much does it cost?","en", True),   # 39 — "how much" in triggers
    ("شرح لي BI",             "ar", False),  # 40 — no Arabic trigger matched
])
def test_should_collect_lead(query, lang, expected):
    assert _should_collect_lead(query, lang) is expected


# ---------------------------------------------------------------------------
# GROUP 8: Source attribution (tests 41-43)
# ---------------------------------------------------------------------------

_SERVICES_CHUNK = RetrievedChunk(
    id="services_ar_chunk_0",
    text="تقدم Digix AI حلول الذكاء الاصطناعي.",
    score=0.90,
    source="services_ar.txt",
    category="services",
    language="ar",
    url="https://digix-ai.com/ar/services",
)


@pytest.mark.asyncio
async def test_sources_populated_and_tag_stripped():
    """Tag present → response stripped of tag, sources populated (test 41)."""
    mock_answer = "answer text [CHUNK_ID: services_ar_chunk_0]"

    with patch("backend.rag.pipeline.retrieve", return_value=[_SERVICES_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer):
        from backend.rag.pipeline import run
        result = await run(query="ما هي خدمات Digix AI؟", language="ar")

    assert "answer text" in result["response"]
    assert "[CHUNK_ID" not in result["response"]
    assert result["sources"] == [
        {"source_file": "services_ar.txt", "url": "https://digix-ai.com/ar/services"}
    ]


@pytest.mark.asyncio
async def test_sources_empty_when_no_tag():
    """No tag → sources == [], response text unchanged (test 42)."""
    mock_answer = "I don't have that information."

    with patch("backend.rag.pipeline.retrieve", return_value=[_SERVICES_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer):
        from backend.rag.pipeline import run
        result = await run(query="unknown query", language="en")

    assert result["sources"] == []
    assert result["response"] == mock_answer


@pytest.mark.asyncio
async def test_sources_empty_and_warning_for_unknown_chunk_id(caplog):
    """Unknown chunk ID → sources == [], warning is logged (test 43)."""
    mock_answer = "Some answer.\n[CHUNK_ID: nonexistent_xyz]"

    with patch("backend.rag.pipeline.retrieve", return_value=[_SERVICES_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer), \
         caplog.at_level(logging.WARNING, logger="backend.rag.pipeline"):
        from backend.rag.pipeline import run
        result = await run(query="test", language="ar")

    assert result["sources"] == []
    assert any("nonexistent_xyz" in r.message for r in caplog.records)
