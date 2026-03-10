from ..extensions import db
from datetime import datetime, timezone


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(500))
    oauth_provider = db.Column(db.String(20), nullable=False)  # 'google' | 'github'
    oauth_sub = db.Column(db.String(100), nullable=False)      # provider user ID
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    manga_entries = db.relationship('UserManga', back_populates='user', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'displayName': self.display_name,
            'avatarUrl': self.avatar_url,
            'isAdmin': self.is_admin,
        }
