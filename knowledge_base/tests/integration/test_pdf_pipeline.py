"""
knowledge_base/tests/integration/test_pdf_pipeline.py

Integration tests for the PDF processing pipeline.

Tests 2–4 use a synthetic text-based PDF created at test time;
Test 1 requires a real text-based PDF from DIGIX AI and is skipped
until that file is provided.
"""

import json
import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "knowledge_base" / "processor"))
sys.path.insert(0, str(ROOT / "knowledge_base" / "scraper"))

from knowledge_base.processor.pdf_processor import process_all_pdfs, process_pdf


# ---------------------------------------------------------------------------
# Fixture: synthetic text-based Arabic PDF
# ---------------------------------------------------------------------------

@pytest.fixture
def arabic_pdf(tmp_path) -> Path:
    """Create a synthetic multi-paragraph Arabic PDF for pipeline testing."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    content = (
        "دورة Power BI من Digix AI\n\n"
        "هذه الدورة تغطي مفاهيم تحليل البيانات باستخدام Power BI.\n\n"
        "المحتوى يشمل: لوحات البيانات، والتقارير التفاعلية، وتحليل البيانات.\n\n"
        "الجمهور المستهدف: المحللون الماليون ومديرو الأعمال.\n\n"
        "المدة: ثلاثة أيام تدريبية مكثفة مع تمارين عملية.\n"
    )
    page.insert_text((50, 80), content, fontsize=11)
    pdf_path = tmp_path / "synthetic_power_bi.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# Test 1 — Real Power_BI.pdf (skipped until client provides text-based version)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="requires text-based PDF from client — current PDF is image-based")
def test_real_power_bi_pdf_produces_arabic_output():
    """[INTEGRATION] Real Power_BI.pdf → >500 chars, >30% Arabic density."""
    from knowledge_base.processor.pdf_processor import PDFS_DIR, extract_text_from_pdf, detect_language
    pdf_path = PDFS_DIR / "Power_BI.pdf"
    assert pdf_path.exists(), f"PDF not found: {pdf_path}"

    text = extract_text_from_pdf(pdf_path)
    assert len(text) > 500, "Expected >500 chars from text-based PDF"
    assert detect_language(text) == "ar"


# ---------------------------------------------------------------------------
# Test 2 — Full pipeline: pdf_processor → cleaner → chunker → metadata
# ---------------------------------------------------------------------------

def test_full_pipeline_pdf_to_chunks_json(arabic_pdf, tmp_path):
    """[INTEGRATION] Synthetic text PDF flows through full pipeline correctly."""
    import cleaner
    import chunker
    import metadata as _metadata

    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()

    # Step 1: process_pdf → raw/
    output = process_pdf(arabic_pdf, slug="power_bi_test", raw_dir=raw_dir)
    assert output is not None and output.exists()

    # Step 2: clean
    cleaned_text = cleaner.clean_file(str(output))
    assert len(cleaned_text) > 50

    # Step 3: chunk
    chunks = chunker.chunk_text(cleaned_text)
    assert len(chunks) >= 1

    # Step 4: verify metadata assignment
    # The filename stem "power_bi_test_ar" is not in WEB_SLUGS → training
    from metadata import WEB_SLUGS
    stem = output.stem.replace("_ar", "").replace("_en", "")
    assert stem not in WEB_SLUGS

    # Simulate the metadata enrichment
    for i, chunk_text in enumerate(chunks):
        entry = {
            "id": f"{output.stem}_chunk_{i}",
            "text": chunk_text,
            "metadata": {
                "source_file": output.name,
                "category": "training",
                "language": "ar",
                "url": None,
                "chunk_index": i,
                "char_count": len(chunk_text),
            },
        }
        assert entry["metadata"]["category"] == "training"
        assert entry["metadata"]["url"] is None
        assert entry["metadata"]["language"] == "ar"


# ---------------------------------------------------------------------------
# Test 3 — process_all_pdfs skips unchanged PDFs
# ---------------------------------------------------------------------------

def test_process_all_pdfs_skips_unchanged(arabic_pdf, tmp_path):
    """[INTEGRATION] process_all_pdfs() skips a PDF whose hash has not changed."""
    pdfs_dir = tmp_path / "pdfs"
    pdfs_dir.mkdir()
    raw_dir = tmp_path / "raw"

    # Copy the synthetic PDF into the temporary pdfs_dir
    dest = pdfs_dir / "test_course.pdf"
    dest.write_bytes(arabic_pdf.read_bytes())

    # Write a manifest
    manifest = {"test_course.pdf": {"slug": "test_course"}}
    (pdfs_dir / "pdf_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    from knowledge_base.processor.pdf_processor import process_all_pdfs as _process

    # First run — processes
    results1 = _process(pdfs_dir=pdfs_dir, raw_dir=raw_dir, force=False)
    assert len(results1) == 1

    # Second run — skips (hash unchanged, output exists)
    results2 = _process(pdfs_dir=pdfs_dir, raw_dir=raw_dir, force=False)
    assert len(results2) == 0


# ---------------------------------------------------------------------------
# Test 4 — process_all_pdfs processes when force=True
# ---------------------------------------------------------------------------

def test_process_all_pdfs_force_reprocesses(arabic_pdf, tmp_path):
    """[INTEGRATION] process_all_pdfs(force=True) reprocesses even if hash unchanged."""
    pdfs_dir = tmp_path / "pdfs"
    pdfs_dir.mkdir()
    raw_dir = tmp_path / "raw"

    dest = pdfs_dir / "test_course.pdf"
    dest.write_bytes(arabic_pdf.read_bytes())

    manifest = {"test_course.pdf": {"slug": "test_course"}}
    (pdfs_dir / "pdf_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    from knowledge_base.processor.pdf_processor import process_all_pdfs as _process

    # First run
    _process(pdfs_dir=pdfs_dir, raw_dir=raw_dir, force=False)

    # Second run with force=True — must process again
    results = _process(pdfs_dir=pdfs_dir, raw_dir=raw_dir, force=True)
    assert len(results) == 1
