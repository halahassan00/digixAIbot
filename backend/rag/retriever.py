"""
backend/rag/retriever.py

Queries ChromaDB at runtime and is called on every user message.

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

_CANDIDATE_MULTIPLIER = 3

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

def _source_diverse(chunks: list[RetrievedChunk], n: int) -> list[RetrievedChunk]:
    """
    Return up to n chunks keeping at most one chunk per source file.

    Home and about pages are generic enough to score highly for almost any
    DIGIX AI query, which would crowd out specific pages (services, training,
    impact) in the top-4 window.  By fetching _CANDIDATE_MULTIPLIER × n
    candidates and de-duplicating on source_file, we ensure that a single
    page can claim at most one slot, giving specific pages a fair chance.
    """
    seen: set[str] = set()
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        if chunk.source not in seen:
            seen.add(chunk.source)
            result.append(chunk)
        if len(result) >= n:
            break
    return result


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

    # Fetch more candidates than needed so source-diversity filtering has
    # enough material to fill n_results slots from distinct pages.
    n_candidates = n_results * _CANDIDATE_MULTIPLIER

    raw = query_chunks(
        collection=_collection,
        query_embedding=query_vector,
        n_results=n_candidates,
        language=language,
        category=category,
    )

    chunks: list[RetrievedChunk] = []
    for doc, meta, distance, chunk_id in zip(
        raw["documents"][0],
        raw["metadatas"][0],
        raw["distances"][0],
        raw["ids"][0],
    ):
        # ChromaDB returns cosine distance (0 = identical, 2 = opposite).
        # Convert to similarity so callers can treat higher = better.
        score = 1.0 - distance

        chunks.append(RetrievedChunk(
            id=chunk_id,
            text=doc,
            score=score,
            source=meta.get("source_file", ""),
            category=meta.get("category", ""),
            language=meta.get("language", ""),
            url=meta.get("url", ""),
        ))

    return _source_diverse(chunks, n_results)
