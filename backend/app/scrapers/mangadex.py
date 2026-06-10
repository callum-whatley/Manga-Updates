import re
import requests
from .matcher import _score, AUTO_MATCH_THRESHOLD

BASE = 'https://api.mangadex.org'
TIMEOUT = 10
_UUID_RE = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
MANGADEX_SITE_NAME = 'MangaDex'


def fetch_mangadex_releases(titles: list[str]) -> list[dict]:
    """
    Search MangaDex for each title and return the latest English chapter.
    Returns a list of {'title', 'cover_url', 'chapter', 'chapter_url', 'mangadex_id'}.
    """
    results = []
    for title in titles:
        info = _fetch_one(title)
        if info:
            results.append(info)
    return results


def _best_title(manga: dict) -> str:
    attrs = manga['attributes']
    titles_dict = attrs.get('title', {})
    en_title = titles_dict.get('en')
    if not en_title:
        for alt in attrs.get('altTitles', []):
            if 'en' in alt:
                en_title = alt['en']
                break
    return en_title or next(iter(titles_dict.values()), '')


def _fetch_one(title: str) -> dict | None:
    try:
        resp = requests.get(
            f'{BASE}/manga',
            params={
                'title': title,
                'limit': 10,
                'availableTranslatedLanguage[]': 'en',
                'includes[]': 'cover_art',
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get('data', [])
        if not data:
            return None

        # Pick the candidate with the highest fuzzy score
        best_manga, best_score, best_found_title = None, 0, ''
        for candidate in data:
            found_title = _best_title(candidate)
            score = _score(title, found_title)
            if score > best_score:
                best_score, best_manga, best_found_title = score, candidate, found_title

        if best_score < AUTO_MATCH_THRESHOLD:
            print(f'[MangaDex] no match above threshold for "{title}" (best: "{best_found_title}", score: {best_score})')
            return None

        manga_id = best_manga['id']
        cover_url = _get_cover(manga_id, best_manga.get('relationships', []))
        chapter_info = _get_latest_english_chapter(manga_id)

        return {
            'title': best_found_title,
            'cover_url': cover_url,
            'chapter': chapter_info.get('chapter') if chapter_info else None,
            'chapter_url': chapter_info.get('chapter_url') if chapter_info else None,
            'mangadex_id': manga_id,
        }
    except Exception as e:
        print(f'[MangaDex] error fetching "{title}": {e}')
        return None


def _get_cover(manga_id: str, relationships: list) -> str | None:
    cover_rel = next((r for r in relationships if r['type'] == 'cover_art'), None)
    if not cover_rel:
        return None
    # Try attributes embedded in the relationship first (avoid extra request)
    filename = (cover_rel.get('attributes') or {}).get('fileName')
    if filename:
        return f'https://uploads.mangadex.org/covers/{manga_id}/{filename}.256.jpg'
    try:
        resp = requests.get(f'{BASE}/cover/{cover_rel["id"]}', timeout=TIMEOUT)
        resp.raise_for_status()
        filename = resp.json()['data']['attributes']['fileName']
        return f'https://uploads.mangadex.org/covers/{manga_id}/{filename}.256.jpg'
    except Exception:
        return None


def _get_chapter_url_by_number(mangadex_id: str, chapter_num: float) -> str | None:
    """Find the MangaDex chapter UUID URL for a specific chapter number.

    MangaDex's feed endpoint doesn't support filtering by chapter number, so we
    paginate descending and stop early once we pass the target.
    """
    offset = 0
    while True:
        try:
            resp = requests.get(
                f'{BASE}/manga/{mangadex_id}/feed',
                params={
                    'translatedLanguage[]': 'en',
                    'order[chapter]': 'desc',
                    'limit': 100,
                    'offset': offset,
                    'contentRating[]': ['safe', 'suggestive', 'erotica'],
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            j = resp.json()
            data = j.get('data', [])
            total = j.get('total', 0)

            for ch in data:
                raw = ch['attributes'].get('chapter')
                if not raw:
                    continue
                try:
                    raw_float = float(raw)
                except ValueError:
                    continue
                if raw_float == chapter_num and _UUID_RE.match(ch['id']):
                    return f'https://mangadex.org/chapter/{ch["id"]}'
                if raw_float < chapter_num:
                    return None

            if not data or offset + len(data) >= total:
                return None
            offset += len(data)
        except Exception as e:
            print(f'[MangaDex] chapter URL lookup failed for ch {chapter_num}: {e}')
            return None


def _get_latest_english_chapter(manga_id: str) -> dict | None:
    try:
        resp = requests.get(
            f'{BASE}/manga/{manga_id}/feed',
            params={
                'translatedLanguage[]': 'en',
                'order[chapter]': 'desc',
                'limit': 20,
                'contentRating[]': ['safe', 'suggestive', 'erotica'],
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        chapters = resp.json().get('data', [])
        for ch in chapters:
            raw = ch['attributes'].get('chapter')
            if not raw:
                continue
            try:
                ch_num = float(raw)
            except ValueError:
                continue
            return {
                'chapter': ch_num,
                'chapter_url': f'https://mangadex.org/chapter/{ch["id"]}',
            }
        return None
    except Exception:
        return None
