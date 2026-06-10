from ..extensions import db
from datetime import datetime, timezone


class UserManga(db.Model):
    __tablename__ = 'user_manga'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    current_chapter = db.Column(db.Float, default=0.0)          # last chapter the user clicked
    current_chapter_url = db.Column(db.String(500))
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'manga_id'),)

    user = db.relationship('User', back_populates='manga_entries')
    manga = db.relationship('Manga', back_populates='user_entries')

    def to_dict(self):
        manga_dict = self.manga.to_dict()
        return {
            **manga_dict,
            'currentChapter': self.current_chapter,
            'currentChapterUrl': self.current_chapter_url,
            'hasUpdate': manga_dict['latestChapter'] > self.current_chapter,
        }
