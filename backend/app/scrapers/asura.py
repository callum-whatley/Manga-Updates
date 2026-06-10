import requests
import re
from bs4 import BeautifulSoup

TIMEOUT = 10
PREMIUM_KEYWORDS = ['premium', 'lock', 'vip', 'paid', 'coin']


def fetch_latest_chapter_asura(series_url: str) -> dict | None:
    """Scrape an AsuraScans series page and return the latest free chapter."""
    try:
        resp = requests.get(series_url, timeout=TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
        return _parse_latest_free_chapter(soup, series_url)
    except Exception as e:
        print(f'[AsuraScans] fetch failed for {series_url}: {e}')
        return None


def _parse_latest_free_chapter(soup: BeautifulSoup, base_url: str) -> dict | None:
    """
    Find the latest chapter that is not behind a premium/lock indicator.
    AsuraScans chapter list items typically have an <a> with the chapter URL
    and a number, plus optional lock icons or classes for premium content.
    """
    chapter_links = soup.select('div.eph-num a, div[class*="chapter"] a')

    for link in chapter_links:
        parent_text = link.get_text(' ', strip=True).lower()
        parent_html = str(link.parent) if link.parent else ''

        if any(kw in parent_text for kw in PREMIUM_KEYWORDS):
            continue
        if any(kw in parent_html.lower() for kw in ['fa-lock', 'premium', 'coin-icon']):
            continue

        href = link.get('href', '')
        if not href:
            continue

        chapter_url = href if href.startswith('http') else base_url.rstrip('/') + '/' + href.lstrip('/')

        chapter_match = re.search(r'(?:chapter|ch)[.\s-]*(\d+\.?\d*)', link.get_text(), re.IGNORECASE)
        if not chapter_match:
            chapter_match = re.search(r'(\d+\.?\d*)', link.get_text())
        if not chapter_match:
            continue

        return {
            'chapter': float(chapter_match.group(1)),
            'chapter_url': chapter_url,
        }

    return None
