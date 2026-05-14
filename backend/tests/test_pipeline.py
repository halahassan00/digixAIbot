"""
backend/tests/test_pipeline.py

Unit tests for Part A — source attribution in pipeline.py.

All tests mock out the LLM call (backend.llm.client.chat) and the
retriever (backend.rag.retriever.retrieve) so no real API keys or
ChromaDB index are required.

pipeline.run() is now async — tests use pytest.mark.asyncio.
"""

import logging
from unittest.mock import patch

import pytest

from backend.rag.retriever import RetrievedChunk

# A single realistic chunk returned by the mocked retriever
_ABOUT_CHUNK = RetrievedChunk(
    id="about_en_chunk_0",
    text="Since 2016, Digix AI has delivered AI training...",
    score=0.91,
    source="about_en.txt",
    category="company",
    language="en",
    url="https://digix-ai.com/about-us",
)

_SERVICES_CHUNK = RetrievedChunk(
    id="services_ar_chunk_0",
    text="تقدم Digix AI حلول الذكاء الاصطناعي للشركات...",
    score=0.88,
    source="services_ar.txt",
    category="services",
    language="ar",
    url="https://digix-ai.com/ar/services",
)


# ---------------------------------------------------------------------------
# Test 1 — GPT-4o returns a valid [CHUNK_ID] tag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sources_populated_when_tag_present():
    """sources contains exactly one entry matching the cited chunk."""
    mock_answer = "Digix AI has been delivering AI solutions since 2016.\n[CHUNK_ID: about_en_chunk_0]"

    with patch("backend.rag.pipeline.retrieve", return_value=[_ABOUT_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer):
        from backend.rag.pipeline import run
        result = await run(query="Tell me about Digix AI", language="en")

    assert result["sources"] == [
        {"source_file": "about_en.txt", "url": "https://digix-ai.com/about-us"}
    ]
    assert "[CHUNK_ID" not in result["response"]
    assert "Digix AI has been delivering" in result["response"]


# ---------------------------------------------------------------------------
# Test 2 — GPT-4o returns an answer with no [CHUNK_ID] tag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sources_empty_when_no_tag():
    """sources is [] and response text is unchanged when no tag is emitted."""
    mock_answer = "I don't know the answer to that question."

    with patch("backend.rag.pipeline.retrieve", return_value=[_ABOUT_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer):
        from backend.rag.pipeline import run
        result = await run(query="What is the moon made of?", language="en")

    assert result["sources"] == []
    assert result["response"] == mock_answer


# ---------------------------------------------------------------------------
# Test 3 — GPT-4o cites a chunk ID that is not in the retrieved set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sources_empty_and_warning_for_unknown_chunk_id(caplog):
    """Unknown chunk ID: no crash, sources == [], warning logged."""
    mock_answer = "Some grounded answer.\n[CHUNK_ID: nonexistent_id]"

    with patch("backend.rag.pipeline.retrieve", return_value=[_ABOUT_CHUNK]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer), \
         caplog.at_level(logging.WARNING, logger="backend.rag.pipeline"):
        from backend.rag.pipeline import run
        result = await run(query="Tell me about Digix AI", language="en")

    assert result["sources"] == []
    assert any("nonexistent_id" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Test 4 — Tag parser is tolerant of whitespace and quotes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tag_variant", [
    "[CHUNK_ID: about_en_chunk_0]",
    "[CHUNK_ID:  about_en_chunk_0  ]",
    '[CHUNK_ID: "about_en_chunk_0"]',
    "[chunk_id: about_en_chunk_0]",
])
def test_tag_parser_tolerant(tag_variant):
    """_parse_chunk_tag handles whitespace and quote variations."""
    from backend.rag.pipeline import _parse_chunk_tag

    answer = f"Some answer text.\n{tag_variant}"
    cleaned, chunk_id = _parse_chunk_tag(answer)

    assert chunk_id == "about_en_chunk_0"
    assert "[CHUNK_ID" not in cleaned.upper()
    assert cleaned.strip() == "Some answer text."


# ---------------------------------------------------------------------------
# Test 5 — PDF source (no URL) only emits source_file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sources_omits_url_for_pdf_chunks():
    """When the chunk has no URL (PDF source), sources entry has only source_file."""
    pdf_chunk = RetrievedChunk(
        id="training_pdf_chunk_3",
        text="Power BI course overview...",
        score=0.85,
        source="power_bi_training.pdf",
        category="training",
        language="ar",
        url="",   # PDFs have no URL
    )
    mock_answer = "Power BI course overview text.\n[CHUNK_ID: training_pdf_chunk_3]"

    with patch("backend.rag.pipeline.retrieve", return_value=[pdf_chunk]), \
         patch("backend.rag.pipeline.chat", return_value=mock_answer):
        from backend.rag.pipeline import run
        result = await run(query="ما هو كورس Power BI؟", language="ar")

    assert result["sources"] == [{"source_file": "power_bi_training.pdf"}]
    assert "url" not in result["sources"][0]
