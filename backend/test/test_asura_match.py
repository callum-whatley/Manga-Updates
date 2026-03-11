"""
Diagnostic tests for AsuraScans scraping + fuzzy matching of
"Omniscient Reader's Viewpoint".

Run with:
    pytest test/test_asura_match.py -s
"""

import requests
import pytest
from bs4 import BeautifulSoup

from app.scrapers.matcher import _score, _normalise, AUTO_MATCH_THRESHOLD
from app.scrapers.generic import scrape_with_selectors

TITLE = "Omniscient Reader's Viewpoint"
ASURA_URL = "https://asuracomic.net/"   # homepage — latest-updates list
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── Matcher unit tests ────────────────────────────────────────────────────────

def test_normalise_title():
    assert _normalise(TITLE) == "omniscient readers viewpoint"


def test_fuzzy_score_exact_match():
    assert _score(TITLE, TITLE) == 100.0


@pytest.mark.parametrize("variant,expected_min", [
    # curly apostrophe
    ("Omniscient Reader\u2019s Viewpoint", 95),
    # missing apostrophe entirely
    ("Omniscient Readers Viewpoint", 95),
    # extra subtitle
    ("Omniscient Reader's Viewpoint (Official)", 90),
    # truncated
    ("Omniscient Reader", 70),
])
def test_fuzzy_score_variants(variant, expected_min):
    score = _score(TITLE, variant)
    print(f"\n  {variant!r} → {score:.1f}")
    assert score >= expected_min, (
        f"Score {score:.1f} for {variant!r} below expected min {expected_min}"
    )


# ── Live scrape tests ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def asura_html():
    resp = requests.get(ASURA_URL, timeout=15, headers=HEADERS)
    resp.raise_for_status()
    return resp.text


def test_title_present_in_raw_html(asura_html):
    """Confirm the title is present in the HTML at all."""
    assert "Omniscient" in asura_html, "Title not found in raw HTML"


def test_title_extractable_by_beautifulsoup(asura_html):
    """Confirm BeautifulSoup can find the title text node."""
    soup = BeautifulSoup(asura_html, "html.parser")
    matches = soup.find_all(string=lambda t: t and "Omniscient" in t)
    print(f"\n  BS4 string matches: {[str(m).strip() for m in matches]}")
    assert matches, "BeautifulSoup found no text nodes containing 'Omniscient'"


def test_missing_containers():
    """Identify which containers are dropped and why."""
    import requests
    from bs4 import BeautifulSoup
    resp = requests.get(ASURA_URL, timeout=15, headers=HEADERS)
    soup = BeautifulSoup(resp.text, "html.parser")

    CONTAINER_SEL = "div.grid.grid-rows-1.grid-cols-12.m-2"
    TITLE_SEL = "span.font-medium > a"
    CHAPTER_SEL = "span.flex-1.inline-block.mt-1:first-child div.flex.text-sm > a"

    containers = soup.select(CONTAINER_SEL)
    print(f"\n  Total containers: {len(containers)}")

    dropped = []
    for i, c in enumerate(containers):
        title_el = c.select_one(TITLE_SEL)
        chapter_el = c.select_one(CHAPTER_SEL)
        if not title_el or not chapter_el:
            title_text = title_el.get_text(strip=True) if title_el else "(no title)"
            reason = "missing chapter link" if title_el else "missing title"
            dropped.append((i + 1, title_text, reason))

    print(f"  Dropped containers ({len(dropped)}):")
    for pos, title, reason in dropped:
        print(f"    #{pos}: {title!r} — {reason}")

    assert not dropped, f"{len(dropped)} containers dropped"


def test_scraper_extracts_title():
    """
    Run scrape_with_selectors with the actual configured selectors and confirm
    'Omniscient Reader's Viewpoint' appears with a score >= AUTO_MATCH_THRESHOLD.
    """
    results = scrape_with_selectors(
        url=ASURA_URL,
        title_selector='span.font-medium > a',
        cover_selector='img.rounded-md.object-cover',
        chapter_link_selector='span.flex-1.inline-block.mt-1:first-child div.flex.text-sm > a',
        container_selector='div.grid.grid-rows-1.grid-cols-12.m-2',
    )

    print(f"\n  scrape_with_selectors returned {len(results)} items")
    if results:
        print(f"  First 5 titles: {[r['title'] for r in results[:5]]}")

    scores = [(r["title"], _score(TITLE, r["title"])) for r in results]
    scores.sort(key=lambda x: -x[1])

    print(f"\n  Top 5 fuzzy matches for {TITLE!r}:")
    for title, score in scores[:5]:
        print(f"    {score:.1f}  {title!r}  ch={next((r['chapter'] for r in results if r['title'] == title), '?')}")

    assert results, "scrape_with_selectors returned no results — selectors may be wrong"

    best_title, best_score = scores[0]
    assert best_score >= AUTO_MATCH_THRESHOLD, (
        f"Best match {best_title!r} scored {best_score:.1f}, "
        f"below AUTO_MATCH_THRESHOLD ({AUTO_MATCH_THRESHOLD})"
    )
