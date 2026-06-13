"""
Integration tests for the Manga API (app/api/manga.py).

Endpoints under test:
  GET    /api/manga/              — list user's manga (auth required)
  POST   /api/manga/              — add manga to user's list (auth required)
  DELETE /api/manga/<id>          — remove manga from user's list (auth required)
  PATCH  /api/manga/<id>/progress — update current chapter (auth required)
"""

import pytest

from app.extensions import db as _db
from app.models.manga import Manga
from app.models.manga_source_entry import MangaSourceEntry
from app.models.scraper_site import ScraperSite
from app.models.user_manga import UserManga


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_manga(db, title: str, slug: str = None) -> Manga:
    slug = slug or title.lower().replace(" ", "-")
    manga = Manga(title=title, slug=slug)
    db.session.add(manga)
    db.session.commit()
    db.session.refresh(manga)
    return manga


def _link_manga(db, user, manga) -> UserManga:
    entry = UserManga(user_id=user.id, manga_id=manga.id)
    db.session.add(entry)
    db.session.commit()
    db.session.refresh(entry)
    return entry


# ── GET /api/manga/ ───────────────────────────────────────────────────────────

class TestListManga:
    def test_returns_401_without_token(self, client):
        resp = client.get("/api/manga/")
        assert resp.status_code == 401

    def test_returns_empty_list_when_no_manga(self, client, auth_headers):
        resp = client.get("/api/manga/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_returns_manga_list_for_user(self, client, db, test_user, auth_headers, app):
        with app.app_context():
            manga = _create_manga(db, "One Piece", "one-piece")
            _link_manga(db, test_user, manga)

        resp = client.get("/api/manga/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "One Piece"

    def test_does_not_return_other_users_manga(self, client, db, test_user, auth_headers, app):
        """Manga linked to another user should not appear in the response."""
        from app.models.user import User

        with app.app_context():
            other = User(
                email="other@example.com",
                display_name="Other User",
                oauth_provider="github",
                oauth_sub="other-sub-456",
            )
            db.session.add(other)
            db.session.commit()
            db.session.refresh(other)

            manga = _create_manga(db, "Naruto", "naruto")
            _link_manga(db, other, manga)

        resp = client.get("/api/manga/", headers=auth_headers)
        assert resp.status_code == 200
        titles = [m["title"] for m in resp.get_json()]
        assert "Naruto" not in titles


# ── POST /api/manga/ ──────────────────────────────────────────────────────────

class TestAddManga:
    def test_returns_401_without_token(self, client):
        resp = client.post("/api/manga/", json={"title": "Bleach"})
        assert resp.status_code == 401

    def test_returns_400_when_title_missing(self, client, auth_headers, monkeypatch):
        # Patch scrapers so no network calls happen
        monkeypatch.setattr("app.api.manga.scrape_site", lambda site: [])
        monkeypatch.setattr("app.api.manga.mangadex_fetch_one", lambda title: None)
        resp = client.post("/api/manga/", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_returns_201_and_adds_manga(self, client, auth_headers, monkeypatch, app):
        monkeypatch.setattr("app.api.manga.scrape_site", lambda site: [])
        monkeypatch.setattr("app.api.manga.mangadex_fetch_one", lambda title: None)

        resp = client.post(
            "/api/manga/",
            json={"title": "Dragon Ball Super"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Dragon Ball Super"

    def test_returns_409_when_already_in_list(self, client, db, test_user, auth_headers, monkeypatch, app):
        monkeypatch.setattr("app.api.manga.scrape_site", lambda site: [])
        monkeypatch.setattr("app.api.manga.mangadex_fetch_one", lambda title: None)

        with app.app_context():
            manga = _create_manga(db, "Hunter x Hunter", "hunter-x-hunter")
            _link_manga(db, test_user, manga)

        resp = client.post(
            "/api/manga/",
            json={"title": "Hunter x Hunter"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    def test_scraper_and_mangadex_called_on_add(self, client, auth_headers, monkeypatch):
        """Verify that scraper and MangaDex are invoked during add."""
        scrape_calls = []
        mdx_calls = []

        monkeypatch.setattr(
            "app.api.manga.scrape_site",
            lambda site: scrape_calls.append(site) or [],
        )
        monkeypatch.setattr(
            "app.api.manga.mangadex_fetch_one",
            lambda title: mdx_calls.append(title) or None,
        )

        resp = client.post(
            "/api/manga/",
            json={"title": "Fullmetal Alchemist"},
            headers=auth_headers,
        )
        # Even with no sites in DB, mangadex_fetch_one should be called
        assert resp.status_code == 201
        assert len(mdx_calls) == 1
        assert mdx_calls[0] == "Fullmetal Alchemist"


# ── DELETE /api/manga/<id> ────────────────────────────────────────────────────

class TestRemoveManga:
    def test_returns_401_without_token(self, client):
        resp = client.delete("/api/manga/999")
        assert resp.status_code == 401

    def test_returns_404_for_nonexistent_entry(self, client, auth_headers):
        resp = client.delete("/api/manga/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_removes_manga_from_user_list(self, client, db, test_user, auth_headers, app):
        with app.app_context():
            manga = _create_manga(db, "Vinland Saga", "vinland-saga")
            entry = _link_manga(db, test_user, manga)
            manga_id = manga.id

        resp = client.delete(f"/api/manga/{manga_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify the user_manga entry is gone
        with app.app_context():
            assert UserManga.query.filter_by(
                user_id=test_user.id, manga_id=manga_id
            ).first() is None

    def test_does_not_remove_manga_belonging_to_another_user(
        self, client, db, test_user, auth_headers, app
    ):
        """User A cannot delete user B's entry."""
        from app.models.user import User

        with app.app_context():
            other = User(
                email="another@example.com",
                display_name="Another User",
                oauth_provider="github",
                oauth_sub="another-sub-789",
            )
            db.session.add(other)
            db.session.commit()
            db.session.refresh(other)

            manga = _create_manga(db, "Berserk", "berserk")
            _link_manga(db, other, manga)
            manga_id = manga.id

        resp = client.delete(f"/api/manga/{manga_id}", headers=auth_headers)
        assert resp.status_code == 404


# ── DELETE /api/manga/<id>/sources/<site_id> ──────────────────────────────────

def _create_site(db, name: str, url: str) -> ScraperSite:
    site = ScraperSite(
        name=name,
        latest_releases_url=url,
        title_selector="h3",
        chapter_link_selector="a",
    )
    db.session.add(site)
    db.session.commit()
    db.session.refresh(site)
    return site


def _add_source(db, manga, site, latest_chapter=10.0, cover_url=None) -> MangaSourceEntry:
    entry = MangaSourceEntry(
        manga_id=manga.id,
        site_id=site.id,
        latest_chapter=latest_chapter,
        latest_chapter_url=f"{site.latest_releases_url}chapter/{int(latest_chapter)}",
        cover_url=cover_url,
    )
    db.session.add(entry)
    db.session.commit()
    db.session.refresh(entry)
    return entry


class TestRemoveSourceEntry:
    def test_returns_401_without_token(self, client):
        resp = client.delete("/api/manga/1/sources/1")
        assert resp.status_code == 401

    def test_response_preserves_current_chapter(self, client, db, test_user, auth_headers, app):
        """Regression: removing a source must not drop currentChapter/currentChapterUrl.

        The endpoint used to return manga.to_dict(), which omits the user-scoped
        progress fields — the frontend then overwrote the entry with NaN-inducing
        undefineds. It must return the UserManga dict instead.
        """
        with app.app_context():
            manga = _create_manga(db, "Solo Leveling", "solo-leveling")
            entry = _link_manga(db, test_user, manga)
            entry.current_chapter = 7.0
            entry.current_chapter_url = "https://example.com/solo-leveling/chapter/7"
            db.session.commit()
            site_a = _create_site(db, "AsuraScans", "https://asura.example/")
            site_b = _create_site(db, "VortexScans", "https://vortex.example/")
            _add_source(db, manga, site_a, latest_chapter=12.0, cover_url="https://a/c.jpg")
            _add_source(db, manga, site_b, latest_chapter=11.0, cover_url="https://b/c.jpg")
            manga_id = manga.id
            site_a_id = site_a.id

        resp = client.delete(
            f"/api/manga/{manga_id}/sources/{site_a_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["currentChapter"] == 7.0
        assert data["currentChapterUrl"] == "https://example.com/solo-leveling/chapter/7"
        # the removed source must be gone from the returned sources list
        assert all(s["siteId"] != site_a_id for s in data["sources"])

    def test_returns_409_when_another_user_tracks_it(
        self, client, db, test_user, auth_headers, app
    ):
        from app.models.user import User

        with app.app_context():
            other = User(
                email="sharer@example.com",
                display_name="Sharer",
                oauth_provider="github",
                oauth_sub="sharer-sub-001",
            )
            db.session.add(other)
            db.session.commit()
            db.session.refresh(other)

            manga = _create_manga(db, "Omniscient Reader", "omniscient-reader")
            _link_manga(db, test_user, manga)
            _link_manga(db, other, manga)
            site = _create_site(db, "AsuraScans", "https://asura2.example/")
            _add_source(db, manga, site)
            manga_id = manga.id
            site_id = site.id

        resp = client.delete(
            f"/api/manga/{manga_id}/sources/{site_id}", headers=auth_headers
        )
        assert resp.status_code == 409


# ── PATCH /api/manga/<id>/progress ───────────────────────────────────────────

class TestUpdateProgress:
    def test_returns_401_without_token(self, client):
        resp = client.patch("/api/manga/999/progress", json={"chapter": 10})
        assert resp.status_code == 401

    def test_returns_404_for_nonexistent_entry(self, client, auth_headers):
        resp = client.patch(
            "/api/manga/99999/progress",
            json={"chapter": 5},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_updates_chapter(self, client, db, test_user, auth_headers, app):
        with app.app_context():
            manga = _create_manga(db, "Attack on Titan", "attack-on-titan")
            entry = _link_manga(db, test_user, manga)
            manga_id = manga.id

        resp = client.patch(
            f"/api/manga/{manga_id}/progress",
            json={"chapter": 42},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["currentChapter"] == 42.0

    def test_updates_chapter_url(self, client, db, test_user, auth_headers, app):
        with app.app_context():
            manga = _create_manga(db, "Chainsaw Man", "chainsaw-man")
            entry = _link_manga(db, test_user, manga)
            manga_id = manga.id

        chapter_url = "https://example.com/chainsaw-man/chapter/5"
        resp = client.patch(
            f"/api/manga/{manga_id}/progress",
            json={"chapter": 5, "chapterUrl": chapter_url},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["currentChapter"] == 5.0
        assert data["currentChapterUrl"] == chapter_url

    def test_returns_400_for_invalid_chapter_value(self, client, db, test_user, auth_headers, app):
        with app.app_context():
            manga = _create_manga(db, "Demon Slayer", "demon-slayer")
            _link_manga(db, test_user, manga)
            manga_id = manga.id

        resp = client.patch(
            f"/api/manga/{manga_id}/progress",
            json={"chapter": "not-a-number"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_ignores_invalid_chapter_url(self, client, db, test_user, auth_headers, app):
        """Private/loopback URLs are rejected by validate_external_url, chapter still updates."""
        with app.app_context():
            manga = _create_manga(db, "My Hero Academia", "my-hero-academia")
            _link_manga(db, test_user, manga)
            manga_id = manga.id

        resp = client.patch(
            f"/api/manga/{manga_id}/progress",
            json={"chapter": 10, "chapterUrl": "http://localhost/evil"},
            headers=auth_headers,
        )
        # Chapter update should succeed; bad URL is silently dropped
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["currentChapter"] == 10.0
        assert data.get("currentChapterUrl") is None
