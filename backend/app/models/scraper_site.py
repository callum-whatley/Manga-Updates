from ..extensions import db
from datetime import datetime, timezone


# Preferred source order for cover art and display. Scanlation sites that host
# the chapters we read (and whose covers match those releases) rank above the
# aggregators (Mangafox, MangaDex) whose cover art is often a different edition.
SOURCE_PRIORITY = ['asurascans', 'vortexscans', 'yomi manga', 'mangafox', 'mangadex']


def source_rank(site_name: str) -> int:
    """Lower rank = higher priority. Unknown sources sort after all known ones."""
    name = (site_name or '').lower()
    return SOURCE_PRIORITY.index(name) if name in SOURCE_PRIORITY else len(SOURCE_PRIORITY)


class ScraperSite(db.Model):
    __tablename__ = 'scraper_sites'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    latest_releases_url = db.Column(db.String(500), nullable=False, unique=True)
    container_selector = db.Column(db.String(500), nullable=True)  # optional: scopes all other selectors
    chapter_image_selector = db.Column(db.String(500), nullable=True)  # optional: for in-app chapter reader
    search_url_template = db.Column(db.Text, nullable=True)
    title_selector = db.Column(db.String(500), nullable=False)
    cover_selector = db.Column(db.String(500), nullable=True)
    chapter_link_selector = db.Column(db.String(500), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    source_entries = db.relationship('MangaSourceEntry', back_populates='site', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'latestReleasesUrl': self.latest_releases_url,
            'containerSelector': self.container_selector,
            'chapterImageSelector': self.chapter_image_selector,
            'searchUrlTemplate': self.search_url_template,
            'titleSelector': self.title_selector,
            'coverSelector': self.cover_selector,
            'chapterLinkSelector': self.chapter_link_selector,
            'isActive': self.is_active,
        }
