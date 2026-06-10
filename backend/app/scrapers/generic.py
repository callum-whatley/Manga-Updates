import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TIMEOUT = 15
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
}


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        print(f'[generic] fetch failed for {url}: {e}')
        return None


def _extract_chapter_number(text: str, href: str = '') -> float:
    # Try URL first — more reliable than link text (e.g. /chapter/76)
    url_match = re.search(r'/chapter[s]?/(\d+\.?\d*)', href, re.IGNORECASE)
    if url_match:
        return float(url_match.group(1))
    match = re.search(r'(\d+\.?\d*)', text)
    return float(match.group(1)) if match else 0.0


def _abs_url(href: str, base_url: str) -> str:
    if not href:
        return ''
    return urljoin(base_url, href)


def _extract_from_container(container, title_sel: str, cover_sel: str | None,
                             chapter_sel: str, base_url: str) -> dict | None:
    title_el = container.select_one(title_sel)
    link_el = container.select_one(chapter_sel)
    if not title_el or not link_el:
        return None

    title_text = title_el.get_text(strip=True)
    href = link_el.get('href', '')
    chapter_url = _abs_url(href, base_url)
    chapter_num = _extract_chapter_number(link_el.get_text(strip=True), href)

    cover_url = None
    if cover_sel:
        cover_el = container.select_one(cover_sel)
        if cover_el:
            raw = cover_el.get('src') or cover_el.get('data-src') or cover_el.get('data-lazy-src')
            if raw:
                cover_url = _abs_url(raw, base_url)

    if title_text and chapter_url:
        return {'title': title_text, 'cover_url': cover_url,
                'chapter': chapter_num, 'chapter_url': chapter_url}
    return None


def scrape_with_selectors(
    url: str,
    title_selector: str,
    cover_selector: str | None,
    chapter_link_selector: str,
    container_selector: str | None = None,
    limit: int = 100,
) -> list[dict]:
    soup = _fetch(url)
    if not soup:
        return []

    results = []

    if container_selector:
        # Container-based: selectors are relative to each card — guaranteed alignment
        for container in soup.select(container_selector):
            item = _extract_from_container(container, title_selector, cover_selector,
                                           chapter_link_selector, url)
            if item:
                results.append(item)
            if len(results) >= limit:
                break
    else:
        # Positional zip fallback
        titles = soup.select(title_selector)
        chapter_links = soup.select(chapter_link_selector)
        covers = soup.select(cover_selector) if cover_selector else []

        for i, (title_el, link_el) in enumerate(zip(titles, chapter_links)):
            title_text = title_el.get_text(strip=True)
            href = link_el.get('href', '')
            chapter_url = _abs_url(href, url)
            chapter_num = _extract_chapter_number(link_el.get_text(strip=True), href)

            cover_url = None
            if covers and i < len(covers):
                cover_el = covers[i]
                raw = cover_el.get('src') or cover_el.get('data-src') or cover_el.get('data-lazy-src')
                if raw:
                    cover_url = _abs_url(raw, url)

            if title_text and chapter_url:
                results.append({'title': title_text, 'cover_url': cover_url,
                                 'chapter': chapter_num, 'chapter_url': chapter_url})
            if len(results) >= limit:
                break

    return results


def test_selectors(
    url: str,
    title_selector: str,
    cover_selector: str | None,
    chapter_link_selector: str,
    container_selector: str | None = None,
    preview_count: int = 8,
) -> dict:
    soup = _fetch(url)
    if not soup:
        return {'ok': False, 'error': 'Failed to fetch the page', 'results': []}

    if container_selector:
        containers = soup.select(container_selector)
        titles = [c.select_one(title_selector) for c in containers]
        titles = [t for t in titles if t]
        chapter_links = [c.select_one(chapter_link_selector) for c in containers]
        chapter_links = [c for c in chapter_links if c]
        covers = [c.select_one(cover_selector) for c in containers] if cover_selector else []
        covers = [c for c in covers if c]
    else:
        titles = soup.select(title_selector)
        chapter_links = soup.select(chapter_link_selector)
        covers = soup.select(cover_selector) if cover_selector else []

    results = scrape_with_selectors(url, title_selector, cover_selector,
                                    chapter_link_selector, container_selector,
                                    limit=preview_count)
    return {
        'ok': bool(results),
        'counts': {
            'titles': len(titles),
            'chapterLinks': len(chapter_links),
            'covers': len(covers),
        },
        'results': results[:preview_count],
    }
