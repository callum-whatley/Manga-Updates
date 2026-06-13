import { strict as assert } from 'assert';
import { chapterNumFromUrl, buildChapterUrl } from '../src/utils/reader';

// ── chapterNumFromUrl ─────────────────────────────────────────────────────────

describe('chapterNumFromUrl', () => {
	it('extracts an integer chapter number', () => {
		assert.equal(chapterNumFromUrl('https://site.com/series/foo/chapter/166'), 166);
	});

	it('extracts a decimal chapter number', () => {
		assert.equal(chapterNumFromUrl('https://site.com/series/foo/chapter/166.5'), 166.5);
	});

	it('extracts chapter 1', () => {
		assert.equal(chapterNumFromUrl('https://site.com/series/foo/chapter/1'), 1);
	});

	it('is case-insensitive on the "Chapter" token', () => {
		assert.equal(chapterNumFromUrl('https://site.com/series/foo/Chapter/10'), 10);
	});

	it('works when chapter is not the last path segment', () => {
		assert.equal(chapterNumFromUrl('https://site.com/series/foo/chapter/5/page/3'), 5);
	});

	it('returns null when URL has no chapter segment', () => {
		assert.equal(chapterNumFromUrl('https://site.com/series/foo'), null);
	});

	it('returns null for an empty string', () => {
		assert.equal(chapterNumFromUrl(''), null);
	});

	it('works for the real AsuraScans URL shape', () => {
		assert.equal(
			chapterNumFromUrl('https://asuracomic.net/series/return-of-the-disaster-class-hero-4a5ff4a9/chapter/166'),
			166,
		);
	});
});

// ── buildChapterUrl ───────────────────────────────────────────────────────────

describe('buildChapterUrl', () => {
	it('replaces the chapter number with a higher number', () => {
		assert.equal(
			buildChapterUrl('https://site.com/series/foo/chapter/5', 6),
			'https://site.com/series/foo/chapter/6',
		);
	});

	it('replaces the chapter number with a lower number', () => {
		assert.equal(
			buildChapterUrl('https://site.com/series/foo/chapter/10', 9),
			'https://site.com/series/foo/chapter/9',
		);
	});

	it('handles a decimal chapter number in the URL', () => {
		assert.equal(
			buildChapterUrl('https://site.com/series/foo/chapter/5.5', 6),
			'https://site.com/series/foo/chapter/6',
		);
	});

	it('handles the real AsuraScans URL shape', () => {
		assert.equal(
			buildChapterUrl(
				'https://asuracomic.net/series/return-of-the-disaster-class-hero-4a5ff4a9/chapter/304',
				305,
			),
			'https://asuracomic.net/series/return-of-the-disaster-class-hero-4a5ff4a9/chapter/305',
		);
	});

	it('is case-insensitive on the "Chapter" token', () => {
		assert.equal(
			buildChapterUrl('https://site.com/series/foo/Chapter/3', 4),
			'https://site.com/series/foo/chapter/4',
		);
	});

	it('does not alter unrelated parts of the URL', () => {
		const url = 'https://site.com/series/foo-123abc/chapter/7';
		const result = buildChapterUrl(url, 8);
		assert.ok(result!.startsWith('https://site.com/series/foo-123abc/chapter/'));
		assert.ok(result!.endsWith('/8'));
	});

	it('returns null for a Fanfox volume-prefixed URL', () => {
		assert.equal(
			buildChapterUrl('https://fanfox.net/manga/vinland-saga/v25/c220/1.html', 221),
			null,
		);
	});

	it('returns null for a Fanfox URL with volume v01', () => {
		assert.equal(
			buildChapterUrl('https://fanfox.net/manga/vinland-saga/v01/c001/1.html', 220),
			null,
		);
	});

	it('returns null regardless of volume number for Fanfox volume-prefixed URL', () => {
		assert.equal(
			buildChapterUrl('https://fanfox.net/manga/some-manga/v99/c500/1.html', 501),
			null,
		);
	});
});
