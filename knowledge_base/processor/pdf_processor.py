"""
knowledge_base/processor/pdf_processor.py

Extracts text from text-based PDFs and feeds output into the existing
raw → cleaner → chunker → metadata → ChromaDB pipeline.

Context
-------
DIGIX AI's 14 current training PDFs were image-based exports and have
already been manually transcribed into knowledge_base/raw/. This module
handles FUTURE PDFs only.

DIGIX AI must be instructed to export PDFs from Word/Google Docs/LibreOffice,
NOT from Canva, Figma, or other design tools (those produce image-only PDFs).

If an image-based PDF is detected, this module logs a clear warning and
skips it rather than silently producing empty output.

No OCR is performed. No embedding. No ChromaDB calls.

Usage
-----
  # Process all PDFs in knowledge_base/pdfs/
  python -m knowledge_base.processor.pdf_processor

  # Called by sync.py on each run
  from knowledge_base.processor.pdf_processor import process_all_pdfs
  process_all_pdfs()
"""

import hashlib
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT      = Path(__file__).resolve().parents[2]
PDFS_DIR  = ROOT / "knowledge_base" / "pdfs"
RAW_DIR   = ROOT / "knowledge_base" / "raw"
MANIFEST  = PDFS_DIR / "pdf_manifest.json"
HASH_STORE = PDFS_DIR / "pdf_hash_store.json"

MIN_CHARS_THRESHOLD = 100   # fewer chars → likely image-based PDF

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from a text-based PDF using PyMuPDF.

    Returns the concatenated text of all pages, separated by double newlines.
    Returns an empty string if no text is found (image-based PDF).

    Does NOT write to disk. Does NOT clean. Does NOT detect language.
    Caller is responsible for those steps.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n".join(p for p in pages if p.strip())
    except Exception as exc:
        logger.error("Failed to open %s: %s", pdf_path.name, exc)
        return ""


def detect_language(text: str) -> str:
    """
    Return "ar" if Arabic characters make up more than 30% of all
    alphabetic characters in text, else return "en".

    Three Unicode ranges are checked because PDF exporters (including Word)
    sometimes store Arabic in Presentation Forms rather than standard:
      - Standard Arabic:       U+0600–U+06FF
      - Presentation Forms A:  U+FB50–U+FDFF
      - Presentation Forms B:  U+FE70–U+FEFF  ← Word / PyMuPDF often uses this

    Default: "ar" (DIGIX AI content is predominantly Arabic).
    """
    arabic = sum(
        1 for c in text
        if ("؀" <= c <= "ۿ")
        or ("ﭐ" <= c <= "﷿")
        or ("ﹰ" <= c <= "﻿")
    )
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return "ar"
    return "ar" if arabic / total_alpha > 0.30 else "en"


def clean_pdf_text(text: str) -> str:
    """
    Light cleaning appropriate for text-based PDF output.

    Steps applied in order:
    1. Strip leading/trailing whitespace per line.
    2. Collapse runs of more than 2 consecutive blank lines to 1.
    3. Remove lines shorter than 3 characters (page numbers, stray chars).
    4. Strip the whole document.

    Does NOT apply web-scraping-specific rules (no pipe removal,
    no footer boilerplate). Those belong in cleaner.py.
    """
    lines = [line.strip() for line in text.splitlines()]

    # Remove very short lines
    lines = [line for line in lines if len(line) >= 3 or line == ""]

    # Collapse consecutive blank lines
    result_lines: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 1:
                result_lines.append(line)
        else:
            blank_run = 0
            result_lines.append(line)

    return "\n".join(result_lines).strip()


