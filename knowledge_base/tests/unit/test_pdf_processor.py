"""
knowledge_base/tests/unit/test_pdf_processor.py

Unit tests for pdf_processor.py.

Fixtures (sample_text_pdf, sample_image_pdf) are defined in conftest.py
and create minimal in-memory PDFs using PyMuPDF — no pre-existing files needed.
"""

import logging

import pytest

from knowledge_base.processor.pdf_processor import (
    clean_pdf_text,
    detect_language,
    extract_text_from_pdf,
    process_pdf,
    process_all_pdfs
)


# ---------------------------------------------------------------------------
# extract_text_from_pdf
# ---------------------------------------------------------------------------

def test_extract_text_returns_nonempty_for_text_pdf(sample_text_pdf):
    """[UNIT] Text-based PDF yields a non-empty string."""
    text = extract_text_from_pdf(sample_text_pdf)
    assert isinstance(text, str)
    assert len(text) > 0


def test_extract_text_contains_known_phrase(sample_text_pdf):
    """[UNIT] Extracted text contains the phrase we inserted."""
    text = extract_text_from_pdf(sample_text_pdf)
    assert "DIGIX AI" in text


def test_extract_text_returns_empty_for_image_pdf(sample_image_pdf):
    """[UNIT] Image-based PDF (no text layer) returns empty string."""
    text = extract_text_from_pdf(sample_image_pdf)
    assert text.strip() == ""


# ---------------------------------------------------------------------------
# process_pdf — image-based detection
# ---------------------------------------------------------------------------

def test_process_pdf_warns_and_returns_none_for_image_pdf(sample_image_pdf, tmp_path, caplog):
    """[UNIT] Image-based PDF: warning logged, None returned, no file written."""
    with caplog.at_level(logging.WARNING, logger="knowledge_base.processor.pdf_processor"):
        result = process_pdf(sample_image_pdf, slug="test", raw_dir=tmp_path)

    assert result is None
    warning_text = " ".join(r.message for r in caplog.records)
    assert "image-based" in warning_text.lower()
    # No file should have been written
    assert list(tmp_path.glob("*.txt")) == []


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------

def test_detect_language_arabic_majority():
    """[UNIT] Text with >30% Arabic characters → 'ar'."""
    arabic_text = "مرحباً بكم في شركة Digix AI للتدريب والحلول التقنية المتقدمة"
    assert detect_language(arabic_text) == "ar"


def test_detect_language_english_majority():
    """[UNIT] Text with <30% Arabic characters → 'en'."""
    english_text = "Welcome to Digix AI. We provide advanced AI training and solutions."
    assert detect_language(english_text) == "en"


def test_detect_language_empty_string_defaults_to_arabic():
    """[UNIT] Empty text defaults to 'ar' (DIGIX AI content is predominantly Arabic)."""
    assert detect_language("") == "ar"


# ---------------------------------------------------------------------------
# clean_pdf_text
# ---------------------------------------------------------------------------

def test_clean_removes_short_lines():
    """[UNIT] Lines shorter than 3 characters are removed."""
    text = "مرحباً\n1\n.\nهذا النص جيد"
    cleaned = clean_pdf_text(text)
    assert "مرحباً" in cleaned
    assert "هذا النص جيد" in cleaned
    # "1" and "." are < 3 chars — must not appear as standalone lines
    lines = [l for l in cleaned.splitlines() if l.strip()]
    assert all(len(l) >= 3 for l in lines)


def test_clean_collapses_multiple_blank_lines():
    """[UNIT] Three or more consecutive blank lines collapse to one."""
    text = "سطر أول\n\n\n\nسطر ثانٍ"
    cleaned = clean_pdf_text(text)
    # Should not have more than one consecutive blank line
    assert "\n\n\n" not in cleaned


# ---------------------------------------------------------------------------
# process_pdf — success path
# ---------------------------------------------------------------------------

def test_process_pdf_writes_output_file(sample_text_pdf, tmp_path):
    """[UNIT] process_pdf writes {slug}_{lang}.txt and returns the path."""
    result = process_pdf(sample_text_pdf, slug="test_course", raw_dir=tmp_path)

    assert result is not None
    assert result.exists()
    # Name follows the slug_lang.txt convention
    assert result.stem.startswith("test_course_")
    assert result.suffix == ".txt"
    assert result.parent == tmp_path


def test_process_pdf_is_idempotent(sample_text_pdf, tmp_path):
    """[UNIT] Running process_pdf twice produces the same file without error."""
    result1 = process_pdf(sample_text_pdf, slug="idempotent_test", raw_dir=tmp_path)
    result2 = process_pdf(sample_text_pdf, slug="idempotent_test", raw_dir=tmp_path)

    assert result1 is not None
    assert result2 is not None
    assert result1 == result2
    assert result1.read_text(encoding="utf-8") == result2.read_text(encoding="utf-8")

# knowledge_base/tests/unit/test_pdf_processor.py

def test_process_all_pdfs_returns_updated_hashes(tmp_path):
    """process_all_pdfs returns updated hash dict without writing to disk."""
    # Create a synthetic text-based PDF in tmp pdfs dir.
    # Content must exceed MIN_CHARS_THRESHOLD (100 chars) to pass extraction.
    import fitz
    pdf = tmp_path / "test_course.pdf"
    doc = fitz.open()
    page = doc.new_page()
    long_content = (
        "DIGIX AI test course content. "
        "This course covers AI, machine learning, and data science. "
        "Enrol now to advance your career in technology."
    )
    page.insert_text((50, 100), long_content, fontsize=12)
    doc.save(str(pdf))
    doc.close()

    # Write manifest
    manifest = tmp_path / "pdf_manifest.json"
    manifest.write_text('{"test_course.pdf": {"slug": "test_course"}}')

    raw_dir = tmp_path / "raw"
    result = process_all_pdfs(
        pdfs_dir=tmp_path,
        raw_dir=raw_dir,
        pdf_hash_store={},   # empty → forces processing
    )

    # Returns updated hash dict
    assert "test_course.pdf" in result
    assert len(result["test_course.pdf"]) == 64  # SHA-256 hex length

def test_process_all_pdfs_skips_unchanged(tmp_path):
    """PDF with matching hash is skipped; no output file written."""
    import hashlib, fitz
    pdf = tmp_path / "test_course.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Same content", fontsize=12)
    doc.save(str(pdf))
    doc.close()

    current_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # Pre-create output file to simulate "already processed"
    (raw_dir / "test_course_ar.txt").write_text("existing", encoding="utf-8")

    manifest = tmp_path / "pdf_manifest.json"
    manifest.write_text('{"test_course.pdf": {"slug": "test_course"}}')

    result = process_all_pdfs(
        pdfs_dir=tmp_path,
        raw_dir=raw_dir,
        pdf_hash_store={"test_course.pdf": current_hash},  # hash matches
    )

    # Hash unchanged — no new processing, original file untouched
    assert (raw_dir / "test_course_ar.txt").read_text() == "existing"
