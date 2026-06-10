from datetime import timedelta
from flask import Blueprint, jsonify, request, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from urllib.parse import urljoin
import json
import re
import requests
from bs4 import BeautifulSoup

from ..models import ScraperSite
from .sanitize import validate_external_url
from .scraper import PROXY_HEADERS

bp = Blueprint('reader', __name__)

def _extract_next_data_images(soup: BeautifulSoup) -> list[str]:
    """Parse __NEXT_DATA__ JSON (Next.js Pages Router) and collect image URLs."""
    tag = soup.find('script', {'id': '__NEXT_DATA__'})
    if not tag:
        return []
    try:
        data = json.loads(tag.string or '')
    except (json.JSONDecodeError, TypeError):
        return []

    image_re = re.compile(r'https?://\S+\.(?:jpg|jpeg|png|webp|gif|avif)(?:\?[^\s"\']*)?', re.IGNORECASE)
    seen: set[str] = set()
    results: list[str] = []

    def _walk(node):
        if isinstance(node, str):
            for url in image_re.findall(node):
                if url not in seen:
                    seen.add(url)
                    results.append(url)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    return results


def _extract_regex_images(html: str, pattern: str) -> list[str]:
    """Find all non-overlapping matches of `pattern` in the raw HTML, deduplicated and sorted."""
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
        seen: set[str] = set()
        results: list[str] = []
        for match in compiled.finditer(html):
            url = match.group(0)
            if url not in seen:
                seen.add(url)
                results.append(url)
        # Sort by the first number found in the filename (e.g. 00-optimized.webp → 0)
        def _page_num(url: str) -> int:
            filename = url.rsplit('/', 1)[-1]
            nums = re.findall(r'\d+', filename)
            return int(nums[0]) if nums else 0
        results.sort(key=_page_num)
        return results
    except re.error:
        return []


def _extract_css_images(soup: BeautifulSoup, selector: str, base_url: str) -> list[str]:
    images = []
    for el in soup.select(selector):
        raw = el.get('src') or el.get('data-src') or el.get('data-lazy-src')
        if raw:
            images.append(urljoin(base_url, raw))
    return images


def _fetch_mangadex_athome_images(chapter_url: str) -> list[str]:
    """Use MangaDex /at-home/server API to get full-quality chapter page URLs."""
    match = re.search(r'/chapter/([a-f0-9-]+)', chapter_url)
    if not match:
        return []
    chapter_id = match.group(1)
    try:
        resp = requests.get(
            f'https://api.mangadex.org/at-home/server/{chapter_id}',
            timeout=15,
        )
        resp.raise_for_status()
        j = resp.json()
        base = j['baseUrl']
        h = j['chapter']['hash']
        return [f'{base}/data/{h}/{p}' for p in j['chapter']['data']]
    except Exception as e:
        current_app.logger.error('mangadex_athome failed: %s', e)
        return []


@bp.get('/mangadex-chapter')
@jwt_required()
def mangadex_chapter():
    from ..models import Manga, UserManga
    from ..scrapers.mangadex import _get_chapter_url_by_number

    manga_id_raw = request.args.get('manga_id', '').strip()
    chapter_raw = request.args.get('chapter', '').strip()

    if not manga_id_raw or not chapter_raw:
        return jsonify({'error': 'manga_id and chapter are required'}), 400

    try:
        manga_id_int = int(manga_id_raw)
        chapter_float = float(chapter_raw)
    except ValueError:
        return jsonify({'error': 'Invalid parameters'}), 400

    user_id = int(get_jwt_identity())
    if not UserManga.query.filter_by(user_id=user_id, manga_id=manga_id_int).first():
        return jsonify({'error': 'Not found'}), 404

    manga_obj = Manga.query.get_or_404(manga_id_int)
    if not manga_obj.mangadex_id:
        return jsonify({'error': 'No MangaDex ID linked to this manga'}), 404

    if chapter_float < 0 or chapter_float > 10000:
        return jsonify({'error': 'chapter out of range'}), 400

    chapter_url = _get_chapter_url_by_number(manga_obj.mangadex_id, chapter_float)
    if not chapter_url:
        return jsonify({'error': f'Chapter {chapter_raw} not found on MangaDex'}), 404

    validated_url = validate_external_url(chapter_url)
    if not validated_url:
        return jsonify({'error': 'Invalid chapter URL returned from MangaDex'}), 502

    return jsonify({'chapter_url': validated_url})


