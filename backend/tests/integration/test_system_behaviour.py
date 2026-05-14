"""
backend/tests/integration/test_system_behaviour.py

GROUP 5: System behaviour — 4 tests.

Uses real ChromaDB + embedder (never mocked).
GPT-4o is mocked at the HTTP boundary via pytest-httpx.

Run with: pytest backend/tests/integration/test_system_behaviour.py -v
"""

import json
from pathlib import Path

import pytest

from backend.rag.retriever import retrieve

_EVAL_DATA = Path(__file__).parent.parent / "eval_data.jsonl"


def _openai_json(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
    }


# ---------------------------------------------------------------------------
# Hand-written query sets
# ---------------------------------------------------------------------------

_OUT_OF_SCOPE = [
    ("ما هو الطقس اليوم في عمان؟",          "ar"),
    ("من هو الرئيس الأمريكي الحالي؟",        "ar"),
    ("ما هو ثمن النفط الآن؟",               "ar"),
    ("كيف أطبخ المنسف الأردني؟",            "ar"),
    ("ما هي عاصمة فرنسا؟",                  "ar"),
    ("What is the speed of light?",          "en"),
    ("Who wrote Romeo and Juliet?",          "en"),
    ("What is the population of China?",     "en"),
    ("How tall is Mount Everest?",           "en"),
    ("What is the latest iPhone model?",     "en"),
]

_ARABIC_QUERIES = [
    "ما هي خدمات DIGIX AI؟",
    "شو البرامج التدريبية اللي بتقدمها الشركة؟",
    "كيف أتواصل مع فريق DIGIX AI؟",
    "ما هو برنامج Power BI؟",
    "شو هي شركة DIGIX AI؟",
    "ما هي شهادة IAIDL؟",
    "كيف يساعد الذكاء الاصطناعي الشركات؟",
    "ما هو برنامج البلوكتشين؟",
    "ما هي الدورات المتاحة؟",
    "ما أهمية الذكاء الاصطناعي في القطاع المالي؟",
]

_ENGLISH_QUERIES = [
    "What services does Digix AI offer?",
    "What training programs are available?",
    "How can I contact the Digix AI team?",
    "What is the Power BI course about?",
    "Tell me about Digix AI.",
    "What is the IAIDL certification?",
    "How does AI help businesses?",
    "What is blockchain training?",
    "What courses are available?",
    "What is the role of AI in financial services?",
]


# ---------------------------------------------------------------------------
# Test 25 — Refusal accuracy: out-of-scope queries return no factual claims
# ---------------------------------------------------------------------------

async def test_refusal_accuracy(httpx_mock):
    refusal = "ليس لدي معلومات حول هذا الموضوع. يرجى التواصل مع فريق Digix AI."
    for _ in _OUT_OF_SCOPE:
        httpx_mock.add_response(json=_openai_json(refusal))

    from backend.rag.pipeline import run

    for query, lang in _OUT_OF_SCOPE:
        result = await run(query=query, language=lang, session_id="refusal-test")
        assert result["collect_lead"] is False, (
            f"Unexpected lead trigger for out-of-scope query: {query!r}"
        )
        assert result["sources"] == [], (
            f"Unexpected sources for out-of-scope query: {query!r}"
        )


# ---------------------------------------------------------------------------
# Test 26 — Arabic queries auto-detected and routed as language="ar"
# ---------------------------------------------------------------------------

async def test_arabic_queries_return_arabic_language(httpx_mock):
    for _ in _ARABIC_QUERIES:
        httpx_mock.add_response(
            json=_openai_json("إجابة باللغة العربية.\n[CHUNK_ID: services_ar_chunk_0]")
        )

    from backend.rag.pipeline import run

    for query in _ARABIC_QUERIES:
        result = await run(query=query)  # language omitted — auto-detect
        assert result["language"] == "ar", (
            f"Expected language='ar', got {result['language']!r} for: {query!r}"
        )


# ---------------------------------------------------------------------------
# Test 27 — English queries auto-detected and routed as language="en"
# ---------------------------------------------------------------------------

async def test_english_queries_return_english_language(httpx_mock):
    for _ in _ENGLISH_QUERIES:
        httpx_mock.add_response(
            json=_openai_json("Answer in English.\n[CHUNK_ID: about_en_chunk_0]")
        )

    from backend.rag.pipeline import run

    for query in _ENGLISH_QUERIES:
        result = await run(query=query)  # language omitted — auto-detect
        assert result["language"] == "en", (
            f"Expected language='en', got {result['language']!r} for: {query!r}"
        )


# ---------------------------------------------------------------------------
# Test 28 — Source attribution rate >= 80% across eval_data.jsonl queries
#
# Strategy: pre-retrieve each query to get the real top chunk ID, then
# mock GPT-4o to cite that ID — tests the full attribution pipeline without
# relying on real GPT-4o responses.
# ---------------------------------------------------------------------------

async def test_source_attribution_rate(httpx_mock):
    if not _EVAL_DATA.exists():
        pytest.skip("eval_data.jsonl not found")

    data = [
        json.loads(line)
        for line in _EVAL_DATA.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Get the top chunk ID for each query so mock responses cite real IDs
    first_chunk_ids = []
    for entry in data:
        chunks = retrieve(query=entry["query"], language=entry["language"])
        first_chunk_ids.append(chunks[0].id if chunks else None)

    for chunk_id in first_chunk_ids:
        content = (
            f"الإجابة المناسبة.\n[CHUNK_ID: {chunk_id}]"
            if chunk_id
            else "لا أعرف."
        )
        httpx_mock.add_response(json=_openai_json(content))

    from backend.rag.pipeline import run

    attributed = 0
    for entry in data:
        result = await run(query=entry["query"], language=entry["language"])
        if result["sources"]:
            attributed += 1

    rate = attributed / len(data)
    assert rate >= 0.80, (
        f"Source attribution rate {rate:.1%} is below 80% "
        f"({attributed}/{len(data)} queries had sources)"
    )
