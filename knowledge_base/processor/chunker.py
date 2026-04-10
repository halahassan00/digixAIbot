import re
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cleaner import clean_file, CLEANED_DIR

CHUNKS_DIR = os.path.join(os.path.dirname(__file__), "..", "processed", "chunks")

# Target chunk size in characters.  ~800 chars ≈ 150–200 tokens — a comfortable
# retrieval unit that preserves local context without being too large to embed.
DEFAULT_MAX_CHARS = 800


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """
    Split cleaned page text into retrieval-ready chunks.

    Strategy:
      1. Split on blank lines to get logical paragraphs / sections.
      2. Accumulate paragraphs until the running total would exceed max_chars,
         then flush the current chunk and start a new one.
      3. If a single paragraph is longer than max_chars, split it into
         sentence-boundary sub-chunks so nothing is silently dropped.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_size: int = 0

    for para in paragraphs:
        # A paragraph that is itself too large gets split by sentences first
        if len(para) > max_chars:
            # Flush whatever is buffered before the oversized paragraph
            if buffer:
                chunks.append("\n\n".join(buffer))
                buffer, buffer_size = [], 0

            chunks.extend(_split_long_paragraph(para, max_chars))
            continue

        # Adding this paragraph would overflow the current chunk → flush first
        if buffer_size + len(para) > max_chars and buffer:
            chunks.append("\n\n".join(buffer))
            buffer, buffer_size = [], 0

        buffer.append(para)
        buffer_size += len(para)

    if buffer:
        chunks.append("\n\n".join(buffer))

    return chunks


def _split_long_paragraph(text: str, max_chars: int) -> list[str]:
    """Break a single long paragraph on sentence boundaries."""
    # Split on .  !  ? followed by whitespace or end-of-string
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_size: int = 0

    for sentence in sentences:
        if buffer_size + len(sentence) > max_chars and buffer:
            chunks.append(" ".join(buffer))
            buffer, buffer_size = [], 0
        buffer.append(sentence)
        buffer_size += len(sentence)

    if buffer:
        chunks.append(" ".join(buffer))

    return chunks


def chunk_file(filepath: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Read a cleaned .txt file and return its chunks."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    return chunk_text(text, max_chars)


def chunk_all(max_chars: int = DEFAULT_MAX_CHARS):
    """Chunk every file in processed/cleaned/ and print a summary."""
    if not os.path.isdir(CLEANED_DIR):
        print(f"Cleaned directory not found: {CLEANED_DIR}")
        print("Run cleaner.py first.")
        return

    os.makedirs(CHUNKS_DIR, exist_ok=True)

    for filename in sorted(os.listdir(CLEANED_DIR)):
        if not filename.endswith(".txt"):
            continue

        src = os.path.join(CLEANED_DIR, filename)
        chunks = chunk_file(src, max_chars)

        # Write one chunk per line in a plain text preview file
        dst = os.path.join(CHUNKS_DIR, filename)
        with open(dst, "w", encoding="utf-8") as f:
            for i, chunk in enumerate(chunks):
                f.write(f"--- chunk {i} ---\n{chunk}\n\n")

        print(f"Chunked: {filename:25s}  ({len(chunks)} chunks)")


if __name__ == "__main__":
    chunk_all()
