"""
backend/rag/embedder.py

Owns the multilingual-e5-large model and is the single place it lives.

Two consumers:
  - chroma_store.py  calls embed_passages() once, offline, to build the index
  - retriever.py     calls embed_query()    on every live request

Both use the same model so passages and queries share a vector space.
The model is loaded lazily on first call and cached in _model for the
lifetime of the process — never loaded twice.

multilingual-e5 requires task prefixes:
  - stored passages  → "passage: <text>"
  - user queries     → "query: <text>"
Omitting the prefix silently degrades retrieval quality.
"""

from pathlib import Path
from typing import Optional

from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_NAME     = "intfloat/multilingual-e5-large"
QUERY_PREFIX   = "query: "
PASSAGE_PREFIX = "passage: "
BATCH_SIZE     = 32   # chunks per encode call — reduce if GPU OOM

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """
    Return the singleton embedding model, loading it on first call.

    The model is downloaded from HuggingFace on the first run (~1.2 GB)
    and cached locally afterwards.
    """
    global _model
    if _model is None:
        print(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_passages(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of passage strings for storage in ChromaDB.

    Applies the "passage: " prefix required by multilingual-e5.
    """
    model = get_model()
    prefixed = [PASSAGE_PREFIX + t for t in texts]
    vectors = model.encode(
        prefixed,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """
    Embed a single user query for similarity search.

    Applies the "query: " prefix required by multilingual-e5.
    """
    model = get_model()
    vector = model.encode(
        QUERY_PREFIX + text,
        normalize_embeddings=True,
    )
    return vector.tolist()

