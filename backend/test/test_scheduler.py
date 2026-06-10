"""
Unit tests for app/scheduler.py.

Run with:
    pytest test/test_scheduler.py
"""

from unittest.mock import patch, MagicMock, call

from app.scheduler import start_scheduler, _check_all_users


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_app():
    app = MagicMock()
    ctx = app.app_context.return_value
    ctx.__enter__ = MagicMock(return_value=None)
    ctx.__exit__ = MagicMock(return_value=False)
    return app


def _setup_site_query(MockSite, active_sites, mdx_site=None):
    """Configure ScraperSite.query.filter_by to serve both call patterns."""
    def filter_by_side_effect(**kwargs):
        m = MagicMock()
        if 'is_active' in kwargs:
            m.all.return_value = active_sites
        elif kwargs.get('name') == 'MangaDex':
            m.first.return_value = mdx_site
        else:
            m.all.return_value = []
            m.first.return_value = None
        return m
    MockSite.query.filter_by.side_effect = filter_by_side_effect


# ── start_scheduler ───────────────────────────────────────────────────────────

class TestStartScheduler:
    def test_registers_job_with_cron_trigger(self):
        app = MagicMock()
        app.debug = False

        with patch('app.scheduler.BackgroundScheduler') as MockScheduler:
            instance = MockScheduler.return_value
            start_scheduler(app)

        instance.add_job.assert_called_once()
        _, kwargs = instance.add_job.call_args
        assert kwargs['trigger'] == 'cron'
        assert kwargs['hour'] == '6,18'
        assert kwargs['minute'] == 0

    def test_passes_app_as_job_argument(self):
        app = MagicMock()
        app.debug = False

        with patch('app.scheduler.BackgroundScheduler') as MockScheduler:
            instance = MockScheduler.return_value
            start_scheduler(app)

        _, kwargs = instance.add_job.call_args
        assert kwargs['args'] == [app]

    def test_starts_scheduler(self):
        app = MagicMock()
        app.debug = False

        with patch('app.scheduler.BackgroundScheduler') as MockScheduler:
            instance = MockScheduler.return_value
            start_scheduler(app)

        instance.start.assert_called_once()

    def test_skips_start_in_debug_reloader_parent(self, monkeypatch):
        """When debug=True and WERKZEUG_RUN_MAIN is unset, scheduler must not start."""
        monkeypatch.delenv('WERKZEUG_RUN_MAIN', raising=False)
        app = MagicMock()
        app.debug = True

        with patch('app.scheduler.BackgroundScheduler') as MockScheduler:
            start_scheduler(app)

        MockScheduler.return_value.start.assert_not_called()

    def test_starts_in_debug_reloader_child(self, monkeypatch):
        """When debug=True and WERKZEUG_RUN_MAIN='true', scheduler should start."""
        monkeypatch.setenv('WERKZEUG_RUN_MAIN', 'true')
        app = MagicMock()
        app.debug = True

        with patch('app.scheduler.BackgroundScheduler') as MockScheduler:
            instance = MockScheduler.return_value
            start_scheduler(app)

        instance.start.assert_called_once()


# ── _check_all_users — CSS-selector pass ─────────────────────────────────────

class TestCheckAllUsersCSS:
    def test_skips_everything_when_library_is_empty(self):
        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry') as mock_upsert,
            patch('app.scrapers.scrape_site') as mock_scrape,
            patch('app.scrapers.matcher.match_scraped_to_library') as mock_match,
            patch('app.scrapers.mangadex._fetch_one') as mock_mdx,
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[MagicMock()])
            MockManga.query.all.return_value = []

            _check_all_users(_make_app())

        mock_scrape.assert_not_called()
        mock_mdx.assert_not_called()
        mock_upsert.assert_not_called()

    def test_calls_scrape_for_each_active_site(self):
        site_a = MagicMock(name='SiteA')
        site_b = MagicMock(name='SiteB')
        manga = MagicMock()

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry'),
            patch('app.scrapers.scrape_site') as mock_scrape,
            patch('app.scrapers.matcher.match_scraped_to_library') as mock_match,
            patch('app.scrapers.mangadex._fetch_one', return_value=None),
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[site_a, site_b])
            MockManga.query.all.return_value = [manga]
            mock_scrape.return_value = []
            mock_match.return_value = {'auto': []}

            _check_all_users(_make_app())

        assert mock_scrape.call_count == 2
        mock_scrape.assert_any_call(site_a)
        mock_scrape.assert_any_call(site_b)

    def test_upserts_css_matched_entries(self):
        site = MagicMock()
        manga = MagicMock()
        scraped_data = {'chapter': 10, 'chapter_url': 'https://site.com/chapter/10'}

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry') as mock_upsert,
            patch('app.scrapers.scrape_site') as mock_scrape,
            patch('app.scrapers.matcher.match_scraped_to_library') as mock_match,
            patch('app.scrapers.mangadex._fetch_one', return_value=None),
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[site])
            MockManga.query.all.return_value = [manga]
            mock_scrape.return_value = [scraped_data]
            mock_match.return_value = {'auto': [{'manga': manga, 'scraped': scraped_data}]}

            _check_all_users(_make_app())

        mock_upsert.assert_any_call(manga, site, scraped_data)

    def test_continues_after_css_scrape_error(self):
        site_a = MagicMock(name='SiteA')
        site_b = MagicMock(name='SiteB')
        manga = MagicMock()

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry'),
            patch('app.scrapers.scrape_site') as mock_scrape,
            patch('app.scrapers.matcher.match_scraped_to_library') as mock_match,
            patch('app.scrapers.mangadex._fetch_one', return_value=None),
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[site_a, site_b])
            MockManga.query.all.return_value = [manga]
            mock_scrape.side_effect = [RuntimeError('network error'), []]
            mock_match.return_value = {'auto': []}

            _check_all_users(_make_app())

        # Both sites attempted despite the first one failing
        assert mock_scrape.call_count == 2


