"""
backend/tests/integration/test_pipeline.py

GROUP 3: Pipeline integration tests — 6 tests.

Uses real ChromaDB + embedder (never mocked).
GPT-4o is mocked at the HTTP boundary via pytest-httpx:
  POST https://api.openai.com/v1/chat/completions

Run with: pytest backend/tests/integration/test_pipeline.py -v
"""

import json
import time

import pytest

from backend.leads.collector import LeadSession


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
# Test 14 — basic schema + language field
# ---------------------------------------------------------------------------

async def test_arabic_query_returns_correct_schema(httpx_mock):
    httpx_mock.add_response(
        json=_openai_json(
            "تقدم Digix AI حلول الذكاء الاصطناعي.\n[CHUNK_ID: services_ar_chunk_0]"
        )
    )
    from backend.rag.pipeline import run

    result = await run(query="ما هي خدمات DIGIX AI؟", language="ar")

    required = {"response", "language", "collect_lead", "lead_stage", "lead_session", "sources"}
    assert required.issubset(result.keys())
    assert result["language"] == "ar"
    assert isinstance(result["collect_lead"], bool)
    assert isinstance(result["sources"], list)
    assert "[CHUNK_ID" not in result["response"].upper()


# ---------------------------------------------------------------------------
# Test 15 — pricing trigger fires lead offer
# ---------------------------------------------------------------------------

async def test_pricing_query_triggers_lead_collection(httpx_mock):
    httpx_mock.add_response(
        json=_openai_json(
            "سعر كورس Power BI يعتمد على البرنامج المختار.\n[CHUNK_ID: training_ar_chunk_0]"
        )
    )
    from backend.rag.pipeline import run

    result = await run(query="كم يكلف كورس Power BI؟", language="ar")

    assert result["collect_lead"] is True
    assert result["lead_stage"] == "OFFERED"


# ---------------------------------------------------------------------------
# Test 16 — [CHUNK_ID: none] cited by GPT-4o → sources empty
# ---------------------------------------------------------------------------

async def test_unknown_chunk_id_returns_empty_sources(httpx_mock):
    httpx_mock.add_response(
        json=_openai_json(
            "لا أعرف الإجابة على هذا السؤال.\n[CHUNK_ID: none]"
        )
    )
    from backend.rag.pipeline import run

    result = await run(query="ما هو اسم المدير التنفيذي؟", language="ar")

    assert result["sources"] == []


# ---------------------------------------------------------------------------
# Test 17 — chat_history appears in messages sent to the LLM
# ---------------------------------------------------------------------------

async def test_chat_history_included_in_llm_request(httpx_mock):
    httpx_mock.add_response(
        json=_openai_json(
            "الإجابة هنا.\n[CHUNK_ID: services_ar_chunk_0]"
        )
    )
    from backend.rag.pipeline import run

    history = [
        {"role": "user",      "content": "ما هي الدورات المتاحة؟"},
        {"role": "assistant", "content": "لدينا دورات في الذكاء الاصطناعي والبيانات."},
    ]
    await run(query="شو التفاصيل؟", language="ar", chat_history=history)

    request = httpx_mock.get_request()
    body = json.loads(request.content)
    message_contents = [m["content"] for m in body["messages"]]
    assert "ما هي الدورات المتاحة؟" in message_contents


# ---------------------------------------------------------------------------
# Test 18 — COLLECTING_NAME stage: collector handles turn, LLM not called
# ---------------------------------------------------------------------------

async def test_collecting_name_stage_skips_llm(httpx_mock):
    # No mock added — if pipeline fires an HTTP call, pytest-httpx raises immediately.
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
        session_id="t18",
    )

    assert len(httpx_mock.get_requests()) == 0
    assert result["lead_stage"] == "COLLECTING_CONTACT"


# ---------------------------------------------------------------------------
# Test 19 — p50 < 3s, p95 < 8s across 10 sequential queries (real ChromaDB,
#           instant mock GPT-4o response)
# ---------------------------------------------------------------------------

async def test_pipeline_latency_p50_p95(httpx_mock):
    queries = [
        ("ما هي خدمات DIGIX AI؟",              "ar"),
        ("شو البرامج التدريبية؟",               "ar"),
        ("What is Power BI?",                    "en"),
        ("كيف أتواصل مع الفريق؟",               "ar"),
        ("ما هي شهادة IAIDL؟",                  "ar"),
        ("What services does Digix AI offer?",   "en"),
        ("ما هو الذكاء الاصطناعي؟",             "ar"),
        ("شو هي شركة DIGIX AI؟",                "ar"),
        ("What is blockchain training?",         "en"),
        ("كيف يساعد الذكاء الاصطناعي الشركات؟", "ar"),
    ]
    for _ in queries:
        httpx_mock.add_response(
            json=_openai_json("إجابة سريعة.\n[CHUNK_ID: services_ar_chunk_0]")
        )

    from backend.rag.pipeline import run

    latencies = []
    for i, (q, lang) in enumerate(queries):
        t0 = time.perf_counter()
        await run(query=q, language=lang, session_id=f"lat-{i}")
        latencies.append(time.perf_counter() - t0)

    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2]
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]

    assert p50 < 3.0, f"p50 latency {p50:.3f}s exceeds 3s"
    assert p95 < 8.0, f"p95 latency {p95:.3f}s exceeds 8s"
