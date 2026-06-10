import json
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

    current_app.logger.info('[search] searching %s for "%s" at %s', site.name, title, search_url)

    if 'yomimanga.com' in search_url:
        results = _search_yomimanga(title, search_url)
    elif 'asurascans.com' in search_url or 'asuracomic.net' in search_url:
        results = _search_with_browser(site, search_url)
    elif 'fanfox.net' in search_url:
        results = _search_fanfox(search_url)
    else:
        results = scrape_with_selectors(
            url=search_url,
            title_selector=site.title_selector,
            cover_selector=site.cover_selector,
            chapter_link_selector=site.chapter_link_selector,
            container_selector=site.container_selector,
        )

    current_app.logger.info('[search] %s returned %d results for "%s"', site.name, len(results), title)
    return results


YOMI_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://yomimanga.com/',
    'Origin': 'https://yomimanga.com',
}


def _search_yomimanga(title: str, search_url: str) -> list[dict]:
    try:
        # Try bare request first; fall back to browser-based fetch to bypass Cloudflare
        raw = ''
        try:
            resp = requests.get(search_url, headers=YOMI_HEADERS, timeout=10)
            resp.raise_for_status()
            if resp.text and resp.text.strip():
                raw = resp.text
        except Exception:
            pass
        if not raw:
            from .browser import fetch_json_in_browser
            raw = fetch_json_in_browser(search_url)
        if not raw or not raw.strip():
            current_app.logger.warning('[search] YomiManga returned empty response for %s', search_url)
            return []
        current_app.logger.warning('[search] YomiManga raw response (first 300 chars): %s', raw[:300])
        results = json.loads(raw)
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
        current_app.logger.warning('[search] browser scrape returned empty for %s', search_url)
        return []
    current_app.logger.info('[search] browser scrape got %d chars for %s', len(html), search_url)

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
