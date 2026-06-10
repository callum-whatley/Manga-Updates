import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from flask import current_app

from .generic import scrape_with_selectors, _extract_from_container, _extract_chapter_number, _abs_url
from .matcher import _score, AUTO_MATCH_THRESHOLD
from ..api.sanitize import validate_external_url

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}


def search_site(site, title: str) -> list[dict]:
    """Search a site for a specific manga title. Returns [{title, cover_url, chapter, chapter_url}]."""
    if not site.search_url_template:
        return []
    search_url = site.search_url_template.replace('{title}', quote_plus(title))
    if not validate_external_url(search_url):
        current_app.logger.warning('[search] rejected search_url: %s', search_url)
        return []

    if 'yomimanga.com' in search_url:
        return _search_yomimanga(title, search_url)
    if 'asurascans.com' in search_url:
        return _search_with_browser(site, search_url)
    if 'fanfox.net' in search_url:
        return _search_fanfox(search_url)
    # Default: SSR search page, reuse site's existing selectors (VortexScans)
    return scrape_with_selectors(
        url=search_url,
        title_selector=site.title_selector,
        cover_selector=site.cover_selector,
        chapter_link_selector=site.chapter_link_selector,
        container_selector=site.container_selector,
    )


def _search_yomimanga(title: str, search_url: str) -> list[dict]:
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        results = resp.json()
        if not isinstance(results, list):
            raise ValueError('expected list response')
    except Exception as e:
        current_app.logger.error('[search] YomiManga search failed: %s', e)
        return []

    best, best_score, best_slug = None, 0, ''
    for item in results:
        if not isinstance(item, dict):
            continue
        item_title = item.get('title', '')
        score = _score(title, item_title)
        if score > best_score:
            best_score, best = score, item
            best_slug = item.get('title_slug', '')

    if best_score < AUTO_MATCH_THRESHOLD or not best_slug:
        return []

    # Validate the manga page URL before navigating with Playwright
    safe_slug = validate_external_url(best_slug)
    if not safe_slug:
        current_app.logger.warning('[search] YomiManga: rejected title_slug %s', best_slug)
        return []

    from .browser import scrape_page_html
    html = scrape_page_html(safe_slug)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    link = soup.select_one('a[href*="/chapter/"]')
    if not link:
        return []

    href = link.get('href', '')
    chapter_url = _abs_url(href, safe_slug)
    chapter_num = _extract_chapter_number(link.get_text(strip=True), href)

    return [{'title': best.get('title', ''), 'cover_url': None, 'chapter': chapter_num, 'chapter_url': chapter_url}]


def _search_fanfox(search_url: str) -> list[dict]:
    return scrape_with_selectors(
        url=search_url,
        container_selector='ul.manga-list-4-list > li',
        title_selector='p.manga-list-4-item-title a',
        chapter_link_selector='p.manga-list-4-item-tip a[href*=".html"]',
        cover_selector='img.manga-list-4-cover',
    )


def _search_with_browser(site, search_url: str) -> list[dict]:
    from .browser import scrape_page_html
    html = scrape_page_html(search_url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    results = []
    if site.container_selector:
        for container in soup.select(site.container_selector):
            item = _extract_from_container(
                container,
                site.title_selector,
                site.cover_selector,
                site.chapter_link_selector,
                search_url,
            )
            if item:
                results.append(item)
    return results
