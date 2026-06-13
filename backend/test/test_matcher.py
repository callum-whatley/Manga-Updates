"""
Unit tests for app/scrapers/matcher.py

Covers:
  - Basic auto-match (score >= AUTO_MATCH_THRESHOLD → in 'auto')
  - Suggest match (SUGGEST_THRESHOLD <= score < AUTO_MATCH_THRESHOLD → in 'suggest')
  - No match (score < SUGGEST_THRESHOLD → neither)
  - Bipartite exclusivity: one scraped item → at most one manga
  - One manga → at most one scraped item
  - Empty scraped list
  - Empty library
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.scrapers.matcher import (
    AUTO_MATCH_THRESHOLD,
    SUGGEST_THRESHOLD,
    match_scraped_to_library,
)


def _manga(title: str, id_: int = 1) -> SimpleNamespace:
    """Minimal stand-in for a Manga ORM object."""
    return SimpleNamespace(title=title, id=id_)


def _scraped(title: str) -> dict:
    return {'title': title, 'chapter': 1, 'chapter_url': 'https://example.com/1'}


# ── helpers ───────────────────────────────────────────────────────────────────

def _force_score(value: float):
    """Context manager that patches _score to always return `value`."""
    return patch('app.scrapers.matcher._score', return_value=value)


# ── auto match ────────────────────────────────────────────────────────────────

class TestAutoMatch:
    def test_exact_title_goes_to_auto(self):
        manga = _manga('One Piece')
        scraped = [_scraped('One Piece')]
        result = match_scraped_to_library(scraped, [manga])
        assert len(result['auto']) == 1
        assert len(result['suggest']) == 0
        assert result['auto'][0]['manga'] is manga
        assert result['auto'][0]['scraped'] is scraped[0]

    def test_high_score_forced_to_auto(self):
        manga = _manga('Some Title')
        scraped = [_scraped('Some Title')]
        with _force_score(AUTO_MATCH_THRESHOLD):
            result = match_scraped_to_library(scraped, [manga])
        assert len(result['auto']) == 1
        assert result['auto'][0]['score'] == AUTO_MATCH_THRESHOLD

    def test_score_just_above_auto_threshold(self):
        manga = _manga('X')
        scraped = [_scraped('X')]
        with _force_score(AUTO_MATCH_THRESHOLD + 1):
            result = match_scraped_to_library(scraped, [manga])
        assert len(result['auto']) == 1
        assert len(result['suggest']) == 0


# ── suggest match ─────────────────────────────────────────────────────────────

class TestSuggestMatch:
    def test_mid_score_goes_to_suggest(self):
        manga = _manga('Some Title')
        scraped = [_scraped('Some Other Title')]
        mid_score = (SUGGEST_THRESHOLD + AUTO_MATCH_THRESHOLD) // 2
        with _force_score(mid_score):
            result = match_scraped_to_library(scraped, [manga])
        assert len(result['suggest']) == 1
        assert len(result['auto']) == 0
        assert result['suggest'][0]['manga'] is manga

    def test_score_at_suggest_threshold_goes_to_suggest(self):
        manga = _manga('X')
        scraped = [_scraped('X')]
        with _force_score(SUGGEST_THRESHOLD):
            result = match_scraped_to_library(scraped, [manga])
        assert len(result['suggest']) == 1
        assert len(result['auto']) == 0

    def test_score_just_below_auto_threshold_goes_to_suggest(self):
        manga = _manga('X')
        scraped = [_scraped('X')]
        with _force_score(AUTO_MATCH_THRESHOLD - 1):
            result = match_scraped_to_library(scraped, [manga])
        assert len(result['suggest']) == 1
        assert len(result['auto']) == 0


# ── no match ──────────────────────────────────────────────────────────────────

class TestNoMatch:
    def test_low_score_produces_no_match(self):
        manga = _manga('One Piece')
        scraped = [_scraped('Completely Different')]
        with _force_score(SUGGEST_THRESHOLD - 1):
            result = match_scraped_to_library(scraped, [manga])
        assert len(result['auto']) == 0
        assert len(result['suggest']) == 0

    def test_score_zero_produces_no_match(self):
        manga = _manga('X')
        scraped = [_scraped('Y')]
        with _force_score(0):
            result = match_scraped_to_library(scraped, [manga])
        assert result == {'auto': [], 'suggest': []}


# ── bipartite exclusivity ─────────────────────────────────────────────────────

class TestBipartiteExclusivity:
    def test_single_scraped_item_assigned_to_highest_scorer_only(self):
        """
        Two manga both score above AUTO_MATCH_THRESHOLD against the same scraped item.
        Only the higher scorer should be assigned; the lower scorer gets nothing.
        """
        manga_a = _manga('Solo Leveling', id_=1)
        manga_b = _manga('Solo Levelling', id_=2)
        shared_item = _scraped('Solo Leveling')

        # Patch _score so manga_a scores 95, manga_b scores 90 — both above AUTO threshold.
        def fake_score(title_a: str, title_b: str) -> float:
            if 'Solo Leveling' == title_a:  # normalised title for manga_a
                return 95.0
            return 90.0  # manga_b

        with patch('app.scrapers.matcher._score', side_effect=fake_score):
            result = match_scraped_to_library([shared_item], [manga_a, manga_b])

        all_matched = result['auto'] + result['suggest']
        assert len(all_matched) == 1, (
            "Only one manga should receive the shared scraped item"
        )
        assert all_matched[0]['manga'] is manga_a

    def test_one_scraped_item_per_manga(self):
        """
        One manga, two scraped items both above threshold — only the best one is assigned.
        """
        manga = _manga('Berserk')
        item_a = _scraped('Berserk')
        item_b = _scraped('Berserk (2016)')

        scores = {
            id(item_a): 98.0,
            id(item_b): 85.0,
        }

        # _score is called as _score(manga.title, item['title']).
        # We need to differentiate by which scraped item dict Python is currently
        # evaluating; we do so via the second argument's value.
        def fake_score(a: str, b: str) -> float:
            if 'berserk 2016' in b.lower().replace('(', '').replace(')', ''):
                return 85.0
            return 98.0

        with patch('app.scrapers.matcher._score', side_effect=fake_score):
            result = match_scraped_to_library([item_a, item_b], [manga])

        all_matched = result['auto'] + result['suggest']
        assert len(all_matched) == 1
        assert all_matched[0]['scraped'] is item_a

    def test_two_manga_two_scraped_items_no_crossover(self):
        """
        Two manga, two distinct scraped items — each manga should get its own best match,
        not both fight over the same item.
        """
        manga_a = _manga('One Piece', id_=1)
        manga_b = _manga('Naruto', id_=2)
        item_one_piece = _scraped('One Piece')
        item_naruto = _scraped('Naruto')

        # Realistic exact-match scores: each manga scores perfectly against its own item.
        result = match_scraped_to_library(
            [item_one_piece, item_naruto],
            [manga_a, manga_b],
        )

        all_matched = result['auto'] + result['suggest']
        assert len(all_matched) == 2
        matched_manga = [m['manga'] for m in all_matched]
        assert manga_a in matched_manga
        assert manga_b in matched_manga


# ── edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_scraped_list_returns_empty(self):
        manga = _manga('One Piece')
        result = match_scraped_to_library([], [manga])
        assert result == {'auto': [], 'suggest': []}

    def test_empty_library_returns_empty(self):
        scraped = [_scraped('One Piece')]
        result = match_scraped_to_library(scraped, [])
        assert result == {'auto': [], 'suggest': []}

    def test_both_empty_returns_empty(self):
        result = match_scraped_to_library([], [])
        assert result == {'auto': [], 'suggest': []}
