"""
backend/tests/integration/test_eval_retrieval.py

GROUP 2: Retrieval metrics over eval_data.jsonl — 8 tests, all @pytest.mark.eval.

All tests share one session-scoped fixture that calls run_eval() once so
ChromaDB is queried a single time for all 8 assertions.

Run fast tests only (skip this file):
    pytest backend/tests/integration/ -v -m "not eval"

Run eval metrics:
    pytest backend/tests/integration/ -v -m eval
"""

import json

import pytest

from backend.tests.eval_retrieval import EVAL_DATA, EVAL_RESULTS, load_eval_data, run_eval

_RECALL_THRESHOLD    = 0.75   # 15/20 with source-diversity retrieval
_MRR_THRESHOLD       = 0.30   # 0.358 actual; low because home/about rank above specific pages
_PRECISION_THRESHOLD = 0.15   # 0.1875 actual; dedup diversifies but ground truth is strict
_RECALL_AR_THRESHOLD = 0.70   # 0.80 actual
_RECALL_EN_THRESHOLD = 0.65   # 0.70 actual; one colloquial training query stays a miss
_LATENCY_MS_LIMIT    = 2000.0 # cold-start model load (~14 s first call) raises the average


@pytest.fixture(scope="session")
def eval_report():
    if not EVAL_DATA.exists():
        pytest.skip("eval_data.jsonl not found — populate ChromaDB and curate the file first")
    data = load_eval_data()
    return run_eval(data)


@pytest.mark.eval
def test_recall_at_4_overall(eval_report):
    assert eval_report["recall_at_4"] >= _RECALL_THRESHOLD, (
        f"Recall@4 {eval_report['recall_at_4']:.4f} < {_RECALL_THRESHOLD}"
    )


@pytest.mark.eval
def test_mrr_overall(eval_report):
    assert eval_report["mrr"] >= _MRR_THRESHOLD, (
        f"MRR {eval_report['mrr']:.4f} < {_MRR_THRESHOLD}"
    )


@pytest.mark.eval
def test_precision_at_4_overall(eval_report):
    assert eval_report["precision_at_4"] >= _PRECISION_THRESHOLD, (
        f"Precision@4 {eval_report['precision_at_4']:.4f} < {_PRECISION_THRESHOLD}"
    )


@pytest.mark.eval
def test_arabic_recall_at_4(eval_report):
    ar = eval_report["by_language"].get("ar")
    if ar is None:
        pytest.skip("No Arabic queries in eval_data.jsonl")
    assert ar["recall_at_4"] >= _RECALL_AR_THRESHOLD, (
        f"Arabic Recall@4 {ar['recall_at_4']:.4f} < {_RECALL_AR_THRESHOLD}"
    )


@pytest.mark.eval
def test_english_recall_at_4(eval_report):
    en = eval_report["by_language"].get("en")
    if en is None:
        pytest.skip("No English queries in eval_data.jsonl")
    assert en["recall_at_4"] >= _RECALL_EN_THRESHOLD, (
        f"English Recall@4 {en['recall_at_4']:.4f} < {_RECALL_EN_THRESHOLD}"
    )


@pytest.mark.eval
def test_eval_results_saved_to_file(eval_report):
    assert EVAL_RESULTS.exists(), "eval_results.json was not written by run_eval()"
    with open(EVAL_RESULTS, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["recall_at_4"] == eval_report["recall_at_4"]
    assert "by_dialect" in saved, "by_dialect breakdown missing from eval_results.json"


@pytest.mark.eval
def test_per_query_breakdown_in_report(eval_report):
    rows = eval_report["per_query"]
    assert len(rows) > 0
    required = {"query", "language", "relevant_ids", "retrieved_ids",
                "recall_at_k", "mrr", "precision_at_k", "hit", "latency_ms"}
    for row in rows:
        missing = required - row.keys()
        assert not missing, f"Row missing keys: {missing}"


@pytest.mark.eval
def test_avg_retrieval_latency(eval_report):
    assert eval_report["avg_latency_ms"] < _LATENCY_MS_LIMIT, (
        f"Avg latency {eval_report['avg_latency_ms']:.1f}ms >= {_LATENCY_MS_LIMIT}ms"
    )
