from ..extensions import db
from datetime import datetime, timezone


class MangaSourceEntry(db.Model):
    """Tracks the latest chapter found for a manga on a specific source site."""
    __tablename__ = 'manga_source_entries'

    id = db.Column(db.Integer, primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('scraper_sites.id'), nullable=False)
    latest_chapter = db.Column(db.Float, default=0.0)
    latest_chapter_url = db.Column(db.String(500))
    cover_url = db.Column(db.String(500), nullable=True)
    scraped_title = db.Column(db.String(500), nullable=True)
    is_removed = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('manga_id', 'site_id'),)

    manga = db.relationship('Manga', back_populates='source_entries')
    site = db.relationship('ScraperSite', back_populates='source_entries')

    def to_dict(self):
        return {
            'siteId': self.site_id,
            'siteName': self.site.name,
            'latestChapter': self.latest_chapter,
            'latestChapterUrl': self.latest_chapter_url,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'scrapedTitle': self.scraped_title,
        }
