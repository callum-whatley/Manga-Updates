from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models import Manga, UserManga, User
from ..scrapers import scrape_site
from ..scrapers.mangadex import _fetch_one as mangadex_fetch_one
from ..models import ScraperSite, MangaSourceEntry
from ..scrapers.matcher import match_scraped_to_library
from .sanitize import sanitize_str, validate_external_url
from datetime import datetime, timezone
import re
import requests as _requests

bp = Blueprint('manga', __name__)


def _current_user() -> User:
    return User.query.get(int(get_jwt_identity()))


def _slugify(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


# ── List user's manga ──────────────────────────────────────────────────────────

@bp.get('/')
@jwt_required()
def list_manga():
    user = _current_user()
    entries = UserManga.query.filter_by(user_id=user.id).join(Manga).order_by(Manga.title).all()
    return jsonify([e.to_dict() for e in entries])


# ── Add manga to user's list ───────────────────────────────────────────────────

@bp.post('/')
@jwt_required()
def add_manga():
    user = _current_user()
    data = request.get_json()
    title = sanitize_str(data.get('title'), max_length=300)
    if not title:
        return jsonify({'error': 'title is required'}), 400

    slug = _slugify(title)
    manga = Manga.query.filter_by(slug=slug).first()

    if not manga:
        manga = Manga(title=title, slug=slug)
        db.session.add(manga)
        db.session.flush()

    existing_site_ids = {e.site_id for e in manga.source_entries}

    # Search each active site for this specific title. Each source stores its own
    # cover; the displayed cover is chosen by priority in Manga.preferred_cover().
    from ..scrapers.search import search_site
    scraper_sites = ScraperSite.query.filter(
        ScraperSite.is_active == True,
        ScraperSite.name != 'MangaDex',
    ).all()
    for site in scraper_sites:
        scraped = search_site(site, title)
        matches = match_scraped_to_library(scraped, [manga])
        for m in matches['auto']:
            _upsert_source_entry(manga, site, m['scraped'])

    # MangaDex last — skip if already linked
    mdx_site = ScraperSite.query.filter_by(name='MangaDex').first()
    if not mdx_site or mdx_site.id not in existing_site_ids:
        info = mangadex_fetch_one(title)
        if info:
            if not manga.mangadex_id:
                manga.mangadex_id = info.get('mangadex_id')
            if info.get('chapter') is not None:
                if not mdx_site:
                    mdx_site = ScraperSite(
                        name='MangaDex',
                        latest_releases_url='https://mangadex.org',
                        title_selector='',
                        chapter_link_selector='',
                        is_active=True,
                    )
                    db.session.add(mdx_site)
                    db.session.flush()
                _upsert_source_entry(manga, mdx_site, {
                    'chapter': info['chapter'],
                    'chapter_url': info['chapter_url'],
                    'cover_url': info.get('cover_url'),
                })

    existing = UserManga.query.filter_by(user_id=user.id, manga_id=manga.id).first()
    if existing:
        return jsonify({'error': 'Already in your list'}), 409

    entry = UserManga(user_id=user.id, manga_id=manga.id)
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


# ── Remove manga from user's list ─────────────────────────────────────────────

@bp.delete('/<int:manga_id>')
@jwt_required()
def remove_manga(manga_id: int):
    user = _current_user()
    entry = UserManga.query.filter_by(user_id=user.id, manga_id=manga_id).first_or_404()
    manga = entry.manga
    db.session.delete(entry)
    db.session.flush()
    # Delete the manga record if no other users have it in their list
    if not UserManga.query.filter_by(manga_id=manga_id).first():
        db.session.delete(manga)
    db.session.commit()
    return '', 204


# ── Remove a source entry from a manga ────────────────────────────────────────

@bp.delete('/<int:manga_id>/sources/<int:site_id>')
@jwt_required()
def remove_source_entry(manga_id: int, site_id: int):
    user = _current_user()
    UserManga.query.filter_by(user_id=user.id, manga_id=manga_id).first_or_404()

    other_watchers = UserManga.query.filter(
        UserManga.manga_id == manga_id,
        UserManga.user_id != user.id,
    ).count()
    if other_watchers:
        return jsonify({'error': 'Cannot remove a shared source entry while other users track this manga'}), 409

    entry = MangaSourceEntry.query.filter_by(manga_id=manga_id, site_id=site_id).first_or_404()
    manga = entry.manga
    db.session.delete(entry)
    db.session.flush()  # so manga.source_entries reflects the removal

    # Re-sync the denormalised cover to whatever the remaining sources offer, so
    # removing the source a cover came from falls back to the next available one.
    from ..models.scraper_site import source_rank
    remaining = [e for e in manga.source_entries if e.cover_url]
    manga.cover_url = (
        min(remaining, key=lambda e: source_rank(e.site.name)).cover_url
        if remaining else None
    )
    db.session.commit()
    return jsonify(manga.to_dict())


# ── Update current chapter (called when user clicks a chapter link) ────────────

@bp.patch('/<int:manga_id>/progress')
@jwt_required()
def update_progress(manga_id: int):
    user = _current_user()
    entry = UserManga.query.filter_by(user_id=user.id, manga_id=manga_id).first_or_404()
    data = request.get_json()
    chapter = data.get('chapter')
    chapter_url = validate_external_url(data.get('chapterUrl', ''))
    if chapter is not None:
        try:
            entry.current_chapter = float(chapter)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid chapter value'}), 400
    if chapter_url:
        entry.current_chapter_url = chapter_url
    db.session.commit()
    return jsonify(entry.to_dict())


# ── Manual update check ────────────────────────────────────────────────────────

@bp.post('/<int:manga_id>/check')
@jwt_required()
def check_updates(manga_id: int):
    user = _current_user()
    entry = UserManga.query.filter_by(user_id=user.id, manga_id=manga_id).first_or_404()
    _refresh_sources_for_manga(entry.manga)
    db.session.commit()
    return jsonify(entry.to_dict())


# ── Check all (manual bulk refresh) ───────────────────────────────────────────

@bp.post('/check-all')
@jwt_required()
def check_all():
    user = _current_user()
    entries = UserManga.query.filter_by(user_id=user.id).join(Manga).all()
    sites = ScraperSite.query.filter_by(is_active=True).all()

    for site in sites:
        scraped = scrape_site(site)
        library = [e.manga for e in entries]
        matches = match_scraped_to_library(scraped, library)
        for m in matches['auto']:
            _upsert_source_entry(m['manga'], site, m['scraped'])

    db.session.commit()
    return jsonify([e.to_dict() for e in entries])


_COVER_REFERER_RULES = [
    ('uploads.mangadex.org', 'https://mangadex.org/'),
    ('asurascans.com', 'https://asurascans.com/'),
    ('asuracomic.net', 'https://asuracomic.net/'),
    ('fanfox.net', 'https://fanfox.net/'),
    ('mangafox.me', 'https://fanfox.net/'),
    ('mfcdn.net', 'https://fanfox.net/'),
]


def _cover_referer(hostname: str) -> str:
    for domain, referer in _COVER_REFERER_RULES:
        if hostname == domain or hostname.endswith('.' + domain):
            return referer
    return ''

_COVER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}


