"""
backend/vectorstore/chroma_store.py

ChromaDB init, load, save, and index build.

Dependency order:
  embedder.py  ←  chroma_store.py  ←  retriever.py

This module imports embed_passages from embedder to build the index
offline (one-time).  retriever.py imports embed_query from embedder
for live requests.  The model is never loaded more than once because
embedder.py holds a singleton.

Run this file directly to build or rebuild the ChromaDB index:
    python -m backend.vectorstore.chroma_store

Supported metadata filters (ChromaDB `where` dicts):
  {"language": "ar"}
  {"language": "en"}
  {"category": "training"}
  {"$and": [{"language": "ar"}, {"category": "services"}]}
"""

import json
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from backend.rag.embedder import embed_passages

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).resolve().parents[2]
CHUNKS_JSON = ROOT / "knowledge_base" / "processed" / "chunks.json"
CHROMA_DIR  = Path(__file__).resolve().parent / "chroma_data"
COLLECTION_NAME = "digix_knowledge"

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def get_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client pointing at chroma_data/."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def get_collection(
    client: Optional[chromadb.PersistentClient] = None,
) -> chromadb.Collection:
    """
    Return (or create) the digix_knowledge collection.

    Embeddings are managed externally (see backend/rag/embedder.py),
    so embedding_function is left as None and we pass raw vectors on
    every upsert / query call.
    """
    if client is None:
        client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

# ---------------------------------------------------------------------------
# Save (upsert)
# ---------------------------------------------------------------------------

def save_chunks(
    collection: chromadb.Collection,
    ids: list[str],
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
    batch_size: int = 500,
) -> None:
    """
    Upsert pre-embedded chunks into the collection.

    Idempotent — re-upserting with the same id overwrites the existing
    document rather than creating a duplicate.

    Parameters
    ----------
    collection  : target ChromaDB collection
    ids         : unique chunk ids (e.g. "about_chunk_0")
    texts       : raw chunk text (stored as ChromaDB documents)
    embeddings  : vectors produced by backend/rag/embedder.py
    metadatas   : list of metadata dicts (language, category, url, …)
    batch_size  : max docs per ChromaDB call (keep ≤ 5000)
    """
    for start in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[start : start + batch_size],
            documents=texts[start : start + batch_size],
            embeddings=embeddings[start : start + batch_size],
            metadatas=metadatas[start : start + batch_size],
        )

# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query_chunks(
    collection: chromadb.Collection,
    query_embedding: list[float],
    n_results: int = 5,
    language: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    Retrieve the top-n closest chunks to a pre-computed query embedding.

    Parameters
    ----------
    collection      : the loaded collection
    query_embedding : vector produced by embedder.embed_query()
    n_results       : number of chunks to return
    language        : optional filter — "ar" or "en"
    category        : optional filter — e.g. "training", "services"

    Returns
    -------
    dict with keys: ids, documents, metadatas, distances
    """
    where: Optional[dict] = None
    if language and category:
        where = {"$and": [{"language": language}, {"category": category}]}
    elif language:
        where = {"language": language}
    elif category:
        where = {"category": category}

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

# ---------------------------------------------------------------------------
# Index builder (offline, one-time)
# ---------------------------------------------------------------------------

def build_index(chunks_path: Path = CHUNKS_JSON) -> None:
    """
    Load chunks.json → embed passages → upsert into ChromaDB.

    This is a one-time offline step, not part of the live server.
    Idempotent: re-running updates existing chunks, never duplicates them.

    Embedding is delegated to embedder.embed_passages() so that the same
    model instance is used here and in the live retriever — one model,
    one vector space.
    """
    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks from {chunks_path}")

    ids       = [c["id"] for c in chunks]
    texts     = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    print("Embedding chunks…")
    embeddings = embed_passages(texts)

    collection = get_collection()
    print("Upserting into collection 'digix_knowledge'…")
    save_chunks(collection, ids, texts, embeddings, metadatas)

    print(f"Done. Collection contains {collection.count()} documents.")


if __name__ == "__main__":
    build_index()
