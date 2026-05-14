"""
knowledge_base/tests/unit/test_cleaner.py

Unit tests for knowledge_base/processor/cleaner.py (GROUP 2, tests 13-17).
"""

from knowledge_base.processor.cleaner import clean_file, clean_text


def test_clean_removes_footer_boilerplate():
    """Lines at or after the footer trigger are stripped (test 13)."""
    text = (
        "معلومات مفيدة عن Digix AI\n"
        "Copyright© 2026 DigixAi. All rights reserved.\n"
        "بيانات ما بعد الفوتر يجب أن تُحذف"
    )
    result = clean_text(text)
    assert "معلومات مفيدة" in result
    assert "Copyright" not in result
    assert "بيانات ما بعد" not in result


def test_clean_removes_pipe_divider_lines():
    """Lines containing only '|' must not appear in the output (test 14)."""
    text = "قسم أول\n|\nقسم ثانٍ"
    result = clean_text(text)
    assert not any(line.strip() == "|" for line in result.splitlines())


def test_clean_collapses_excess_blank_lines():
    """More than 2 consecutive blank lines collapse to at most 1 (test 15)."""
    text = "سطر أول\n\n\n\n\nسطر ثانٍ"
    result = clean_text(text)
    assert "\n\n\n" not in result


def test_clean_preserves_arabic_text():
    """Arabic content is passed through unchanged (test 16)."""
    arabic = "تقدم Digix AI تدريباً متخصصاً في مجال الذكاء الاصطناعي."
    result = clean_text(arabic)
    assert arabic in result


def test_clean_file_returns_nonempty(tmp_path):
    """clean_file on a normal .txt file returns non-empty output (test 17)."""
    txt = tmp_path / "sample.txt"
    txt.write_text(
        "Digix AI provides AI training programs.\n"
        "Contact us for more information.\n",
        encoding="utf-8",
    )
    result = clean_file(str(txt))
    assert len(result.strip()) > 0
