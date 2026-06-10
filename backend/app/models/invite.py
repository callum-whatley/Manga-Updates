from ..extensions import db
from datetime import datetime, timezone
import secrets


class Invite(db.Model):
    __tablename__ = 'invites'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    used_by = db.relationship('User', foreign_keys=[used_by_id])

    @classmethod
    def generate(cls):
        invite = cls()
        db.session.add(invite)
        db.session.commit()
        return invite
