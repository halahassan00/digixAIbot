"""
knowledge_base/sync/sync.py

Full knowledge-base rebuild pipeline.

Run this whenever website content or PDFs change:
    python -m knowledge_base.sync.sync

What it does
------------
1. Re-scrape the DIGIX AI website.
   Hash-based change detection is handled inside scraper.py — pages whose
   extracted text has not changed since the last run are skipped.
2. Re-process any new or changed PDFs in knowledge_base/pdfs/.
   Hash-based change detection is handled inside pdf_processor.py.
3. Rebuild the full processed pipeline:
     raw/ → cleaner → chunker → metadata → chunks.json
4. Rebuild the ChromaDB vector index from the new chunks.json.

Steps 3–4 always run to completion even if nothing changed upstream,
so the index is always consistent with the raw files.

Hash store
----------
Both the scraper and pdf_processor record content hashes in one shared file:
    knowledge_base/sync/hash_store.json

Format:
    {
        "web": { "<url>": "<sha256>" },
        "pdf": { "<filename>": "<sha256>" }
    }

This file is gitignored. Delete it to force a full re-scrape and re-process.
"""

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sync")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT            = Path(__file__).resolve().parents[2]
HASH_STORE_PATH = Path(__file__).resolve().parent / "hash_store.json"

# ---------------------------------------------------------------------------
# Shared hash-store helpers
# ---------------------------------------------------------------------------

def _load_hash_store() -> dict:
    """Load the shared hash store, returning {"web": {}, "pdf": {}} if absent."""
    if HASH_STORE_PATH.exists():
        try:
            data = json.loads(HASH_STORE_PATH.read_text(encoding="utf-8"))
            data.setdefault("web", {})
            data.setdefault("pdf", {})
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"web": {}, "pdf": {}}


def _save_hash_store(store: dict) -> None:
    HASH_STORE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync() -> None:
    sys.path.insert(0, str(ROOT))   # ensure package root is importable

    store = _load_hash_store()

    # ------------------------------------------------------------------
    # Step 1: Re-scrape web pages
    # ------------------------------------------------------------------
    logger.info("Step 1/4: Scraping web pages...")
    try:
        from knowledge_base.scraper.scraper import scrape_all
        web_hashes = scrape_all(web_hash_store=store["web"])
        store["web"] = web_hashes
        _save_hash_store(store)
    except Exception as exc:
        logger.error("Web scrape failed: %s", exc)
        logger.warning("Continuing with existing raw files.")

    # ------------------------------------------------------------------
    # Step 2: Re-process PDFs
    # ------------------------------------------------------------------
    logger.info("Step 2/4: Processing PDFs...")
    from knowledge_base.processor.pdf_processor import process_all_pdfs
    pdf_hashes = process_all_pdfs(pdf_hash_store=store["pdf"])
    store["pdf"] = pdf_hashes
    _save_hash_store(store)

    # ------------------------------------------------------------------
    # Step 3: Rebuild processed pipeline (clean → chunk → metadata)
    # ------------------------------------------------------------------
    logger.info("Step 3/4: Rebuilding chunks.json...")
    from knowledge_base.processor import metadata as _metadata
    _metadata.run()

    # ------------------------------------------------------------------
    # Step 4: Rebuild ChromaDB index
    # ------------------------------------------------------------------
    logger.info("Step 4/4: Rebuilding ChromaDB index...")
    from backend.vectorstore.chroma_store import build_index
    build_index()

    logger.info("Sync complete.")


if __name__ == "__main__":
    sync()
