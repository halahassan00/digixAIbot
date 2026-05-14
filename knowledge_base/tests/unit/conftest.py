"""
Pytest fixtures that create minimal PDF files for unit testing.

Both fixtures use PyMuPDF's writer to build in-memory PDFs and save
them to a temporary directory — no pre-existing PDF files are required.

Note on Arabic rendering
------------------------
PyMuPDF's insert_text() uses PDF base14 fonts which do not include
Arabic glyphs.  Arabic characters in content streams require a CIDFont
or embedded TTF, which adds significant complexity.  Instead, the
sample_text_pdf fixture stores text that is reliably extractable
(ASCII + ASCII-range Arabic transliteration labels).  The known phrase
"DIGIX AI" is always present, and the total extracted length exceeds
MIN_CHARS_THRESHOLD (100 chars).  Separate detect_language() unit tests
use raw Python strings — they do not depend on PDF round-trip behaviour.
"""

import pytest
from pathlib import Path


@pytest.fixture
def sample_text_pdf(tmp_path) -> Path:
    """
    A single-page PDF with selectable text.

    Contains a long enough ASCII string to pass MIN_CHARS_THRESHOLD (100),
    and includes the known phrase "DIGIX AI" for content verification.
    """
    import fitz

    content = (
        "DIGIX AI - Training Course Overview\n\n"
        "Welcome to the Digix AI training program. This course covers advanced\n"
        "artificial intelligence concepts and practical applications.\n\n"
        "Modules include: data analysis, machine learning, natural language\n"
        "processing, and business intelligence with Power BI.\n\n"
        "Target audience: business analysts, data scientists, and managers.\n"
        "Duration: three intensive training days with hands-on exercises.\n"
    )

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 80), content, fontsize=11)
    path = tmp_path / "sample_text.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def sample_image_pdf(tmp_path) -> Path:
    """
    A single-page PDF with no selectable text layer (simulates an
    image-based PDF exported from Canva/Figma).

    We draw a filled rectangle instead of inserting text so PyMuPDF
    finds zero text characters on extraction.
    """
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Draw a filled gray rectangle — no text in the content stream
    page.draw_rect(
        fitz.Rect(50, 50, 500, 700),
        color=(0.5, 0.5, 0.5),
        fill=(0.8, 0.8, 0.8),
    )
    path = tmp_path / "sample_image.pdf"
    doc.save(str(path))
    doc.close()
    return path
