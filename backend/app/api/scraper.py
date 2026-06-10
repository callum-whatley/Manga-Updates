from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from urllib.parse import urljoin, urlparse, urlencode, quote
import re
import requests
from bs4 import BeautifulSoup

from ..extensions import db
from ..models import ScraperSite, MangaSourceEntry, Manga, UserManga, User
from ..scrapers.generic import test_selectors, scrape_with_selectors
from ..scrapers.matcher import match_scraped_to_library
from .sanitize import sanitize_str, validate_external_url
from datetime import datetime, timezone

bp = Blueprint('scraper', __name__)

PROXY_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
}

# ── Selector overlay JS injected into proxied pages ───────────────────────────

OVERLAY_JS = """
<script>
(function () {
  var ROLES = ['title', 'cover', 'chapter_link'];
  var LABELS = { title: 'Title', cover: 'Cover image', chapter_link: 'Chapter link' };
  var COLORS = { title: '#E63946', cover: '#2196F3', chapter_link: '#4CAF50' };
  var selections = {};

  // --- floating panel ---
  var panel = document.createElement('div');
  panel.id = '__sel_panel';
  panel.style.cssText = [
    'position:fixed;top:16px;right:16px;z-index:999999',
    'background:#0d0d0d;color:#e8e4df;font:13px/1.5 monospace',
    'border:1px solid #333;border-radius:6px;padding:14px 18px',
    'min-width:280px;box-shadow:0 4px 24px rgba(0,0,0,.7)',
  ].join(';');

  function renderPanel() {
    var html = '<b style="font-size:14px">Selector Tool</b><br><br>';
    ROLES.forEach(function (role) {
      var sel = selections[role];
      var color = COLORS[role];
      html += '<div style="margin-bottom:8px">';
      html += '<span style="color:' + color + ';font-weight:bold">' + LABELS[role] + '</span><br>';
      if (sel) {
        html += '<span style="color:#aaa;font-size:11px;word-break:break-all">' + escHtml(sel) + '</span>';
        html += ' <a href="#" data-role="' + role + '" class="__clear_btn" style="color:#E63946;font-size:11px;margin-left:4px">clear</a>';
      } else {
        html += '<span style="color:#555;font-size:11px">click an element on the page</span>';
      }
      html += '</div>';
    });

    var allSet = selections.title && selections.chapter_link;
    var btnColor = allSet ? '#E63946' : '#555';
    var btnCursor = allSet ? 'pointer' : 'default';
    html += '<br><button id="__test_btn" style="background:' + btnColor + ';color:#fff;border:none;padding:7px 16px;border-radius:4px;cursor:' + btnCursor + ';font:inherit;width:100%"' + (allSet ? '' : ' disabled') + '>Test selectors</button>';

    panel.innerHTML = html;

    // re-attach listeners
    panel.querySelectorAll('.__clear_btn').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        delete selections[e.currentTarget.dataset.role];
        renderPanel();
        reHighlight();
      });
    });

    var testBtn = document.getElementById('__test_btn');
    if (testBtn && allSet) {
      testBtn.addEventListener('click', function () {
        window.parent.postMessage({ type: 'SELECTOR_CONFIRM', selections: selections }, '*');
      });
    }
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // --- tooltip ---
  var tooltip = document.createElement('div');
  tooltip.style.cssText = 'position:fixed;z-index:999998;background:#111;color:#ccc;font:11px monospace;padding:4px 8px;border-radius:3px;pointer-events:none;display:none;max-width:320px;word-break:break-all';
  document.body.appendChild(tooltip);

  // --- role picker popup ---
  var picker = document.createElement('div');
  picker.style.cssText = 'position:fixed;z-index:999999;background:#1c1c1c;border:1px solid #333;border-radius:6px;padding:8px;display:none;box-shadow:0 4px 16px rgba(0,0,0,.8)';
  document.body.appendChild(picker);

  var currentTarget = null;

  function cssSelector(el) {
    if (el.id) return '#' + el.id;
    var parts = [];
    while (el && el.nodeType === 1 && el !== document.body) {
      var part = el.tagName.toLowerCase();
      var cls = Array.from(el.classList).filter(function(c){ return !/^(active|selected|hover|focus)$/i.test(c); }).slice(0,2);
      if (cls.length) part += '.' + cls.join('.');
      parts.unshift(part);
      el = el.parentElement;
    }
    return parts.join(' > ');
  }

  // --- highlight all elements matching current selections ---
  function reHighlight() {
    document.querySelectorAll('[data-sel-role]').forEach(function (el) {
      el.removeAttribute('data-sel-role');
      el.style.outline = '';
    });
    ROLES.forEach(function (role) {
      if (!selections[role]) return;
      try {
        document.querySelectorAll(selections[role]).forEach(function (el) {
          el.setAttribute('data-sel-role', role);
          el.style.outline = '2px solid ' + COLORS[role];
        });
      } catch(e) {}
    });
  }

  // --- hover ---
  document.addEventListener('mouseover', function (e) {
    if (panel.contains(e.target) || picker.contains(e.target)) return;
    var sel = cssSelector(e.target);
    tooltip.textContent = sel;
    tooltip.style.display = 'block';
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY + 12) + 'px';
  });
  document.addEventListener('mousemove', function (e) {
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY + 12) + 'px';
  });
  document.addEventListener('mouseout', function () {
    tooltip.style.display = 'none';
  });

  // --- click → role picker ---
  document.addEventListener('click', function (e) {
    if (panel.contains(e.target) || picker.contains(e.target)) return;
    e.preventDefault();
    e.stopPropagation();
    currentTarget = e.target;
    var sel = cssSelector(e.target);

    var html = '<div style="font:12px monospace;color:#aaa;margin-bottom:8px">Tag as:</div>';
    ROLES.forEach(function (role) {
      html += '<button data-role="' + role + '" class="__role_btn" style="display:block;width:100%;margin-bottom:4px;padding:5px 12px;background:#2a2a2a;color:' + COLORS[role] + ';border:1px solid ' + COLORS[role] + '55;border-radius:4px;cursor:pointer;font:inherit;text-align:left">' + LABELS[role] + '</button>';
    });
    html += '<button id="__cancel_pick" style="display:block;width:100%;margin-top:4px;padding:5px 12px;background:transparent;color:#555;border:1px solid #333;border-radius:4px;cursor:pointer;font:inherit">Cancel</button>';
    picker.innerHTML = html;
    picker.style.display = 'block';
    picker.style.left = Math.min(e.clientX, window.innerWidth - 200) + 'px';
    picker.style.top = Math.min(e.clientY, window.innerHeight - 200) + 'px';

    picker.querySelectorAll('.__role_btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        selections[btn.dataset.role] = cssSelector(currentTarget);
        picker.style.display = 'none';
        renderPanel();
        reHighlight();
      });
    });
    document.getElementById('__cancel_pick').addEventListener('click', function () {
      picker.style.display = 'none';
    });
  }, true);

  document.body.appendChild(panel);
  renderPanel();
})();
</script>
"""

