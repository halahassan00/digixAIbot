"""
backend/tests/unit/test_chroma_store.py

Unit tests for backend/vectorstore/chroma_store.py (GROUP 5, tests 28-30).
Uses chromadb.EphemeralClient (in-memory) — no disk I/O, no external service.
"""

import json
from unittest.mock import patch

import chromadb
import pytest

from backend.vectorstore.chroma_store import build_index, get_collection, save_chunks


@pytest.fixture
def client():
    return chromadb.EphemeralClient()


# ---------------------------------------------------------------------------
# Test 28: cosine distance
# ---------------------------------------------------------------------------

def test_get_collection_uses_cosine_distance(client):
    """Collection metadata must specify hnsw:space = 'cosine' (test 28)."""
    collection = get_collection(client)
    assert collection.metadata.get("hnsw:space") == "cosine"


# ---------------------------------------------------------------------------
# Test 29: None URL coercion
# ---------------------------------------------------------------------------

def test_save_chunks_url_none_does_not_raise(client):
    """save_chunks coerces url=None to '' before upserting — must not raise (test 29)."""
    collection = get_collection(client)
    save_chunks(
        collection,
        ids=["chunk_0"],
        texts=["some text"],
        embeddings=[[0.1, 0.2, 0.3]],
        metadatas=[{"language": "ar", "url": None, "category": "training"}],
    )
    assert collection.count() == 1


# ---------------------------------------------------------------------------
# Test 30: count after build_index
# ---------------------------------------------------------------------------

def test_count_after_build_index_matches_chunks(tmp_path):
    """build_index upserts all chunks; collection.count() equals fixture size (test 30)."""
    chunks = [
        {
            "id": f"test_chunk_{i}",
            "text": f"chunk text {i}",
            "metadata": {"language": "ar", "url": "", "category": "test"},
        }
        for i in range(5)
    ]
    chunks_file = tmp_path / "chunks.json"
    chunks_file.write_text(json.dumps(chunks), encoding="utf-8")

    ephemeral = chromadb.EphemeralClient()
    # EphemeralClient instances share in-process state; wipe any collection
    # left behind by earlier tests before counting.
    try:
        ephemeral.delete_collection("digix_knowledge")
    except Exception:
        pass

    fake_embeddings = [[float(i) * 0.1 + 0.01, 0.2, 0.3] for i in range(5)]

    with patch("backend.vectorstore.chroma_store.embed_passages", return_value=fake_embeddings), \
         patch("backend.vectorstore.chroma_store.get_client", return_value=ephemeral):
        build_index(chunks_path=chunks_file)

    collection = get_collection(ephemeral)
    assert collection.count() == 5
