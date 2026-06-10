"""
Unit tests for the image-extraction helpers in app/api/reader.py.

Run with:
    pytest test/test_reader.py
"""

import json
from bs4 import BeautifulSoup

from app.api.reader import _extract_regex_images, _extract_next_data_images, _extract_css_images


# ── _extract_regex_images ─────────────────────────────────────────────────────

class TestExtractRegexImages:
    def test_returns_matching_url(self):
        html = '<p>See https://cdn.site.com/01-optimized.webp here</p>'
        result = _extract_regex_images(html, r'https://cdn\.site\.com/\d+-optimized\.webp')
        assert result == ['https://cdn.site.com/01-optimized.webp']

    def test_deduplicates_identical_urls(self):
        html = 'https://cdn.site.com/01.webp https://cdn.site.com/01.webp'
        result = _extract_regex_images(html, r'https://cdn\.site\.com/\d+\.webp')
        assert result == ['https://cdn.site.com/01.webp']

    def test_sorts_results_by_page_number(self):
        html = (
            'https://cdn.site.com/03-optimized.webp '
            'https://cdn.site.com/01-optimized.webp '
            'https://cdn.site.com/02-optimized.webp'
        )
        result = _extract_regex_images(html, r'https://cdn\.site\.com/\d+-optimized\.webp')
        assert result == [
            'https://cdn.site.com/01-optimized.webp',
            'https://cdn.site.com/02-optimized.webp',
            'https://cdn.site.com/03-optimized.webp',
        ]

    def test_sort_handles_zero_padded_numbers(self):
        html = 'https://cdn.site.com/10.webp https://cdn.site.com/09.webp https://cdn.site.com/11.webp'
        result = _extract_regex_images(html, r'https://cdn\.site\.com/\d+\.webp')
        assert result == [
            'https://cdn.site.com/09.webp',
            'https://cdn.site.com/10.webp',
            'https://cdn.site.com/11.webp',
        ]

    def test_invalid_regex_returns_empty_list(self):
        result = _extract_regex_images('<p>hello</p>', r'[invalid(')
        assert result == []

    def test_no_matches_returns_empty_list(self):
        result = _extract_regex_images('<p>hello world</p>', r'https://never\.example\.com/\w+')
        assert result == []

    def test_empty_html_returns_empty_list(self):
        result = _extract_regex_images('', r'https://cdn\.site\.com/\d+\.webp')
        assert result == []


# ── _extract_next_data_images ─────────────────────────────────────────────────

def _make_next_data_soup(data: dict) -> BeautifulSoup:
    html = f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'
    return BeautifulSoup(html, 'html.parser')


class TestExtractNextDataImages:
    def test_extracts_image_url_from_nested_structure(self):
        data = {'props': {'pageProps': {'images': ['https://cdn.site.com/page1.webp']}}}
        soup = _make_next_data_soup(data)
        result = _extract_next_data_images(soup)
        assert 'https://cdn.site.com/page1.webp' in result

    def test_extracts_image_url_from_top_level_string_value(self):
        data = {'imageUrl': 'https://example.com/cover.jpg'}
        soup = _make_next_data_soup(data)
        result = _extract_next_data_images(soup)
        assert 'https://example.com/cover.jpg' in result

    def test_deduplicates_repeated_image_urls(self):
        data = {'a': 'https://example.com/page.png', 'b': 'https://example.com/page.png'}
        soup = _make_next_data_soup(data)
        result = _extract_next_data_images(soup)
        assert result.count('https://example.com/page.png') == 1

    def test_extracts_multiple_formats(self):
        data = {
            'img1': 'https://cdn.site.com/01.jpg',
            'img2': 'https://cdn.site.com/02.png',
            'img3': 'https://cdn.site.com/03.webp',
        }
        soup = _make_next_data_soup(data)
        result = _extract_next_data_images(soup)
        assert len(result) == 3

    def test_missing_script_tag_returns_empty_list(self):
        soup = BeautifulSoup('<html><body>no script here</body></html>', 'html.parser')
        assert _extract_next_data_images(soup) == []

    def test_invalid_json_returns_empty_list(self):
        html = '<script id="__NEXT_DATA__">not valid json {{{</script>'
        soup = BeautifulSoup(html, 'html.parser')
        assert _extract_next_data_images(soup) == []

    def test_empty_json_object_returns_empty_list(self):
        soup = _make_next_data_soup({})
        assert _extract_next_data_images(soup) == []


# ── _extract_css_images ───────────────────────────────────────────────────────

class TestExtractCssImages:
    def test_extracts_src_attribute(self):
        html = '<div class="wrap"><img class="page" src="https://cdn.site.com/p1.jpg" /></div>'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'div.wrap img.page', 'https://cdn.site.com/')
        assert result == ['https://cdn.site.com/p1.jpg']

    def test_falls_back_to_data_src(self):
        html = '<img class="lazy" data-src="https://cdn.site.com/p2.jpg" />'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.lazy', 'https://cdn.site.com/')
        assert result == ['https://cdn.site.com/p2.jpg']

    def test_falls_back_to_data_lazy_src(self):
        html = '<img class="lazy2" data-lazy-src="https://cdn.site.com/p3.jpg" />'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.lazy2', 'https://cdn.site.com/')
        assert result == ['https://cdn.site.com/p3.jpg']

    def test_prefers_src_over_data_src(self):
        html = '<img class="p" src="https://cdn.site.com/a.jpg" data-src="https://cdn.site.com/b.jpg" />'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.p', 'https://cdn.site.com/')
        assert result == ['https://cdn.site.com/a.jpg']

    def test_resolves_relative_url(self):
        html = '<img class="page" src="/images/p1.jpg" />'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.page', 'https://cdn.site.com/chapter/1')
        assert result == ['https://cdn.site.com/images/p1.jpg']

    def test_skips_elements_without_any_src_attribute(self):
        html = '<img class="page" alt="no src" />'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.page', 'https://cdn.site.com/')
        assert result == []

    def test_no_matching_elements_returns_empty_list(self):
        html = '<div>no images here</div>'
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.page', 'https://cdn.site.com/')
        assert result == []

    def test_extracts_multiple_images(self):
        html = (
            '<img class="page" src="https://cdn.site.com/p1.jpg" />'
            '<img class="page" src="https://cdn.site.com/p2.jpg" />'
            '<img class="page" src="https://cdn.site.com/p3.jpg" />'
        )
        soup = BeautifulSoup(html, 'html.parser')
        result = _extract_css_images(soup, 'img.page', 'https://cdn.site.com/')
        assert result == [
            'https://cdn.site.com/p1.jpg',
            'https://cdn.site.com/p2.jpg',
            'https://cdn.site.com/p3.jpg',
        ]