@bp.get('/images')
@jwt_required()
def get_images():
    url = validate_external_url(request.args.get('url', '').strip())
    site_id_raw = request.args.get('site_id', '').strip()

    if not url:
        return jsonify({'error': 'A valid external url parameter is required'}), 400
    if not site_id_raw:
        return jsonify({'error': 'site_id parameter is required'}), 400

    try:
        site_id = int(site_id_raw)
    except ValueError:
        return jsonify({'error': 'site_id must be an integer'}), 400

    site = ScraperSite.query.get_or_404(site_id)
    if not site.chapter_image_selector:
        return jsonify({'error': 'This site has no chapter image selector configured'}), 400

    sel = site.chapter_image_selector

    if sel.startswith('mangadex_athome:'):
        images = _fetch_mangadex_athome_images(url)
        return jsonify({'images': images})

    if sel.startswith('fanfox:'):
        from ..scrapers.fanfox import fetch_chapter_images
        images = fetch_chapter_images(url)
        return jsonify({'images': images})

    # Browser-rendered extraction — skip requests.get entirely
    if sel.startswith('browser:'):
        from ..scrapers.browser import scrape_chapter_images
        images = scrape_chapter_images(url, sel[8:])
        return jsonify({'images': images})

    try:
        resp = requests.get(url, timeout=15, headers=PROXY_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        current_app.logger.error('get_images failed: %s', e)
        return jsonify({'error': 'Failed to fetch chapter page'}), 502

    if sel == '__NEXT_DATA__':
        images = _extract_next_data_images(soup)
    elif sel.startswith('regex:'):
        images = _extract_regex_images(resp.text, sel[6:])
    else:
        images = _extract_css_images(soup, sel, url)

    return jsonify({'images': images})


@bp.get('/image-token')
@jwt_required()
def image_token():
    token = create_access_token(
        identity=get_jwt_identity(),
        expires_delta=timedelta(minutes=5),
        additional_claims={'t': 'img'},
    )
    return jsonify({'token': token})


_SAFE_IMAGE_TYPES = frozenset({
    'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif',
})


@bp.get('/proxy-image')
def proxy_image():
    from flask_jwt_extended import decode_token
    url_token = request.args.get('token', '').strip()
    auth_header = request.headers.get('Authorization', '')
    header_token = auth_header[7:] if auth_header.startswith('Bearer ') else ''

    if url_token:
        try:
            claims = decode_token(url_token)
        except Exception:
            return jsonify({'error': 'Invalid or expired token'}), 401
        if claims.get('t') != 'img':
            return jsonify({'error': 'Invalid token type'}), 401
    elif header_token:
        try:
            decode_token(header_token)
        except Exception:
            return jsonify({'error': 'Invalid or expired token'}), 401
    else:
        return jsonify({'error': 'Authentication required'}), 401

    url = validate_external_url(request.args.get('url', '').strip())
    if not url:
        return jsonify({'error': 'A valid external url parameter is required'}), 400

    from urllib.parse import urlparse
    req_headers = dict(PROXY_HEADERS)
    hostname = urlparse(url).hostname or ''
    if 'mangadex.network' in hostname:
        req_headers['Referer'] = 'https://mangadex.org'
    elif 'mangafox.me' in hostname or 'fanfox.net' in hostname:
        req_headers['Referer'] = 'https://fanfox.net/'

    try:
        resp = requests.get(url, stream=True, timeout=15, headers=req_headers, allow_redirects=False)
        if resp.is_redirect:
            current_app.logger.warning('proxy_image: redirect rejected for %s', url)
            return jsonify({'error': 'Failed to fetch upstream image'}), 502
        resp.raise_for_status()
    except Exception as e:
        current_app.logger.error('proxy_image failed: %s', e)
        return jsonify({'error': 'Failed to fetch upstream image'}), 502

    content_type = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
    if content_type not in _SAFE_IMAGE_TYPES:
        content_type = 'application/octet-stream'
    resp_headers = {
        'Content-Type': content_type,
        'Cache-Control': 'public, max-age=3600',
        'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': 'inline; filename="image"',
    }
    return Response(resp.iter_content(8192), headers=resp_headers)
