"""
backend/tests/eval_retrieval.py

Retrieval evaluation harness — measures Recall@4 and MRR against a
hand-curated test set stored in eval_data.jsonl.

Metrics match the family used in Arabic-RAG literature (Akkiraju et al., 2024),
enabling direct citation of these numbers in Chapter 5 of the report.

Usage
-----
  # Run as a script (prints table + saves eval_results.json):
  python -m backend.tests.eval_retrieval

  # Run as pytest (asserts mean Recall@4 >= RECALL_THRESHOLD):
  pytest backend/tests/eval_retrieval.py -v

  # Run unit test for metric math only (no ChromaDB needed):
  pytest backend/tests/eval_retrieval.py::test_metric_math -v

What this module does NOT do
----------------------------
- Does not measure answer faithfulness or end-to-end response quality.
- Does not call GPT-4o. Pure retrieval evaluation only.
"""

import json
import sys
import time
import warnings
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths & thresholds
# ---------------------------------------------------------------------------

EVAL_DATA    = Path(__file__).parent / "eval_data.jsonl"
EVAL_RESULTS = Path(__file__).parent / "eval_results.json"

RECALL_THRESHOLD = 0.7   # pytest fails the integration test if mean Recall@4 < this
MIN_EVAL_QUERIES = 20    # warn if the file has fewer entries

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def compute_recall_at_k(
    relevant_ids: list[str],
    retrieved_ids: list[str],
    k: int = 4,
) -> float:
    """Return 1.0 if any relevant ID appears in the top-k retrieved IDs, else 0.0."""
    top_k = set(retrieved_ids[:k])
    return 1.0 if top_k & set(relevant_ids) else 0.0


