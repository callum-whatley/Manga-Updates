"""
Unit tests for the _upsert_source_entry guard logic in app/api/manga.py.

Focuses on the scraped_title validation paths that are hard to exercise through
the full HTTP layer:
  - score < 80 against stored scraped_title → update is skipped
  - existing entry with no scraped_title → stores new title on first update
  - new_title is None → guard is bypassed (update proceeds)
  - is_removed entry → always skipped regardless of title
  - new entry (no existing) → creates with scraped_title stored
"""

from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_manga(id_=1, title='Solo Leveling'):
    m = MagicMock()
    m.id = id_
    m.title = title
    m.cover_url = None
    return m


def _make_site(id_=10):
    s = MagicMock()
    s.id = id_
    return s


def _scraped(title='Solo Leveling', chapter=100, chapter_url='https://site.com/ch/100', cover_url=None):
    d = {'chapter': chapter, 'chapter_url': chapter_url}
    if title is not None:
        d['title'] = title
    if cover_url is not None:
        d['cover_url'] = cover_url
    return d


def _run_upsert(manga, site, scraped_data, existing_entry=None):
    """
    Call _upsert_source_entry with both MangaSourceEntry (fetched inside the
    function via 'from ..models import MangaSourceEntry') and db.session patched.

    Patches:
      app.models.MangaSourceEntry  — the class the function imports at call time
      app.api.manga.db             — the db instance imported at module level
    """
    from app.api.manga import _upsert_source_entry

    mock_mse_class = MagicMock()
    mock_mse_class.query.filter_by.return_value.first.return_value = existing_entry

    mock_db = MagicMock()

    with (
        patch('app.models.MangaSourceEntry', mock_mse_class),
        patch('app.api.manga.db', mock_db),
    ):
        _upsert_source_entry(manga, site, scraped_data)

    return mock_db, mock_mse_class


# ── Guard: score below threshold → skip ──────────────────────────────────────

class TestGuardBelowThreshold:
    def test_skips_update_when_score_below_80(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = False
        existing.scraped_title = 'Solo Leveling'
        original_chapter = 99
        existing.latest_chapter = original_chapter

        scraped_data = _scraped(title='Completely Different Series', chapter=1)

        with patch('app.scrapers.matcher._score', return_value=40.0):
            mock_db, _ = _run_upsert(manga, site, scraped_data, existing_entry=existing)

        assert existing.latest_chapter == original_chapter
        mock_db.session.add.assert_not_called()

    def test_does_not_skip_when_score_at_80(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = False
        existing.scraped_title = 'Solo Leveling'
        existing.latest_chapter = 99

        scraped_data = _scraped(title='Solo Leveling', chapter=100)

        # Patch the binding that manga.py imported directly at module load time
        with patch('app.api.manga._score', return_value=80.0):
            _run_upsert(manga, site, scraped_data, existing_entry=existing)

        assert existing.latest_chapter == 100

    def test_does_not_skip_when_score_above_80(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = False
        existing.scraped_title = 'Solo Leveling'
        existing.latest_chapter = 99

        scraped_data = _scraped(title='Solo Leveling', chapter=101)

        with patch('app.api.manga._score', return_value=95.0):
            _run_upsert(manga, site, scraped_data, existing_entry=existing)

        assert existing.latest_chapter == 101


# ── First write of scraped_title ──────────────────────────────────────────────

class TestFirstWriteOfScrapedTitle:
    def test_stores_scraped_title_when_entry_has_none(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = False
        existing.scraped_title = None  # not yet set
        existing.latest_chapter = 50

        scraped_data = _scraped(title='Solo Leveling', chapter=51)

        _run_upsert(manga, site, scraped_data, existing_entry=existing)

        assert existing.scraped_title == 'Solo Leveling'
        assert existing.latest_chapter == 51

    def test_does_not_overwrite_existing_scraped_title(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = False
        existing.scraped_title = 'Solo Leveling'
        existing.latest_chapter = 99

        scraped_data = _scraped(title='Solo Leveling Chapter Special', chapter=100)

        with patch('app.scrapers.matcher._score', return_value=95.0):
            _run_upsert(manga, site, scraped_data, existing_entry=existing)

        # scraped_title was already set — must not be overwritten
        assert existing.scraped_title == 'Solo Leveling'


# ── None new_title bypasses guard ─────────────────────────────────────────────

class TestNullNewTitle:
    def test_guard_bypassed_when_new_title_is_absent(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = False
        existing.scraped_title = 'Solo Leveling'
        existing.latest_chapter = 99

        # No 'title' key → sanitize_str returns None → guard is skipped
        scraped_data = {'chapter': 100, 'chapter_url': 'https://site.com/ch/100'}

        _run_upsert(manga, site, scraped_data, existing_entry=existing)

        assert existing.latest_chapter == 100


# ── is_removed entry always skipped ──────────────────────────────────────────

class TestIsRemovedEntry:
    def test_is_removed_entry_never_updated(self):
        manga = _make_manga()
        site = _make_site()

        existing = MagicMock()
        existing.is_removed = True
        existing.latest_chapter = 5

        scraped_data = _scraped(title='Solo Leveling', chapter=100)

        _, mock_mse = _run_upsert(manga, site, scraped_data, existing_entry=existing)

        assert existing.latest_chapter == 5


# ── New entry creation ────────────────────────────────────────────────────────

class TestNewEntryCreation:
    def test_creates_entry_with_scraped_title(self):
        manga = _make_manga()
        site = _make_site()
        scraped_data = _scraped(title='Solo Leveling', chapter=1)

        mock_db, mock_mse = _run_upsert(manga, site, scraped_data, existing_entry=None)

        mock_mse.assert_called_once()
        call_kwargs = mock_mse.call_args[1]
        assert call_kwargs['scraped_title'] == 'Solo Leveling'
        assert call_kwargs['latest_chapter'] == 1
        mock_db.session.add.assert_called_once()

    def test_creates_entry_with_empty_scraped_title_when_missing(self):
        manga = _make_manga()
        site = _make_site()
        scraped_data = {'chapter': 1, 'chapter_url': 'https://site.com/1'}

        mock_db, mock_mse = _run_upsert(manga, site, scraped_data, existing_entry=None)

        # sanitize_str(None) returns '' — falsy, so the guard treats it the same as None
        call_kwargs = mock_mse.call_args[1]
        assert not call_kwargs['scraped_title']
