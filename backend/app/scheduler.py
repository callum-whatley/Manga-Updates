import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def _check_all_users(app) -> None:
    """Scrape every active site and update source entries for all manga in the DB.

    Two passes:
      1. CSS-selector sites  — scrape the latest-releases page and fuzzy-match titles.
      2. MangaDex            — per-title API lookup (scrape_site skips MangaDex because
                               it has empty selectors, so we handle it separately).
    """
    with app.app_context():
        from .models import Manga, ScraperSite
        from .api.manga import _upsert_source_entry
        from .scrapers import scrape_site
        from .scrapers.mangadex import _fetch_one as mangadex_fetch_one
        from .scrapers.matcher import match_scraped_to_library
        from .extensions import db

        logger.info('Scheduled check: starting')
        sites = ScraperSite.query.filter_by(is_active=True).all()
        library = Manga.query.all()

        if not library:
            logger.info('Scheduled check: no manga in library, skipping')
            return

        updated = 0

        # ── Pass 1: CSS-selector sites ────────────────────────────────────────
        for site in sites:
            try:
                scraped = scrape_site(site)  # returns [] for MangaDex
                matches = match_scraped_to_library(scraped, library)
                for m in matches['auto']:
                    _upsert_source_entry(m['manga'], site, m['scraped'])
                    updated += 1
            except Exception:
                logger.exception('Scheduled check: error scraping site %s', site.name)

        # ── Pass 2: MangaDex per-title refresh ────────────────────────────────
        mdx_site = ScraperSite.query.filter_by(name='MangaDex').first()
        if mdx_site:
            for manga in library:
                try:
                    info = mangadex_fetch_one(manga.title)
                    if info and info.get('chapter') is not None:
                        _upsert_source_entry(manga, mdx_site, {
                            'chapter': info['chapter'],
                            'chapter_url': info['chapter_url'],
                            'cover_url': info.get('cover_url'),
                        })
                        updated += 1
                except Exception:
                    logger.exception(
                        'Scheduled check: MangaDex error for "%s"', manga.title
                    )

        db.session.commit()
        logger.info('Scheduled check: done — %d source entries updated', updated)


def start_scheduler(app) -> None:
    """Start the background scheduler. Safe to call from create_app()."""
    # When Flask runs with the debug reloader, the module is imported twice.
    # Only start the scheduler in the child (reloader) process, not the parent.
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return

    scheduler = BackgroundScheduler(daemon=True)
    # Run at 06:00 and 18:00 UTC every day
    scheduler.add_job(
        _check_all_users,
        trigger='cron',
        hour='6,18',
        minute=0,
        args=[app],
        id='check_all_users',
        replace_existing=True,
    )
    scheduler.start()
    logger.info('Scheduler started — jobs will run at 06:00 and 18:00 UTC')
