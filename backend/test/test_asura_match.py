"""
Tests for AsuraScans scraping + fuzzy matching.

AsuraScans (asurascans.com) migrated to Astro + React in 2025.
The homepage (latest-updates list) is still server-rendered and scrapeable.
Individual series pages now load chapter lists via client-side JS, so
_parse_latest_free_chapter is effectively broken for the live site.

All tests use HTML fixtures — no live network calls.
"""
import pytest
from unittest.mock import MagicMock
from bs4 import BeautifulSoup

from app.scrapers.matcher import _score, _normalise, AUTO_MATCH_THRESHOLD
from app.scrapers.generic import scrape_with_selectors
from app.scrapers.asura import _parse_latest_free_chapter

TITLE = "Omniscient Reader's Viewpoint"
BASE_URL = "https://asurascans.com/"

# ── New CSS selectors for asurascans.com (post-2025 Tailwind/Astro layout) ───
#
# Homepage latest-updates structure:
#   <div class="grid grid-cols-12 gap-2 py-4 px-2 border-b ...">   ← card
#     <a class="col-span-4 ..."><img ...></a>                        ← cover
#     <div class="col-span-8 ...">
#       <a class="font-bold text-base line-clamp-1 ...">Title</a>   ← title
#       <div class="flex flex-col ...">
#         <a href="/comics/{slug}/chapter/{n}">Chapter N</a>        ← latest chapter
#         <a href="...chapter/{n-1}">Chapter N-1</a>
#       </div>
#     </div>
#   </div>
#
# Note: border-[#312f40] contains CSS-selector-special chars; we target the
# container by the non-special classes grid-cols-12 + gap-2 + py-4 instead.

CONTAINER_SEL = "div.grid.grid-cols-12.gap-2.py-4"
TITLE_SEL = "a.font-bold.text-base.line-clamp-1"
COVER_SEL = "a.col-span-4 img"
CHAPTER_SEL = "a[href*='/chapter/']:first-of-type"

# Fixture HTML reflecting the current asurascans.com card structure.
# The third card intentionally omits the chapter link to verify it is skipped.
LATEST_HTML = """\
<html><body>
  <div class="grid grid-cols-12 gap-2 py-4 px-2 border-b border-neutral">
    <a class="col-span-4 overflow-hidden rounded-md group" href="/comics/omniscient-readers-viewpoint">
      <img alt="Omniscient Reader's Viewpoint" class="object-cover rounded-md"
           src="https://cdn.asurascans.com/covers/omniscient.webp">
    </a>
    <div class="col-span-8 flex flex-col min-w-0">
      <a class="font-bold text-base line-clamp-1 mb-2"
         href="/comics/omniscient-readers-viewpoint">
        Omniscient Reader's Viewpoint
      </a>
      <div class="flex flex-col">
        <a class="flex items-center justify-between"
           href="/comics/omniscient-readers-viewpoint/chapter/170">
          <span>Chapter 170</span>
        </a>
        <a class="flex items-center justify-between"
           href="/comics/omniscient-readers-viewpoint/chapter/169">
          <span>Chapter 169</span>
        </a>
      </div>
    </div>
  </div>
  <div class="grid grid-cols-12 gap-2 py-4 px-2 border-b border-neutral">
    <a class="col-span-4 overflow-hidden rounded-md group" href="/comics/solo-leveling">
      <img alt="Solo Leveling" class="object-cover rounded-md"
           src="https://cdn.asurascans.com/covers/solo-leveling.webp">
    </a>
    <div class="col-span-8 flex flex-col min-w-0">
      <a class="font-bold text-base line-clamp-1 mb-2" href="/comics/solo-leveling">
        Solo Leveling
      </a>
      <div class="flex flex-col">
        <a class="flex items-center justify-between"
           href="/comics/solo-leveling/chapter/200">
          <span>Chapter 200</span>
        </a>
      </div>
    </div>
  </div>
  <div class="grid grid-cols-12 gap-2 py-4 px-2 border-b border-neutral">
    <a class="col-span-4 overflow-hidden rounded-md group" href="/comics/no-chapter-manhwa">
      <img alt="No Chapter Manhwa" class="object-cover rounded-md"
           src="https://cdn.asurascans.com/covers/no-chapter.webp">
    </a>
    <div class="col-span-8 flex flex-col min-w-0">
      <a class="font-bold text-base line-clamp-1 mb-2" href="/comics/no-chapter-manhwa">
        No Chapter Manhwa
      </a>
      <!-- intentionally no chapter link — should be skipped by scraper -->
    </div>
  </div>
</body></html>
"""

