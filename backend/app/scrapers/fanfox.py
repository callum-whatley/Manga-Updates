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
