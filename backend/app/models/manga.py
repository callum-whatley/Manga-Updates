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

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'coverUrl': self.cover_url,
            'latestChapter': self.latest_chapter,
            'latestChapterUrl': self.latest_chapter_url,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
