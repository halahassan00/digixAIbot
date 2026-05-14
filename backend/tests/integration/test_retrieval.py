"""
backend/tests/integration/test_retrieval.py

GROUP 1: Retrieval quality — 5 tests against the live ChromaDB index.

No mocking. ChromaDB and the embedder are real.
Run with: pytest backend/tests/integration/test_retrieval.py -v
"""

from backend.rag.retriever import retrieve


def test_arabic_query_returns_only_arabic_chunks():
    chunks = retrieve("ما هي خدمات DIGIX AI؟", language="ar")
    assert len(chunks) > 0
    assert all(c.language == "ar" for c in chunks)


def test_english_query_returns_only_english_chunks():
    chunks = retrieve("What is Power BI?", language="en")
    assert len(chunks) > 0
    assert all(c.language == "en" for c in chunks)


def test_training_query_returns_training_category():
    chunks = retrieve("Power BI training", language="ar")
    assert len(chunks) > 0
    assert any(c.category == "training" for c in chunks)


def test_all_scores_in_valid_range():
    chunks = retrieve("ما هي خدمات DIGIX AI؟", language="ar")
    assert len(chunks) > 0
    assert all(0 < c.score <= 1.0 for c in chunks)


def test_n_results_respected():
    chunks = retrieve("ما هي خدمات DIGIX AI؟", language="ar", n_results=4)
    assert 1 <= len(chunks) <= 4
