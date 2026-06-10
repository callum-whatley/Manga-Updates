"""
Integration tests for the Reader API (app/api/reader.py).

Endpoints under test:
  GET /api/reader/images       — extract chapter images from a page (auth required)
  GET /api/reader/proxy-image  — proxy an external image (no auth required)
"""

import pytest
from unittest.mock import MagicMock, patch

from app.models.scraper_site import ScraperSite
from app.extensions import db as _db


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_mock_response(content: bytes = b"", text: str = "", status_code: int = 200,
                         content_type: str = "text/html"):
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = content
    mock.text = text
    mock.headers = {"Content-Type": content_type}
    mock.raise_for_status = MagicMock()
    mock.iter_content = MagicMock(return_value=iter([content]))
    return mock


def _create_scraper_site(db, name: str = "TestSite",
                          selector: str = "img.page",
                          url: str = "https://testsite.example.com") -> ScraperSite:
    site = ScraperSite(
        name=name,
        latest_releases_url=url,
        title_selector=".title",
        chapter_link_selector=".chapter a",
        chapter_image_selector=selector,
        is_active=True,
    )
    db.session.add(site)
    db.session.commit()
    db.session.refresh(site)
    return site


# ── GET /api/reader/images ────────────────────────────────────────────────────

class TestGetImages:
    def test_returns_401_without_token(self, client):
        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://example.com/chapter/1", "site_id": "1"},
        )
        assert resp.status_code == 401

    def test_returns_400_when_url_missing(self, client, auth_headers):
        resp = client.get(
            "/api/reader/images",
            query_string={"site_id": "1"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_returns_400_when_site_id_missing(self, client, auth_headers):
        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://example.com/chapter/1"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_returns_400_when_site_id_not_integer(self, client, auth_headers):
        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://example.com/chapter/1", "site_id": "abc"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_returns_400_when_url_is_private(self, client, auth_headers, db, app):
        with app.app_context():
            site = _create_scraper_site(db)
            site_id = site.id

        resp = client.get(
            "/api/reader/images",
            query_string={"url": "http://localhost/chapter/1", "site_id": str(site_id)},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_returns_404_for_unknown_site_id(self, client, auth_headers):
        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://example.com/chapter/1", "site_id": "99999"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_returns_400_when_site_has_no_image_selector(self, client, db, auth_headers, app):
        with app.app_context():
            site = _create_scraper_site(db, name="NoSelectorSite",
                                         selector=None,
                                         url="https://noselector.example.com")
            site_id = site.id

        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://example.com/chapter/1", "site_id": str(site_id)},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_returns_image_list_for_css_selector(self, client, db, auth_headers, monkeypatch, app):
        with app.app_context():
            site = _create_scraper_site(db, name="CssSite",
                                         selector="img.page-img",
                                         url="https://csssite.example.com")
            site_id = site.id

        html = (
            b'<html><body>'
            b'<img class="page-img" src="https://cdn.example.com/p1.jpg" />'
            b'<img class="page-img" src="https://cdn.example.com/p2.jpg" />'
            b'</body></html>'
        )
        mock_resp = _make_mock_response(content=html)

        monkeypatch.setattr("app.api.reader.requests.get", lambda *a, **kw: mock_resp)

        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://csssite.example.com/chapter/1", "site_id": str(site_id)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "images" in data
        assert len(data["images"]) == 2
        assert "https://cdn.example.com/p1.jpg" in data["images"]

    def test_returns_502_when_external_fetch_fails(self, client, db, auth_headers, monkeypatch, app):
        with app.app_context():
            site = _create_scraper_site(db, name="FailSite",
                                         selector="img.page",
                                         url="https://failsite.example.com")
            site_id = site.id

        def _raise(*a, **kw):
            raise ConnectionError("Connection refused")

        monkeypatch.setattr("app.api.reader.requests.get", _raise)

        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://failsite.example.com/chapter/1", "site_id": str(site_id)},
            headers=auth_headers,
        )
        assert resp.status_code == 502

    def test_regex_selector_returns_sorted_images(self, client, db, auth_headers, monkeypatch, app):
        with app.app_context():
            site = _create_scraper_site(
                db,
                name="RegexSite",
                selector=r"regex:https://cdn\.example\.com/\d+-optimized\.webp",
                url="https://regexsite.example.com",
            )
            site_id = site.id

        html_text = (
            "https://cdn.example.com/03-optimized.webp "
            "https://cdn.example.com/01-optimized.webp "
            "https://cdn.example.com/02-optimized.webp"
        )
        mock_resp = _make_mock_response(content=html_text.encode(), text=html_text)

        monkeypatch.setattr("app.api.reader.requests.get", lambda *a, **kw: mock_resp)

        resp = client.get(
            "/api/reader/images",
            query_string={"url": "https://regexsite.example.com/chapter/1", "site_id": str(site_id)},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["images"] == [
            "https://cdn.example.com/01-optimized.webp",
            "https://cdn.example.com/02-optimized.webp",
            "https://cdn.example.com/03-optimized.webp",
        ]


# ── GET /api/reader/proxy-image ───────────────────────────────────────────────

class TestProxyImage:
    FAKE_IMAGE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal fake PNG bytes

    def _mock_streaming_response(self, content: bytes = None, content_type: str = "image/png"):
        content = content or self.FAKE_IMAGE
        mock = MagicMock()
        mock.status_code = 200
        mock.headers = {"Content-Type": content_type}
        mock.raise_for_status = MagicMock()
        mock.iter_content = MagicMock(return_value=iter([content]))
        return mock

    def test_returns_400_when_url_missing(self, client):
        resp = client.get("/api/reader/proxy-image")
        assert resp.status_code == 400

    def test_returns_400_for_private_ip_url(self, client):
        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "http://192.168.1.1/image.jpg"},
        )
        assert resp.status_code == 400

    def test_returns_400_for_localhost_url(self, client):
        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "http://localhost/image.jpg"},
        )
        assert resp.status_code == 400

    def test_proxies_image_successfully(self, client, monkeypatch):
        mock_resp = self._mock_streaming_response(self.FAKE_IMAGE, "image/jpeg")
        monkeypatch.setattr("app.api.reader.requests.get", lambda *a, **kw: mock_resp)

        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "https://cdn.example.com/page1.jpg"},
        )
        assert resp.status_code == 200

    def test_cache_control_header_present(self, client, monkeypatch):
        """Cache-Control: public, max-age=3600 must be set on every proxied image."""
        mock_resp = self._mock_streaming_response()
        monkeypatch.setattr("app.api.reader.requests.get", lambda *a, **kw: mock_resp)

        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "https://cdn.example.com/page1.png"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("Cache-Control") == "public, max-age=3600"

    def test_content_type_forwarded_from_upstream(self, client, monkeypatch):
        mock_resp = self._mock_streaming_response(content_type="image/webp")
        monkeypatch.setattr("app.api.reader.requests.get", lambda *a, **kw: mock_resp)

        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "https://cdn.example.com/page1.webp"},
        )
        assert resp.status_code == 200
        assert "image/webp" in resp.content_type

    def test_returns_502_when_upstream_fails(self, client, monkeypatch):
        def _raise(*a, **kw):
            raise ConnectionError("upstream is down")

        monkeypatch.setattr("app.api.reader.requests.get", _raise)

        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "https://cdn.example.com/broken.jpg"},
        )
        assert resp.status_code == 502

    def test_proxy_image_does_not_require_auth(self, client, monkeypatch):
        """proxy-image is intentionally unauthenticated (images are proxied for the reader)."""
        mock_resp = self._mock_streaming_response()
        monkeypatch.setattr("app.api.reader.requests.get", lambda *a, **kw: mock_resp)

        resp = client.get(
            "/api/reader/proxy-image",
            query_string={"url": "https://cdn.example.com/page1.png"},
        )
        # Should NOT return 401
        assert resp.status_code != 401