# ── Proxy ─────────────────────────────────────────────────────────────────────

def _rewrite_urls(html: str, base_url: str, proxy_prefix: str) -> str:
    """Rewrite src/href to route static assets through the proxy."""
    parsed = urlparse(base_url)
    origin = f'{parsed.scheme}://{parsed.netloc}'

    def rewrite(attr: str, m: re.Match) -> str:
        url = m.group(1)
        if url.startswith('data:') or url.startswith('javascript:') or url.startswith('#'):
            return m.group(0)
        abs_url = urljoin(base_url, url)
        return f'{attr}="{proxy_prefix}?url={quote(abs_url, safe="")}"'

    html = re.sub(r'src="([^"]*)"', lambda m: rewrite('src', m), html)
    html = re.sub(r"src='([^']*)'", lambda m: rewrite('src', m), html)
    # Don't rewrite hrefs — we want clicks to be intercepted by the overlay JS
    return html


@bp.get('/proxy')
def proxy():
    from flask_jwt_extended import decode_token
    from jwt.exceptions import InvalidTokenError
    token = request.args.get('token', '').strip()
    if not token:
        return jsonify({'error': 'token parameter required'}), 401
    try:
        decoded = decode_token(token)
    except Exception:
        return jsonify({'error': 'Invalid or expired token'}), 401

    user = User.query.get(int(decoded['sub']))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin only'}), 403

    url = validate_external_url(request.args.get('url', '').strip())
    if not url:
        return jsonify({'error': 'A valid external url parameter is required'}), 400

    try:
        resp = requests.get(url, timeout=15, headers=PROXY_HEADERS)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({'error': f'Failed to fetch page: {e}'}), 502

    html = resp.text
    proxy_prefix = request.host_url.rstrip('/') + '/api/scraper/proxy'
    html = _rewrite_urls(html, url, proxy_prefix)
    html = html.replace('</body>', OVERLAY_JS + '</body>', 1)

    return Response(html, content_type='text/html; charset=utf-8')


