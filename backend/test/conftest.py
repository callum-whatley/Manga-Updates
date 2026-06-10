import os
from unittest.mock import patch

# Stub env vars so Flask config can be imported without a real environment.
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")
os.environ.setdefault("GITHUB_CLIENT_ID", "test")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test")

import pytest
from flask_jwt_extended import create_access_token
from app import create_app
from app.extensions import db as _db


class TestConfig:
    """Test configuration — SQLite in-memory, no external services."""
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = "test-secret"
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    GOOGLE_CLIENT_ID = "test"
    GOOGLE_CLIENT_SECRET = "test"
    GITHUB_CLIENT_ID = "test"
    GITHUB_CLIENT_SECRET = "test"
    FRONTEND_URL = "http://localhost:5173"
    BACKEND_URL = ""
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = False
    NATIVE_CALLBACK_SCHEME = "mangaupdates"
    CAPACITOR_ORIGINS = "capacitor://localhost,http://localhost"
    TESTING = True


@pytest.fixture(scope="session")
def app():
    """Flask test app using SQLite in-memory DB. Scheduler is disabled."""
    with patch("app.scheduler.start_scheduler"):
        application = create_app(TestConfig)
    application.config["TESTING"] = True

    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """Yield db within app context; roll back after each test for isolation."""
    with app.app_context():
        yield _db
        _db.session.rollback()


@pytest.fixture
def test_user(db, app):
    """Creates and returns a test User in the DB."""
    from app.models.user import User
    with app.app_context():
        # Clean up any leftover user from a previous test
        existing = User.query.filter_by(email="test@example.com").first()
        if existing:
            _db.session.delete(existing)
            _db.session.commit()
        user = User(
            email="test@example.com",
            display_name="Test User",
            oauth_provider="github",
            oauth_sub="test-sub-123",
        )
        _db.session.add(user)
        _db.session.commit()
        _db.session.refresh(user)
        yield user
        # Cleanup: delete user and cascade entries
        u = User.query.get(user.id)
        if u:
            _db.session.delete(u)
            _db.session.commit()


@pytest.fixture
def auth_headers(app, test_user):
    """Returns JWT auth headers for the test user."""
    with app.app_context():
        token = create_access_token(identity=str(test_user.id))
        return {"Authorization": f"Bearer {token}"}
