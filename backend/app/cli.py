import click
from .extensions import db
from .models import Invite, User, ScraperSite

_PRECONFIGURED_SITES = [
    {
        'name': 'MangaDex',
        'latest_releases_url': 'https://mangadex.org',
        'title_selector': '',
        'chapter_link_selector': '',
        'container_selector': None,
        'cover_selector': None,
        'chapter_image_selector': 'mangadex_athome:',
        'is_active': True,
    },
    {
        'name': 'AsuraScans',
        'latest_releases_url': 'https://asurascans.com/',
        'container_selector': 'div.grid.grid-cols-12.gap-2.py-4',
        'title_selector': 'a.font-bold',
        'chapter_link_selector': 'a[href*="/chapter/"]',
        'cover_selector': 'img',
        'chapter_image_selector': 'browser:img[src*="cdn.asurascans.com"]',
        'search_url_template': 'https://www.asurascans.com/browse?search={title}',
        'is_active': True,
    },
    {
        'name': 'VortexScans',
        'latest_releases_url': 'https://vortexscans.org/',
        'container_selector': 'div.flex-1.flex.flex-col.min-w-0',
        'title_selector': 'a[href*="/series/"]:not([href*="/chapter-"])',
        'chapter_link_selector': 'a[href*="/chapter-"]',
        'cover_selector': None,
        'chapter_image_selector': 'img[data-reader-page-image]',
        'search_url_template': 'https://vortexscans.org/series?searchTerm={title}',
        'is_active': True,
    },
    {
        'name': 'Yomi Manga',
        'latest_releases_url': 'https://yomimanga.com/',
        'container_selector': 'div.manga-item',
        'title_selector': 'p.line-clamp-2',
        'chapter_link_selector': 'a[href*="/chapter/"]',
        'cover_selector': 'img.lazy-image',
        'chapter_image_selector': 'browser:#chapter-images img',
        'search_url_template': 'https://yomimanga.com/search?q={title}',
        'is_active': True,
    },
    {
        'name': 'Mangafox',
        'latest_releases_url': 'https://fanfox.net/',
        'container_selector': 'ul.manga-list-1-list > li',
        'title_selector': 'p.manga-list-1-item-title a',
        'chapter_link_selector': 'p.manga-list-1-item-subtitle a',
        'cover_selector': 'img.manga-list-1-cover',
        'chapter_image_selector': 'fanfox:',
        'search_url_template': 'https://fanfox.net/search?title={title}',
        'is_active': True,
    },
]


def register_cli(app):
    @app.cli.group()
    def invite():
        """Manage invite codes."""

    @invite.command('create')
    def create_invite():
        """Generate a new invite code."""
        with app.app_context():
            inv = Invite.generate()
            click.echo(f'Invite created: {inv.code}')
            click.echo(f'Join URL: {app.config["FRONTEND_URL"]}/join?code={inv.code}')

    @invite.command('list')
    def list_invites():
        """List all invite codes."""
        with app.app_context():
            invites = Invite.query.all()
            for inv in invites:
                status = 'used' if inv.used else 'available'
                click.echo(f'{inv.code}  [{status}]  created {inv.created_at}')

    @app.cli.group()
    def user():
        """Manage users."""

    @user.command('make-admin')
    @click.argument('email')
    def make_admin(email):
        """Grant admin privileges to a user by email."""
        with app.app_context():
            u = User.query.filter_by(email=email).first()
            if not u:
                click.echo(f'No user found with email: {email}', err=True)
                return
            u.is_admin = True
            db.session.commit()
            click.echo(f'Admin granted to {u.display_name} <{u.email}>')

    @user.command('list')
    def list_users():
        """List all registered users."""
        with app.app_context():
            users = User.query.all()
            for u in users:
                admin = ' [admin]' if u.is_admin else ''
                click.echo(f'{u.id:>4}  {u.email}  ({u.oauth_provider}){admin}')

    @app.cli.command('seed-sites')
    def seed_sites():
        """Insert preconfigured scraper sites if they don't already exist."""
        with app.app_context():
            for cfg in _PRECONFIGURED_SITES:
                exists = ScraperSite.query.filter_by(
                    latest_releases_url=cfg['latest_releases_url']
                ).first()
                if exists:
                    click.echo(f'  skipped  {cfg["name"]}')
                    continue
                db.session.add(ScraperSite(**cfg))
                click.echo(f'  created  {cfg["name"]}')

            # Back-fill chapter_image_selector on existing rows that have none
            for cfg in _PRECONFIGURED_SITES:
                if not cfg.get('chapter_image_selector'):
                    continue
                site = ScraperSite.query.filter_by(latest_releases_url=cfg['latest_releases_url']).first()
                if site and site.chapter_image_selector is None:
                    site.chapter_image_selector = cfg['chapter_image_selector']
                    click.echo(f'  updated  {cfg["name"]} chapter_image_selector')

            # Fix Mangafox: upgrade from browser: placeholder to proper fanfox: scraper
            fanfox_site = ScraperSite.query.filter_by(latest_releases_url='https://fanfox.net/').first()
            if fanfox_site and fanfox_site.chapter_image_selector == 'browser:img.reader-main-img':
                fanfox_site.chapter_image_selector = 'fanfox:'
                click.echo('  updated  Mangafox chapter_image_selector → fanfox:')

            # Back-fill search_url_template on existing rows that have none
            for cfg in _PRECONFIGURED_SITES:
                if not cfg.get('search_url_template'):
                    continue
                site = ScraperSite.query.filter_by(latest_releases_url=cfg['latest_releases_url']).first()
                if site and site.search_url_template is None:
                    site.search_url_template = cfg['search_url_template']
                    click.echo(f'  updated  {cfg["name"]} search_url_template')

            db.session.commit()
