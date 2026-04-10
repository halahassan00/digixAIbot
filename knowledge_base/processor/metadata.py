"""
metadata.py — full pipeline: raw → clean → chunk → enrich with metadata → JSON

Output: knowledge_base/processed/chunks.json
Each entry is a dict ready to be embedded and stored in a vector database.
"""

import json
import os
import sys

# Allow importing sibling modules
sys.path.insert(0, os.path.dirname(__file__))
# Allow importing from the scraper package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scraper"))

from cleaner import clean_file
from chunker import chunk_text, DEFAULT_MAX_CHARS
from pages import STATIC_PAGES  # Source-of-truth page metadata

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "processed", "chunks.json")


def _build_page_index() -> dict[str, dict]:
    """
    Return a dict keyed by filename mapping to page metadata.
    e.g. {"home.txt": {"url": "...", "category": "home", "language": "en"}}
    """
    index = {}
    for page in STATIC_PAGES:
        index[page["filename"]] = {
            "url": page["url"],
            "category": page["category"],
            "language": page["language"],
        }
    return index


def build_chunks(max_chars: int = DEFAULT_MAX_CHARS) -> list[dict]:
    """
    Run the full pipeline for every raw file that has page metadata.
    Returns a list of chunk dicts.
    """
    page_index = _build_page_index()
    all_chunks: list[dict] = []

    for filename in sorted(os.listdir(RAW_DIR)):
        if not filename.endswith(".txt"):
            continue

        page_meta = page_index.get(filename)
        if page_meta is None:
            # Dynamically discovered pages (training courses, service details)
            # don't have a STATIC_PAGES entry.  Build a best-effort metadata stub.
            lang = "ar" if filename.endswith("_ar.txt") else "en"
            category = filename.replace("_ar.txt", "").replace(".txt", "")
            page_meta = {"url": None, "category": category, "language": lang}

        filepath = os.path.join(RAW_DIR, filename)
        cleaned = clean_file(filepath)
        chunks = chunk_text(cleaned, max_chars)

        for idx, chunk_text_val in enumerate(chunks):
            lang = page_meta["language"]
            category = page_meta["category"]
            chunk_id = f"{category}_{lang}_chunk_{idx}" if idx == 0 else \
                       f"{category}_{lang}_chunk_{idx}"
            # Make the id unique across all pages (include stem)
            stem = filename.replace(".txt", "")
            chunk_id = f"{stem}_chunk_{idx}"

            all_chunks.append({
                "id": chunk_id,
                "text": chunk_text_val,
                "metadata": {
                    "source_file": filename,
                    "category": page_meta["category"],
                    "language": page_meta["language"],
                    "url": page_meta["url"],
                    "chunk_index": idx,
                    "char_count": len(chunk_text_val),
                },
            })

        print(f"Processed: {filename:25s}  ({len(chunks)} chunks)")

    return all_chunks


def save_chunks(chunks: list[dict], output_path: str = OUTPUT_FILE):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(chunks)} chunks → {output_path}")


def run(max_chars: int = DEFAULT_MAX_CHARS):
    """Entry point: build and save all chunks."""
    chunks = build_chunks(max_chars)
    save_chunks(chunks)
    return chunks


if __name__ == "__main__":
    run()