def compute_mrr(
    relevant_ids: list[str],
    retrieved_ids: list[str],
) -> float:
    """Return 1/rank of the first relevant chunk found; 0.0 if none found."""
    relevant_set = set(relevant_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_set:
            return 1.0 / rank
    return 0.0


def compute_precision_at_k(
    relevant_ids: list[str],
    retrieved_ids: list[str],
    k: int = 4,
) -> float:
    """Return the fraction of top-k retrieved chunks that are relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    return sum(1 for rid in top_k if rid in set(relevant_ids)) / len(top_k)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_eval_data(path: Path = EVAL_DATA) -> list[dict]:
    """Load eval_data.jsonl; warn if fewer than MIN_EVAL_QUERIES entries."""
    if not path.exists():
        raise FileNotFoundError(
            f"Eval data file not found: {path}\n"
            "Create it by hand-curating queries after populating ChromaDB."
        )
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if len(entries) < MIN_EVAL_QUERIES:
        warnings.warn(
            f"eval_data.jsonl has only {len(entries)} queries "
            f"(minimum recommended: {MIN_EVAL_QUERIES}). "
            "Results may not be statistically representative.",
            UserWarning,
            stacklevel=2,
        )
    return entries

# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def run_eval(eval_data: list[dict], top_k: int = 4) -> dict:
    """
    Run retrieval evaluation over eval_data.

    For each query: retrieve top_k via the production retrieve() function
    (which applies source-diversity filtering) → compute Recall@4 and MRR.
    Print per-query results and an aggregate table; save eval_results.json.

    Returns the aggregate results dict.
    """
    from backend.rag.retriever import retrieve

    rows = []
    latencies = []

    print(f"\n{'='*80}")
    print(f"  DIGIX AI Retrieval Evaluation  |  top_k={top_k}  |  queries={len(eval_data)}")
    print(f"{'='*80}\n")
    print(f"{'#':<4} {'Lang':<5} {'Dialect':<12} {'Recall@4':<10} {'MRR':<8} {'P@4':<8} {'Hit?':<6}  Query")
    print("-" * 90)

    for i, entry in enumerate(eval_data, start=1):
        query: str        = entry["query"]
        language: str     = entry["language"]
        dialect: str      = entry.get("dialect", "unknown")
        relevant: list    = entry["relevant_chunk_ids"]

        t0 = time.perf_counter()
        chunks = retrieve(query=query, language=language, n_results=top_k)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

        retrieved_ids: list[str] = [c.id for c in chunks]

        recall    = compute_recall_at_k(relevant, retrieved_ids, k=top_k)
        mrr       = compute_mrr(relevant, retrieved_ids)
        precision = compute_precision_at_k(relevant, retrieved_ids, k=top_k)
        hit       = recall > 0.0

        rows.append({
            "query":          query,
            "language":       language,
            "dialect":        dialect,
            "relevant_ids":   relevant,
            "retrieved_ids":  retrieved_ids,
            "recall_at_k":    recall,
            "mrr":            mrr,
            "precision_at_k": precision,
            "hit":            hit,
            "latency_ms":     round(latency_ms, 1),
        })

        query_preview = query[:50] + "…" if len(query) > 50 else query
        print(
            f"{i:<4} {language:<5} {dialect:<12} {recall:<10.1f} {mrr:<8.3f} "
            f"{precision:<8.3f} {'✓' if hit else '✗':<6}  {query_preview}"
        )

    # -------------------------------------------------------------------------
    # Aggregate stats
    # -------------------------------------------------------------------------
    ar_rows = [r for r in rows if r["language"] == "ar"]
    en_rows = [r for r in rows if r["language"] == "en"]

    def _agg(subset: list[dict]) -> Optional[dict]:
        if not subset:
            return None
        n = len(subset)
        return {
            "count":          n,
            "recall_at_4":    round(sum(r["recall_at_k"]    for r in subset) / n, 4),
            "mrr":            round(sum(r["mrr"]            for r in subset) / n, 4),
            "precision_at_4": round(sum(r["precision_at_k"] for r in subset) / n, 4),
        }

    overall = _agg(rows)
    by_language = {
        "ar": _agg(ar_rows),
        "en": _agg(en_rows),
    }

    # Dialect breakdown (fusha / colloquial / en)
    dialects = sorted({r["dialect"] for r in rows})
    by_dialect = {
        d: _agg([r for r in rows if r["dialect"] == d])
        for d in dialects
    }

    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    print("\n" + "=" * 90)
    print("  Results Summary")
    print("=" * 90)
    print(
        f"  Overall   — Recall@{top_k}: {overall['recall_at_4']:.4f}  |  "
        f"MRR: {overall['mrr']:.4f}  |  P@{top_k}: {overall['precision_at_4']:.4f}  |  "
        f"n={overall['count']}"
    )
    if by_language.get("ar"):
        ar = by_language["ar"]
        print(
            f"  Arabic    — Recall@{top_k}: {ar['recall_at_4']:.4f}  |  "
            f"MRR: {ar['mrr']:.4f}  |  P@{top_k}: {ar['precision_at_4']:.4f}  |  "
            f"n={ar['count']}"
        )
    if by_language.get("en"):
        en = by_language["en"]
        print(
            f"  English   — Recall@{top_k}: {en['recall_at_4']:.4f}  |  "
            f"MRR: {en['mrr']:.4f}  |  P@{top_k}: {en['precision_at_4']:.4f}  |  "
            f"n={en['count']}"
        )
    print()
    for dialect, stats in by_dialect.items():
        if stats:
            print(
                f"  [{dialect:<11}] Recall@{top_k}: {stats['recall_at_4']:.4f}  |  "
                f"MRR: {stats['mrr']:.4f}  |  P@{top_k}: {stats['precision_at_4']:.4f}  |  "
                f"n={stats['count']}"
            )
    print(f"\n  Avg retrieval latency: {avg_latency_ms} ms")
    print("=" * 90 + "\n")

    report = {
        "top_k":           top_k,
        "total_queries":   len(rows),
        "recall_at_4":     overall["recall_at_4"],
        "mrr":             overall["mrr"],
        "precision_at_4":  overall["precision_at_4"],
        "avg_latency_ms":  avg_latency_ms,
        "by_language":     by_language,
        "by_dialect":      by_dialect,
        "per_query":       rows,
    }

    with open(EVAL_RESULTS, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved → {EVAL_RESULTS}\n")

    return report


# ---------------------------------------------------------------------------
# Entry point (script mode)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    data = load_eval_data()
    run_eval(data)


# ---------------------------------------------------------------------------
# pytest tests
# ---------------------------------------------------------------------------

def test_metric_math():
    """
    Unit test for Recall@4 and MRR math using a tiny synthetic dataset.

    Three queries against a fixed ranked list:
      Q1 — relevant ID at rank 1  → MRR=1,   Recall=1
      Q2 — relevant ID at rank 3  → MRR=1/3, Recall=1
      Q3 — relevant ID absent     → MRR=0,   Recall=0

    Expected mean MRR    = (1 + 1/3 + 0) / 3
    Expected mean Recall = (1 + 1 + 0)   / 3
    """
    retrieved = ["d1", "d2", "d3", "d4"]   # fixed top-4 for all queries

    cases = [
        (["d1"], retrieved),   # rank-1 hit
        (["d3"], retrieved),   # rank-3 hit
        (["d5"], retrieved),   # miss (d5 not in top-4)
    ]

    recalls = [compute_recall_at_k(rel, ret, k=4) for rel, ret in cases]
    mrrs    = [compute_mrr(rel, ret)               for rel, ret in cases]

    expected_recall = (1.0 + 1.0 + 0.0) / 3
    expected_mrr    = (1.0 + 1.0 / 3 + 0.0) / 3

    assert abs(sum(recalls) / 3 - expected_recall) < 1e-9
    assert abs(sum(mrrs)    / 3 - expected_mrr)    < 1e-9

    # Spot-check individual values
    assert recalls[0] == 1.0
    assert recalls[2] == 0.0
    assert abs(mrrs[0] - 1.0)       < 1e-9
    assert abs(mrrs[1] - 1.0 / 3)   < 1e-9
    assert mrrs[2] == 0.0


def test_retrieval_quality():
    """
    Integration test: run the full eval against the live ChromaDB index.

    Requires:
      - ChromaDB index populated via: python -m backend.vectorstore.chroma_store
      - eval_data.jsonl curated with real chunk IDs

    Asserts mean Recall@4 >= RECALL_THRESHOLD (default 0.7).
    Skip this test if eval_data.jsonl does not exist yet.
    """
    import pytest

    if not EVAL_DATA.exists():
        pytest.skip("eval_data.jsonl not found — populate ChromaDB and curate the file first")

    data = load_eval_data()
    report = run_eval(data)

    assert report["recall_at_4"] >= RECALL_THRESHOLD, (
        f"Recall@4 {report['recall_at_4']:.4f} is below threshold {RECALL_THRESHOLD}. "
        "Check embeddings, chunking, or metadata filtering."
    )
