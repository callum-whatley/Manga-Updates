import re
import requests
from flask import current_app

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Referer': 'https://fanfox.net/',
}


def _decode_packer(packed_js: str) -> str:
    """Decode Dean Edwards p,a,c,k,e,r packed JavaScript."""
    m = re.search(r"\}\('(.*?)',\s*(\d+),\s*\d+,\s*'(.*?)'\.split\(", packed_js, re.DOTALL)
    if not m:
        return ''
    payload, base_str, kw_str = m.group(1), m.group(2), m.group(3)
    base = int(base_str)
    keywords = kw_str.split('|')

    def to_int(s):
        n = 0
        for c in s:
            n *= base
            if '0' <= c <= '9':
                n += ord(c) - ord('0')
            elif 'a' <= c <= 'z':
                n += ord(c) - ord('a') + 10
        return n

    def replace_word(m):
        n = to_int(m.group(0))
        if n < len(keywords) and keywords[n]:
            return keywords[n]
        return m.group(0)

    return re.sub(r'\b\w+\b', replace_word, payload)


def fetch_chapter_images(chapter_url: str) -> list[str]:
    """
    Fetch all chapter images from a Fanfox chapter URL.
    Uses chapterfun.ashx API to get per-page signed image URLs, then
    decodes the packed JS responses. Calls odd pages only for efficiency.
    """
    try:
        resp = requests.get(chapter_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        current_app.logger.error('[Fanfox] failed to fetch chapter page %s: %s', chapter_url, e)
        return []

    chapterid_m = re.search(r'var chapterid\s*=\s*(\d+)', html)
    imagecount_m = re.search(r'var imagecount\s*=\s*(\d+)', html)
    if not chapterid_m or not imagecount_m:
        current_app.logger.error('[Fanfox] could not find chapterid/imagecount in %s', chapter_url)
        return []

    chapterid = chapterid_m.group(1)
    imagecount = int(imagecount_m.group(1))

    seen: dict[int, str] = {}

    for page in range(1, imagecount + 1, 2):
        try:
            api_resp = requests.get(
                'https://fanfox.net/chapterfun.ashx',
                params={'cid': chapterid, 'page': page, 'key': ''},
                headers=HEADERS,
                timeout=10,
            )
            api_resp.raise_for_status()
            decoded = _decode_packer(api_resp.text)

            pix_m = re.search(r'var pix\s*=\s*"([^"]+)"', decoded)
            pvalue_items = re.findall(r'"(/[^"]+\.(?:jpg|webp|png)\?[^"]*)"', decoded)

            if pix_m and pvalue_items:
                pix = pix_m.group(1)
                for i, item in enumerate(pvalue_items):
                    pg_num = page + i
                    seen[pg_num] = f'https:{pix}{item}'
        except Exception as e:
            current_app.logger.warning('[Fanfox] page %d fetch failed: %s', page, e)

    return [seen[k] for k in sorted(seen.keys())]


def get_chapter_url(latest_chapter_url: str, chapter_num: float) -> str | None:
    """Look up the correct chapter URL for chapter_num from the Fanfox manga page."""
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup

    m = re.search(r'fanfox\.net/manga/([^/]+)/', latest_chapter_url)
    if not m:
        return None
    slug = m.group(1)
    if not re.fullmatch(r'[a-zA-Z0-9_\-]+', slug):
        return None
    manga_page_url = f'https://fanfox.net/manga/{slug}/'
    chapter_str = str(int(chapter_num)) if chapter_num == int(chapter_num) else str(chapter_num)

    def _find_in_html(html: str) -> str | None:
        soup = BeautifulSoup(html, 'html.parser')
        # Chapter URLs include an optional volume segment and zero-padded chapter
        # number, e.g. /manga/toriko/v01/c001/1.html or /manga/toriko/vTBD/c396/1.html
        pattern = re.compile(rf'/manga/{re.escape(slug)}/(?:v[^/]+/)?c(\d+\.?\d*)/')
        for a in soup.select(f'a[href*="/manga/{slug}/"]'):
            href = a.get('href', '')
            m = pattern.search(href)
            if m and float(m.group(1)) == chapter_num:
                return urljoin('https://fanfox.net', href)
        return None

    # Try regular requests first — Fanfox serves chapter lists SSR
    try:
        resp = requests.get(manga_page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        result = _find_in_html(resp.text)
        if result:
            return result
    except Exception as e:
        current_app.logger.warning('[Fanfox] requests failed for %s: %s', manga_page_url, e)

    # Fall back to Playwright for JS-rendered content
    from .browser import scrape_page_html
    html = scrape_page_html(manga_page_url)
    if html:
        result = _find_in_html(html)
        if result:
            return result

    current_app.logger.error('[Fanfox] could not find URL for %s ch.%s', slug, chapter_str)
    return None