# Series page fixtures for _parse_latest_free_chapter.
# Note: the live asurascans.com series page now loads chapters via JS
# (CSR), so this function no longer works against the live site.
# These fixtures test the parsing logic in isolation.
SERIES_HTML = """\
<html><body>
  <div class="eph-num">
    <a href="https://asurascans.com/comics/omniscient/chapter/170">Chapter 170</a>
  </div>
  <div class="eph-num">
    <a href="https://asurascans.com/comics/omniscient/chapter/169">Chapter 169</a>
  </div>
</body></html>
"""

SERIES_PREMIUM_HTML = """\
<html><body>
  <div class="eph-num">
    <a href="https://asurascans.com/comics/foo/chapter/10">Chapter 10 premium</a>
  </div>
  <div class="eph-num">
    <a href="https://asurascans.com/comics/foo/chapter/9">Chapter 9</a>
  </div>
</body></html>
"""


# ── Matcher unit tests ────────────────────────────────────────────────────────

def test_normalise_title():
    assert _normalise(TITLE) == "omniscient readers viewpoint"


def test_fuzzy_score_exact_match():
    assert _score(TITLE, TITLE) == 100.0


@pytest.mark.parametrize("variant,expected_min", [
    ("Omniscient Reader’s Viewpoint", 95),   # curly apostrophe
    ("Omniscient Readers Viewpoint", 95),           # missing apostrophe
    ("Omniscient Reader's Viewpoint (Official)", 90),  # extra subtitle
    ("Omniscient Reader", 70),                      # truncated
])
def test_fuzzy_score_variants(variant, expected_min):
    score = _score(TITLE, variant)
    assert score >= expected_min, (
        f"Score {score:.1f} for {variant!r} below expected min {expected_min}"
    )


# ── scrape_with_selectors (generic scraper, new asurascans.com layout) ────────

@pytest.fixture
def mock_latest_page(monkeypatch):
    """Patch requests.get to return LATEST_HTML without any network call."""
    import requests as requests_mod
    mock_resp = MagicMock()
    mock_resp.content = LATEST_HTML.encode()
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setattr(requests_mod, "get", MagicMock(return_value=mock_resp))


def _scrape():
    return scrape_with_selectors(
        url=BASE_URL,
        title_selector=TITLE_SEL,
        cover_selector=COVER_SEL,
        chapter_link_selector=CHAPTER_SEL,
        container_selector=CONTAINER_SEL,
    )


def test_scraper_skips_container_without_chapter_link(mock_latest_page):
    """Container missing a chapter link is silently dropped; two valid items remain."""
    results = _scrape()
    assert len(results) == 2


def test_scraper_extracts_title(mock_latest_page):
    results = _scrape()
    titles = [r["title"] for r in results]
    assert any("Omniscient" in t for t in titles)


def test_scraper_extracts_latest_chapter_only(mock_latest_page):
    """Only the first (latest) chapter link per card is returned."""
    results = _scrape()
    omniscient = next(r for r in results if "Omniscient" in r["title"])
    assert omniscient["chapter"] == 170.0


def test_scraper_extracts_chapter_url(mock_latest_page):
    results = _scrape()
    omniscient = next(r for r in results if "Omniscient" in r["title"])
    assert "/chapter/170" in omniscient["chapter_url"]


def test_scraper_extracts_cover_url(mock_latest_page):
    results = _scrape()
    assert all(r["cover_url"] for r in results)


def test_scraper_returns_empty_on_fetch_failure(monkeypatch):
    import requests as requests_mod
    monkeypatch.setattr(requests_mod, "get", MagicMock(side_effect=Exception("timeout")))
    assert _scrape() == []


def test_scraped_title_fuzzy_matches_above_threshold(mock_latest_page):
    """Scraped title scores >= AUTO_MATCH_THRESHOLD against the reference title."""
    results = _scrape()
    best = max(_score(TITLE, r["title"]) for r in results)
    assert best >= AUTO_MATCH_THRESHOLD, (
        f"Best fuzzy score {best:.1f} below AUTO_MATCH_THRESHOLD ({AUTO_MATCH_THRESHOLD})"
    )


# ── _parse_latest_free_chapter (asura.py) ────────────────────────────────────

def test_parse_returns_latest_chapter():
    soup = BeautifulSoup(SERIES_HTML, "html.parser")
    result = _parse_latest_free_chapter(soup, "https://asurascans.com/comics/omniscient")
    assert result is not None
    assert result["chapter"] == 170.0
    assert "/chapter/170" in result["chapter_url"]


def test_parse_skips_premium_chapter():
    soup = BeautifulSoup(SERIES_PREMIUM_HTML, "html.parser")
    result = _parse_latest_free_chapter(soup, "https://asurascans.com/comics/foo")
    assert result is not None
    assert result["chapter"] == 9.0


def test_parse_returns_none_on_empty_html():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    result = _parse_latest_free_chapter(soup, "https://asurascans.com/comics/foo")
    assert result is None