def process_pdf(
    pdf_path: Path,
    slug: str,
    raw_dir: Path = RAW_DIR,
) -> "Path | None":
    """
    Full pipeline for a single PDF:
      1. extract_text_from_pdf()
      2. Check minimum character count — warn and return None if below threshold
      3. clean_pdf_text()
      4. detect_language()
      5. Write to raw_dir / f"{slug}_{lang}.txt"
      6. Return the output path, or None if extraction failed

    Logs a clear warning if the PDF appears to be image-based.
    """
    text = extract_text_from_pdf(pdf_path)

    if len(text) < MIN_CHARS_THRESHOLD:
        logger.warning(
            "WARNING: %s produced only %d chars after extraction. "
            "This PDF is likely image-based (exported from Canva/Figma/design tool). "
            "Re-export as a text-based PDF from Word or Google Docs, or contact the "
            "DIGIX AI team to provide a text-based version.",
            pdf_path.name,
            len(text),
        )
        return None

    cleaned = clean_pdf_text(text)
    lang = detect_language(cleaned)

    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / f"{slug}_{lang}.txt"
    output_path.write_text(cleaned, encoding="utf-8")
    logger.info("Wrote %s (%d chars, lang=%s)", output_path.name, len(cleaned), lang)
    return output_path


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, default) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return default


def _auto_slug(filename: str) -> str:
    """Derive a slug from a filename when not in the manifest."""
    stem = Path(filename).stem
    # Remove non-ASCII, lowercase, replace whitespace/hyphens with underscores
    ascii_stem = stem.encode("ascii", errors="ignore").decode()
    slug = re.sub(r"[\s\-]+", "_", ascii_stem).strip("_").lower()
    return slug or "unknown"


def process_all_pdfs(
    pdfs_dir: Path = PDFS_DIR,
    raw_dir: Path = RAW_DIR,
    force: bool = False,
    pdf_hash_store: dict | None = None,
) -> dict:
    """
    Process all PDFs in pdfs_dir that are new or changed since last run.

    Change detection is hash-based (SHA-256). Skips PDFs whose hash and
    output file are both unchanged unless force=True.

    Reads slug assignments from pdf_manifest.json. PDFs without a manifest
    entry get an auto-generated slug and a notice to add them manually.

    Returns dict mapping slug → output_path for successfully processed PDFs.
    Prints a summary table on completion.

    This is the function sync.py calls.
    """
    manifest = _load_json(MANIFEST, {})
    hash_store = dict(pdf_hash_store) if pdf_hash_store else {}

    pdf_files = sorted(pdfs_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDFs found in", pdfs_dir)
        return {}

    results: dict[str, Path] = {}
    skipped = 0

    for pdf_path in pdf_files:
        fname = pdf_path.name

        # Resolve slug
        if fname in manifest:
            slug = manifest[fname]["slug"]
        else:
            slug = _auto_slug(fname)
            logger.info(
                "No manifest entry for %r — using auto-generated slug %r. "
                "Add it to pdf_manifest.json for stable naming.",
                fname, slug,
            )

        # Hash-based change detection
        current_hash = _sha256(pdf_path)
        expected_output = raw_dir / f"{slug}_ar.txt"  # check either lang variant
        expected_output_en = raw_dir / f"{slug}_en.txt"
        output_exists = expected_output.exists() or expected_output_en.exists()

        if not force and hash_store.get(fname) == current_hash and output_exists:
            skipped += 1
            continue

        # Process
        output = process_pdf(pdf_path, slug, raw_dir)
        if output is not None:
            results[slug] = output
            hash_store[fname] = current_hash


    # Summary
    print(f"\n{'='*60}")
    print(f"  PDF processing complete")
    print(f"  Processed: {len(results)}  |  Skipped (unchanged): {skipped}  |  Failed: {len(pdf_files) - len(results) - skipped}")
    print(f"{'='*60}")
    for slug, path in results.items():
        print(f"  {slug:35s} → {path.name}")

    return hash_store


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # Standalone run: load and save the shared hash store directly
    HASH_STORE_PATH = ROOT / "knowledge_base" / "sync" / "hash_store.json"

    def _load_store():
        if HASH_STORE_PATH.exists():
            try:
                data = json.loads(HASH_STORE_PATH.read_text(encoding="utf-8"))
                return data.get("pdf", {})
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_store(pdf_hashes: dict):
        HASH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing = json.loads(HASH_STORE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            existing = {"web": {}, "pdf": {}}
        existing["pdf"] = pdf_hashes
        HASH_STORE_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    pdf_hashes = process_all_pdfs(pdf_hash_store=_load_store())
    _save_store(pdf_hashes)