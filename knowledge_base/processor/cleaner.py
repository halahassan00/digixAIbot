import re
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")
CLEANED_DIR = os.path.join(os.path.dirname(__file__), "..", "processed", "cleaned")

# Lines to discard on exact match (after stripping whitespace)
EXACT_NOISE = {
    "•",        # Bullet markers that appeared alone on a line
    "0",        # Animated counter placeholders in impact.txt
    "+",        # Animated counter suffix
    "%",        # Animated counter suffix
    "*",        # Required-field markers from the contact form
    "العربية",  # Language-switcher link at the top of some pages
    "Show More", # Pagination artifact on the training page
}

# Once one of these lines is reached, everything after it is footer boilerplate
FOOTER_TRIGGERS = {
    "Copyright© 2026 DigixAi. All rights reserved.",
    "© 2026 جميع الحقوق محفوظة لشركة  DigixAi.",
    "© 2026 جميع الحقوق محفوظة لشركة DigixAi.",
}

# Patterns that mark an entire line as noise (anchored to the full line)
_LINE_PATTERNS = [
    re.compile(r"^tags\.\S+$"),   # tags.Cloud, tags.CRISC, tags.Governance …
    re.compile(r"^\d{2}$"),       # 01 / 02 / 03 step-number labels
]


def clean_text(text: str) -> str:
    """Remove scraper artefacts and boilerplate from raw page text."""
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        stripped = line.strip()

        # Stop at the footer — everything below is boilerplate
        if stripped in FOOTER_TRIGGERS:
            break

        # Convert section dividers to blank lines so the chunker can split on them
        if stripped == "|":
            cleaned.append("")
            continue

        # Drop exact-match noise tokens
        if stripped in EXACT_NOISE:
            continue

        # Drop pattern-matched noise lines
        if any(p.match(stripped) for p in _LINE_PATTERNS):
            continue

        cleaned.append(stripped)

    # Collapse runs of blank lines into a single blank line
    result = []
    prev_blank = False
    for line in cleaned:
        if line == "":
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    return "\n".join(result).strip()


def clean_file(filepath: str) -> str:
    """Read a raw .txt file and return its cleaned text."""
    with open(filepath, "r", encoding="utf-8") as f:
        return clean_text(f.read())


def clean_all():
    """Process every .txt file in raw/ and write cleaned versions to processed/cleaned/."""
    os.makedirs(CLEANED_DIR, exist_ok=True)

    for filename in sorted(os.listdir(RAW_DIR)):
        if not filename.endswith(".txt"):
            continue

        src = os.path.join(RAW_DIR, filename)
        dst = os.path.join(CLEANED_DIR, filename)

        cleaned = clean_file(src)

        with open(dst, "w", encoding="utf-8") as f:
            f.write(cleaned)

        lines = cleaned.count("\n") + 1
        print(f"Cleaned: {filename:25s}  ({lines} lines)")


if __name__ == "__main__":
    clean_all()
