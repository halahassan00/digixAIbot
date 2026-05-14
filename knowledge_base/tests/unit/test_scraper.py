"""
knowledge_base/tests/unit/test_scraper.py

Unit tests for knowledge_base/scraper/scraper.py (GROUP 12, tests 74-76).
fetch_page, extract_text, and save_text are monkeypatched — no network calls.
"""

import hashlib

import pytest

import knowledge_base.scraper.scraper as scraper_module

# A minimal page list used in place of the real STATIC_PAGES
_SINGLE_PAGE = [
    {
        "url": "https://example.com/test",
        "category": "test",
        "filename": "test.txt",
        "js_render": False,
    }
]

_HTML = "<html><body><p>Test content</p></body></html>"
_TEXT = "Test content"
_TEXT_HASH = hashlib.sha256(_TEXT.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _patch_pages(monkeypatch):
    """Replace STATIC_PAGES with a single controllable page; disable dynamic discovery."""
    monkeypatch.setattr(scraper_module, "STATIC_PAGES", _SINGLE_PAGE)
    monkeypatch.setattr(scraper_module, "DYNAMIC_SECTIONS", [])


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip the politeness delay so tests finish instantly."""
    monkeypatch.setattr(scraper_module.time, "sleep", lambda _: None)


# ---------------------------------------------------------------------------
# Test 74: skip page when hash matches
# ---------------------------------------------------------------------------

def test_scrape_all_skips_unchanged_page(monkeypatch):
    """When stored hash matches extracted text, save_text is NOT called (test 74)."""
    monkeypatch.setattr(scraper_module, "fetch_page", lambda url, **kw: _HTML)
    monkeypatch.setattr(scraper_module, "extract_text", lambda html: _TEXT)

    saved = []
    monkeypatch.setattr(scraper_module, "save_text", lambda text, fname: saved.append(fname))

    # Pre-populate store with the matching hash
    result = scraper_module.scrape_all(web_hash_store={_SINGLE_PAGE[0]["url"]: _TEXT_HASH})

    assert saved == [], "save_text must not be called when hash is unchanged"


# ---------------------------------------------------------------------------
# Test 75: call save_text when hash changes
# ---------------------------------------------------------------------------

def test_scrape_all_saves_when_hash_changes(monkeypatch):
    """When stored hash differs from current text, save_text IS called (test 75)."""
    monkeypatch.setattr(scraper_module, "fetch_page", lambda url, **kw: _HTML)
    monkeypatch.setattr(scraper_module, "extract_text", lambda html: _TEXT)

    saved = []
    monkeypatch.setattr(scraper_module, "save_text", lambda text, fname: saved.append(fname))

    # Store has a stale hash
    result = scraper_module.scrape_all(web_hash_store={_SINGLE_PAGE[0]["url"]: "old_hash"})

    assert "test.txt" in saved
    # Hash in return dict must be updated to the current value
    assert result[_SINGLE_PAGE[0]["url"]] == _TEXT_HASH


# ---------------------------------------------------------------------------
# Test 76: returns updated hash dict
# ---------------------------------------------------------------------------

def test_scrape_all_returns_updated_hash_dict(monkeypatch):
    """scrape_all returns a dict mapping url → sha256(text) (test 76)."""
    monkeypatch.setattr(scraper_module, "fetch_page", lambda url, **kw: _HTML)
    monkeypatch.setattr(scraper_module, "extract_text", lambda html: _TEXT)
    monkeypatch.setattr(scraper_module, "save_text", lambda text, fname: None)

    result = scraper_module.scrape_all(web_hash_store={})

    assert isinstance(result, dict)
    assert _SINGLE_PAGE[0]["url"] in result
    assert result[_SINGLE_PAGE[0]["url"]] == _TEXT_HASH
