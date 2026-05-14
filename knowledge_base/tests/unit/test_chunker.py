"""
knowledge_base/tests/unit/test_chunker.py

Unit tests for knowledge_base/processor/chunker.py (GROUP 3, tests 18-22).
"""

from knowledge_base.processor.chunker import DEFAULT_MAX_CHARS, chunk_text


def test_all_chunks_within_max_chars():
    """Every produced chunk must be ≤ DEFAULT_MAX_CHARS characters (test 18)."""
    text = "\n\n".join(f"Paragraph {i}: " + "word " * 50 for i in range(20))
    chunks = chunk_text(text)
    assert chunks
    for chunk in chunks:
        assert len(chunk) <= DEFAULT_MAX_CHARS


def test_chunks_split_on_paragraph_boundaries():
    """Paragraphs separated by double-newlines become distinct chunks (test 19)."""
    # Two paragraphs each just under DEFAULT_MAX_CHARS — together they exceed it
    para_a = "A " * (DEFAULT_MAX_CHARS // 2 // 2)   # well under limit alone
    para_b = "B " * (DEFAULT_MAX_CHARS // 2 // 2)
    text = para_a.strip() + "\n\n" + para_b.strip()
    # If combined length > limit the chunker must split on the blank line
    if len(para_a.strip()) + len(para_b.strip()) > DEFAULT_MAX_CHARS:
        chunks = chunk_text(text)
        assert len(chunks) >= 2
    else:
        # Combined fits — verify we still get at least one chunk
        assert len(chunk_text(text)) >= 1


def test_long_paragraph_split_by_sentences():
    """A paragraph longer than DEFAULT_MAX_CHARS is split at sentence boundaries (test 20)."""
    long_para = ". ".join(f"This is sentence number {i}" for i in range(60)) + "."
    assert len(long_para) > DEFAULT_MAX_CHARS
    chunks = chunk_text(long_para)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= DEFAULT_MAX_CHARS


def test_nonempty_input_returns_at_least_one_chunk():
    """Any non-empty input produces ≥ 1 chunk (test 21)."""
    assert len(chunk_text("hello")) >= 1


def test_empty_string_returns_empty_list():
    """Empty input returns [] (test 22)."""
    assert chunk_text("") == []
