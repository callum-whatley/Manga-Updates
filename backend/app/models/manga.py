from ..extensions import db
from datetime import datetime, timezone
from .scraper_site import source_rank


class Manga(db.Model):
    __tablename__ = 'manga'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(500), unique=True, nullable=False)  # normalised title for dedup
    cover_url = db.Column(db.String(500))
    mangadex_id = db.Column(db.String(100), unique=True, nullable=True)
    asura_url = db.Column(db.String(500), nullable=True)
    latest_chapter = db.Column(db.Float, default=0.0)
    latest_chapter_url = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_entries = db.relationship('UserManga', back_populates='manga', cascade='all, delete-orphan')
    source_entries = db.relationship('MangaSourceEntry', back_populates='manga', cascade='all, delete-orphan')

    def best_chapter(self) -> float:
        """Highest chapter number across all sources."""
        if self.source_entries:
            return max((e.latest_chapter for e in self.source_entries), default=0.0)
        return self.latest_chapter

    def preferred_cover(self) -> str | None:
        """Cover from the highest-priority source that currently has one.

        Computed live from the source entries so that removing the source a cover
        came from automatically falls back to the next available source (or to no
        cover if none remain). Falls back to the denormalised manga-level cover
        only when no source carries one.
        """
        with_cover = [e for e in self.source_entries if e.cover_url]
        if with_cover:
            best = min(with_cover, key=lambda e: source_rank(e.site.name))
            return best.cover_url
        return self.cover_url

    def to_dict(self):
        sources = sorted(
            [e.to_dict() for e in self.source_entries],
            key=lambda s: source_rank(s['siteName'])
        ) if self.source_entries else []
        return {
            'id': self.id,
            'title': self.title,
            'coverUrl': self.preferred_cover(),
            'latestChapter': self.best_chapter(),
            'sources': sources,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
