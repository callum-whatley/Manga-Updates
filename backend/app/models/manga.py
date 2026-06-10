from ..extensions import db
from datetime import datetime, timezone


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

    def to_dict(self):
        sources = sorted(
            [e.to_dict() for e in self.source_entries],
            key=lambda s: s['siteName'].lower() == 'mangadex'
        ) if self.source_entries else []
        return {
            'id': self.id,
            'title': self.title,
            'coverUrl': self.cover_url,
            'latestChapter': self.best_chapter(),
            'sources': sources,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