# ── _check_all_users — MangaDex pass ─────────────────────────────────────────

class TestCheckAllUsersMangaDex:
    def test_calls_mangadex_fetch_for_each_manga(self):
        manga_a = MagicMock(title='Solo Leveling')
        manga_b = MagicMock(title='Omniscient Reader')
        mdx_site = MagicMock(name='MangaDex')

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry'),
            patch('app.scrapers.scrape_site', return_value=[]),
            patch('app.scrapers.matcher.match_scraped_to_library', return_value={'auto': []}),
            patch('app.scrapers.mangadex._fetch_one', return_value=None) as mock_mdx,
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[], mdx_site=mdx_site)
            MockManga.query.all.return_value = [manga_a, manga_b]

            _check_all_users(_make_app())

        assert mock_mdx.call_count == 2
        mock_mdx.assert_any_call('Solo Leveling')
        mock_mdx.assert_any_call('Omniscient Reader')

    def test_upserts_mangadex_result_when_chapter_found(self):
        manga = MagicMock(title='Solo Leveling')
        mdx_site = MagicMock(name='MangaDex')
        mdx_info = {
            'chapter': 200,
            'chapter_url': 'https://mangadex.org/chapter/abc',
            'cover_url': 'https://covers.mangadex.org/abc.jpg',
        }

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry') as mock_upsert,
            patch('app.scrapers.scrape_site', return_value=[]),
            patch('app.scrapers.matcher.match_scraped_to_library', return_value={'auto': []}),
            patch('app.scrapers.mangadex._fetch_one', return_value=mdx_info),
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[], mdx_site=mdx_site)
            MockManga.query.all.return_value = [manga]

            _check_all_users(_make_app())

        mock_upsert.assert_any_call(manga, mdx_site, {
            'chapter': 200,
            'chapter_url': 'https://mangadex.org/chapter/abc',
            'cover_url': 'https://covers.mangadex.org/abc.jpg',
        })

    def test_skips_mangadex_upsert_when_no_chapter_returned(self):
        manga = MagicMock(title='Solo Leveling')
        mdx_site = MagicMock(name='MangaDex')

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry') as mock_upsert,
            patch('app.scrapers.scrape_site', return_value=[]),
            patch('app.scrapers.matcher.match_scraped_to_library', return_value={'auto': []}),
            patch('app.scrapers.mangadex._fetch_one', return_value={'chapter': None}),
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[], mdx_site=mdx_site)
            MockManga.query.all.return_value = [manga]

            _check_all_users(_make_app())

        mock_upsert.assert_not_called()

    def test_skips_mangadex_pass_when_no_mdx_site_in_db(self):
        manga = MagicMock(title='Solo Leveling')

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry'),
            patch('app.scrapers.scrape_site', return_value=[]),
            patch('app.scrapers.matcher.match_scraped_to_library', return_value={'auto': []}),
            patch('app.scrapers.mangadex._fetch_one') as mock_mdx,
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[], mdx_site=None)  # no MangaDex site
            MockManga.query.all.return_value = [manga]

            _check_all_users(_make_app())

        mock_mdx.assert_not_called()

    def test_continues_after_mangadex_fetch_error(self):
        manga_a = MagicMock(title='Solo Leveling')
        manga_b = MagicMock(title='Omniscient Reader')
        mdx_site = MagicMock(name='MangaDex')
        good_info = {
            'chapter': 50,
            'chapter_url': 'https://mangadex.org/chapter/xyz',
            'cover_url': None,
        }

        with (
            patch('app.models.ScraperSite') as MockSite,
            patch('app.models.Manga') as MockManga,
            patch('app.api.manga._upsert_source_entry') as mock_upsert,
            patch('app.scrapers.scrape_site', return_value=[]),
            patch('app.scrapers.matcher.match_scraped_to_library', return_value={'auto': []}),
            patch('app.scrapers.mangadex._fetch_one',
                  side_effect=[RuntimeError('API timeout'), good_info]) as mock_mdx,
            patch('app.extensions.db'),
        ):
            _setup_site_query(MockSite, active_sites=[], mdx_site=mdx_site)
            MockManga.query.all.return_value = [manga_a, manga_b]

            _check_all_users(_make_app())

        # Both titles attempted; second one still upserted
        assert mock_mdx.call_count == 2
        mock_upsert.assert_called_once_with(manga_b, mdx_site, {
            'chapter': 50,
            'chapter_url': 'https://mangadex.org/chapter/xyz',
            'cover_url': None,
        })
