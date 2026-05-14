"""
backend/tests/unit/test_eval_retrieval.py

Unit tests for retrieval metric math (GROUP 11, tests 68-73).
No ChromaDB, no embeddings — pure arithmetic verification.
"""

import pytest

from backend.tests.eval_retrieval import compute_mrr, compute_recall_at_k

# Fixed ranked list used across all tests
_RETRIEVED = ["d1", "d2", "d3", "d4"]


# ---------------------------------------------------------------------------
# Tests 68-70: MRR per query
# ---------------------------------------------------------------------------

def test_mrr_rank_1_hit():
    """Relevant ID at rank 1 → MRR contribution = 1.0 (test 68)."""
    assert compute_mrr(["d1"], _RETRIEVED) == pytest.approx(1.0)


def test_mrr_rank_3_hit():
    """Relevant ID at rank 3 → MRR contribution = 1/3 (test 69)."""
    assert compute_mrr(["d3"], _RETRIEVED) == pytest.approx(1 / 3)


def test_mrr_no_hit():
    """Relevant ID absent → MRR contribution = 0.0 (test 70)."""
    assert compute_mrr(["d5"], _RETRIEVED) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test 71: mean MRR over three queries
# ---------------------------------------------------------------------------

def test_mean_mrr_over_three_queries():
    """Mean MRR over (hit@1, hit@3, miss) = (1 + 1/3 + 0) / 3 (test 71)."""
    mrrs = [
        compute_mrr(["d1"], _RETRIEVED),
        compute_mrr(["d3"], _RETRIEVED),
        compute_mrr(["d5"], _RETRIEVED),
    ]
    expected = (1.0 + 1 / 3 + 0.0) / 3
    assert sum(mrrs) / 3 == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Test 72: Recall@4
# ---------------------------------------------------------------------------

def test_recall_at_k_hit_in_top_4():
    """Relevant ID inside top-4 → Recall@4 = 1.0 (test 72a)."""
    assert compute_recall_at_k(["d4"], _RETRIEVED, k=4) == pytest.approx(1.0)


def test_recall_at_k_miss():
    """Relevant ID outside top-4 → Recall@4 = 0.0 (test 72b)."""
    assert compute_recall_at_k(["d5"], _RETRIEVED, k=4) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test 73: Precision@4
# ---------------------------------------------------------------------------

def test_precision_at_k_two_relevant_of_four():
    """2 relevant IDs in top-4 returned → Precision@4 = 0.5 (test 73)."""
    relevant = {"d1", "d3"}
    k = 4
    hits = len(relevant & set(_RETRIEVED[:k]))
    precision = hits / k
    assert precision == pytest.approx(0.5)
