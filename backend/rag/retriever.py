"""
backend/rag/retriever.py

Queries ChromaDB at runtime — called on every user message.

Dependency order:
  embedder.py  ←  chroma_store.py  ←  retriever.py
                  embedder.py      ↗

This module:
  1. Embeds the user query via embedder.embed_query()
  2. Searches ChromaDB via chroma_store.query_chunks()
  3. Returns a flat list of RetrievedChunk dicts for pipeline.py to consume

The ChromaDB collection is loaded once at module level and reused across
all requests — opening a PersistentClient on every request would be slow.
"""

from dataclasses import dataclass
from typing import Optional

from backend.rag.embedder import embed_query
from backend.vectorstore.chroma_store import get_collection, query_chunks

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    """A single chunk returned from ChromaDB, ready for the LLM prompt."""
    id:        str
    text:      str
    score:     float   # cosine similarity — higher is more relevant
    source:    str     # source_file, e.g. "services_ar.txt"
    category:  str     # e.g. "services", "training"
    language:  str     # "ar" or "en"
    url:       str

# ---------------------------------------------------------------------------
# Singleton collection
# ---------------------------------------------------------------------------

# Loaded once when this module is first imported; shared across all requests.
_collection = get_collection()

# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    language: Optional[str] = None,
    category: Optional[str] = None,
    n_results: int = 5,
) -> list[RetrievedChunk]:
    """
    Embed `query` and return the top-n most relevant chunks from ChromaDB.

    Parameters
    ----------
    query      : the user's message, in Arabic or English
    language   : pass "ar" or "en" to restrict results to one language.
                 None returns results from both languages.
    category   : optional category filter (e.g. "training", "services")
    n_results  : number of chunks to return (default 5)

    Returns
    -------
    List of RetrievedChunk, sorted by relevance (highest score first).
    """
    query_vector = embed_query(query)

    raw = query_chunks(
        collection=_collection,
        query_embedding=query_vector,
        n_results=n_results,
        language=language,
        category=category,
    )

    chunks: list[RetrievedChunk] = []
    for doc, meta, distance in zip(
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
    ):
        # ChromaDB returns cosine distance (0 = identical, 2 = opposite).
        # Convert to similarity so callers can treat higher = better.
        score = 1.0 - distance

        chunks.append(RetrievedChunk(
            id=meta.get("source_file", "") + f"_chunk_{meta.get('chunk_index', '')}",
            text=doc,
            score=score,
            source=meta.get("source_file", ""),
            category=meta.get("category", ""),
            language=meta.get("language", ""),
            url=meta.get("url", ""),
        ))

    return chunks