@bp.get('/cover')
def proxy_cover():
    raw_url = request.args.get('url', '')
    url = validate_external_url(raw_url)
    if not url:
        return '', 400
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or ''
    headers = {**_COVER_HEADERS, 'Referer': _cover_referer(hostname)}
    try:
        resp = _requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        if resp.status_code != 200:
            return '', resp.status_code
        ct = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
        if ct not in {'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/avif'}:
            return '', 400
        return Response(resp.content, content_type=ct, headers={
            'Cache-Control': 'public, max-age=86400',
            'X-Content-Type-Options': 'nosniff',
        })
    except Exception:
        return '', 502


def _upsert_source_entry(manga, site, scraped: dict):
    from ..models import MangaSourceEntry
    cover = scraped.get('cover_url')
    entry = MangaSourceEntry.query.filter_by(manga_id=manga.id, site_id=site.id).first()
    if entry:
        entry.latest_chapter = scraped['chapter']
        entry.latest_chapter_url = scraped['chapter_url']
        if cover:
            entry.cover_url = cover
        entry.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(MangaSourceEntry(
            manga_id=manga.id,
            site_id=site.id,
            latest_chapter=scraped['chapter'],
            latest_chapter_url=scraped['chapter_url'],
            cover_url=cover,
        ))
    # Keep the manga-level cover as a denormalised fallback (used when no source
    # carries a cover). Per-source covers drive the displayed cover via
    # Manga.preferred_cover().
    if not manga.cover_url and cover:
        manga.cover_url = cover


def _refresh_sources_for_manga(manga):
    """Re-scrape all active sites to find the latest chapter for a single manga."""
    sites = ScraperSite.query.filter_by(is_active=True).all()
    for site in sites:
        scraped = scrape_site(site)
        matches = match_scraped_to_library(scraped, [manga])
        for m in matches['auto']:
            _upsert_source_entry(manga, site, m['scraped'])