# ── Test selectors ─────────────────────────────────────────────────────────────

@bp.post('/test')
@jwt_required()
def test():
    user = User.query.get(int(get_jwt_identity()))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    data = request.get_json()
    url = validate_external_url((data.get('url') or '').strip())
    title_sel = sanitize_str(data.get('titleSelector'), max_length=500)
    cover_sel = sanitize_str(data.get('coverSelector'), max_length=500) or None
    chapter_sel = sanitize_str(data.get('chapterLinkSelector'), max_length=500)
    container_sel = sanitize_str(data.get('containerSelector'), max_length=500) or None

    if not url or not title_sel or not chapter_sel:
        return jsonify({'error': 'A valid external url, titleSelector, and chapterLinkSelector are required'}), 400

    try:
        result = test_selectors(url, title_sel, cover_sel, chapter_sel, container_sel)
    except Exception as e:
        return jsonify({'error': f'Invalid selector: {e}'}), 400
    return jsonify(result)


# ── Save site + trigger re-scrape ─────────────────────────────────────────────

@bp.post('/sites')
@jwt_required()
def save_site():
    user = User.query.get(int(get_jwt_identity()))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    data = request.get_json()

    url = validate_external_url((data.get('url') or '').strip())
    name = sanitize_str(data.get('name') or (urlparse(url).netloc if url else ''), max_length=100)
    title_sel = sanitize_str(data.get('titleSelector'), max_length=500)
    cover_sel = sanitize_str(data.get('coverSelector'), max_length=500) or None
    chapter_sel = sanitize_str(data.get('chapterLinkSelector'), max_length=500)
    container_sel = sanitize_str(data.get('containerSelector'), max_length=500) or None
    chapter_image_sel = sanitize_str(data.get('chapterImageSelector'), max_length=500) or None

    if not url or not title_sel or not chapter_sel:
        return jsonify({'error': 'A valid external url, titleSelector, and chapterLinkSelector are required'}), 400

    site = ScraperSite.query.filter_by(latest_releases_url=url).first()
    if site:
        site.name = name
        site.container_selector = container_sel
        site.chapter_image_selector = chapter_image_sel
        site.title_selector = title_sel
        site.cover_selector = cover_sel
        site.chapter_link_selector = chapter_sel
    else:
        site = ScraperSite(
            name=name,
            latest_releases_url=url,
            container_selector=container_sel,
            chapter_image_selector=chapter_image_sel,
            title_selector=title_sel,
            cover_selector=cover_sel,
            chapter_link_selector=chapter_sel,
        )
        db.session.add(site)
        db.session.flush()

    # Scrape the new source
    scraped = scrape_with_selectors(url, title_sel, cover_sel, chapter_sel)

    # Fuzzy-match scraped results against the user's manga library
    user_manga_entries = UserManga.query.filter_by(user_id=user.id).join(Manga).all()
    library = [e.manga for e in user_manga_entries]
    matches = match_scraped_to_library(scraped, library)

    auto_linked = []
    for m in matches['auto']:
        _upsert_source_entry(m['manga'], site, m['scraped'])
        auto_linked.append({'mangaId': m['manga'].id, 'title': m['manga'].title, 'score': round(m['score'], 1)})

    db.session.commit()

    return jsonify({
        'site': site.to_dict(),
        'autoLinked': auto_linked,
        'suggestions': [
            {
                'mangaId': m['manga'].id,
                'title': m['manga'].title,
                'matchedTitle': m['scraped']['title'],
                'score': round(m['score'], 1),
                'scraped': m['scraped'],
            }
            for m in matches['suggest']
        ],
    }), 201


