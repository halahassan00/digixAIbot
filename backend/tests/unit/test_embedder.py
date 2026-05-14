"""
backend/tests/unit/test_embedder.py

Unit tests for backend/rag/embedder.py (GROUP 4, tests 23-27).
SentenceTransformer is mocked — the model is never loaded during unit tests.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import backend.rag.embedder as embedder_module
from backend.rag.embedder import embed_passages, embed_query, get_model


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Restore the module-level singleton after each test."""
    original = embedder_module._model
    embedder_module._model = None
    yield
    embedder_module._model = original


# ---------------------------------------------------------------------------
# Tests 23-24: prefix injection
# ---------------------------------------------------------------------------

def test_embed_passages_prepends_passage_prefix():
    """embed_passages prepends 'passage: ' to every text before encoding (test 23)."""
    captured = []

    def fake_encode(inputs, **kwargs):
        captured.extend(inputs)
        return np.array([[0.1, 0.2]] * len(inputs))

    mock = MagicMock()
    mock.encode.side_effect = fake_encode

    with patch("backend.rag.embedder.get_model", return_value=mock):
        embed_passages(["hello", "world"])

    assert all(t.startswith("passage: ") for t in captured)
    assert "passage: hello" in captured
    assert "passage: world" in captured


def test_embed_query_prepends_query_prefix():
    """embed_query prepends 'query: ' to the input text before encoding (test 24)."""
    captured = []

    def fake_encode(text, **kwargs):
        captured.append(text)
        return np.array([0.1, 0.2])

    mock = MagicMock()
    mock.encode.side_effect = fake_encode

    with patch("backend.rag.embedder.get_model", return_value=mock):
        embed_query("test query")

    assert captured[0] == "query: test query"


# ---------------------------------------------------------------------------
# Tests 25-26: return types
# ---------------------------------------------------------------------------

def test_embed_passages_returns_list_of_lists_of_floats():
    """embed_passages returns list[list[float]], not numpy arrays (test 25)."""
    mock = MagicMock()
    mock.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    with patch("backend.rag.embedder.get_model", return_value=mock):
        result = embed_passages(["text one", "text two"])

    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert isinstance(result[0][0], float)


def test_embed_query_returns_list_of_floats():
    """embed_query returns list[float], not a numpy array (test 26)."""
    mock = MagicMock()
    mock.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch("backend.rag.embedder.get_model", return_value=mock):
        result = embed_query("test")

    assert isinstance(result, list)
    assert isinstance(result[0], float)


# ---------------------------------------------------------------------------
# Test 27: singleton
# ---------------------------------------------------------------------------

def test_get_model_returns_same_object_on_repeated_calls():
    """get_model() is a singleton — SentenceTransformer is constructed only once (test 27)."""
    mock_instance = MagicMock()

    with patch("backend.rag.embedder.SentenceTransformer", return_value=mock_instance) as mock_cls:
        first = get_model()
        second = get_model()

    assert first is second
    mock_cls.assert_called_once()