# ── Test chapter image selector ───────────────────────────────────────────────

@bp.post('/test-chapter')
@jwt_required()
def test_chapter():
    user = User.query.get(int(get_jwt_identity()))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    data = request.get_json()
    url = validate_external_url((data.get('url') or '').strip())
    image_sel = sanitize_str(data.get('chapterImageSelector'), max_length=500)

    if not url or not image_sel:
        return jsonify({'error': 'A valid external url and chapterImageSelector are required'}), 400

    if image_sel.startswith('mangadex_athome:'):
        from .reader import _fetch_mangadex_athome_images
        images = _fetch_mangadex_athome_images(url)
        return jsonify({'images': images[:20]})

    if image_sel.startswith('fanfox:'):
        from ..scrapers.fanfox import fetch_chapter_images
        images = fetch_chapter_images(url)
        return jsonify({'images': images[:20]})

    if image_sel.startswith('browser:'):
        from ..scrapers.browser import scrape_chapter_images
        images = scrape_chapter_images(url, image_sel[8:])
        return jsonify({'images': images[:20]})

    try:
        resp = requests.get(url, timeout=15, headers=PROXY_HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')
    except Exception as e:
        return jsonify({'error': f'Failed to fetch page: {e}'}), 502

    from .reader import _extract_next_data_images, _extract_regex_images, _extract_css_images
    if image_sel == '__NEXT_DATA__':
        images = _extract_next_data_images(soup)
    elif image_sel.startswith('regex:'):
        images = _extract_regex_images(resp.text, image_sel[6:])
    else:
        images = _extract_css_images(soup, image_sel, url)

    return jsonify({'images': images[:20]})


def _upsert_source_entry(manga, site, scraped: dict):
    entry = MangaSourceEntry.query.filter_by(manga_id=manga.id, site_id=site.id).first()
    if entry:
        entry.latest_chapter = scraped['chapter']
        entry.latest_chapter_url = scraped['chapter_url']
        entry.updated_at = datetime.now(timezone.utc)
    else:
        db.session.add(MangaSourceEntry(
            manga_id=manga.id,
            site_id=site.id,
            latest_chapter=scraped['chapter'],
            latest_chapter_url=scraped['chapter_url'],
        ))
    if not manga.cover_url and scraped.get('cover_url'):
        manga.cover_url = scraped['cover_url']


# ── Confirm a manual suggestion ───────────────────────────────────────────────

@bp.post('/sites/<int:site_id>/confirm-match')
@jwt_required()
def confirm_match(site_id: int):
    """Called when the user manually confirms a fuzzy suggestion."""
    user = User.query.get(int(get_jwt_identity()))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    data = request.get_json()
    manga_id = data.get('mangaId')
    scraped = data.get('scraped')  # {title, cover_url, chapter, chapter_url}

    if not manga_id or not scraped:
        return jsonify({'error': 'mangaId and scraped are required'}), 400

    site = ScraperSite.query.get_or_404(site_id)
    manga = Manga.query.get_or_404(manga_id)
    _upsert_source_entry(manga, site, scraped)
    db.session.commit()
    return jsonify({'ok': True})


# ── List sites ────────────────────────────────────────────────────────────────

@bp.get('/sites')
@jwt_required()
def list_sites():
    sites = ScraperSite.query.filter_by(is_active=True).all()
    return jsonify([s.to_dict() for s in sites])


# ── Delete site ───────────────────────────────────────────────────────────────

@bp.delete('/sites/<int:site_id>')
@jwt_required()
def delete_site(site_id: int):
    user = User.query.get(int(get_jwt_identity()))
    if not user.is_admin:
        return jsonify({'error': 'Admin only'}), 403
    site = ScraperSite.query.get_or_404(site_id)
    db.session.delete(site)
    db.session.commit()
    return '', 204
