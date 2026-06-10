import { test, expect, type Page } from '@playwright/test';
import type { MangaEntry } from '../src/types';

// ── Mock data ─────────────────────────────────────────────────────────────────

function makeManga(overrides: Partial<MangaEntry> = {}): MangaEntry {
	return {
		id: 1,
		title: 'Test Manga',
		coverUrl: null,
		latestChapter: 10,
		sources: [
			{
				siteId: 1,
				siteName: 'AsuraScans',
				latestChapter: 10,
				latestChapterUrl: 'https://asuracomic.net/series/test/chapter/10',
				updatedAt: null,
			},
		],
		currentChapter: 8,
		currentChapterUrl: 'https://asuracomic.net/series/test/chapter/8',
		hasUpdate: false,
		updatedAt: null,
		...overrides,
	};
}

const MANGA_1 = makeManga({ id: 1, title: 'Solo Leveling' });
const MANGA_2 = makeManga({ id: 2, title: 'Nano Machine' });

// ── Base mock setup ───────────────────────────────────────────────────────────

async function setupAuth(page: Page) {
	await page.addInitScript(() => {
		localStorage.setItem('token', 'test-token');
	});
	await page.route('**/api/user/me', (route) =>
		route.fulfill({
			json: { id: 1, displayName: 'Test User', email: 'test@test.com', isAdmin: false, avatarUrl: null },
		}),
	);
}

// ── Tests: Manga list renders ─────────────────────────────────────────────────

test('manga list renders 2 cards when API returns 2 items', async ({ page }) => {
	await setupAuth(page);
	await page.route('**/api/manga/', (route) => route.fulfill({ json: [MANGA_1, MANGA_2] }));

	await page.goto('/');
	await expect(page.locator('.manga-card')).toHaveCount(2);
});

test('manga card shows the title', async ({ page }) => {
	await setupAuth(page);
	await page.route('**/api/manga/', (route) => route.fulfill({ json: [MANGA_1] }));

	await page.goto('/');
	await expect(page.locator('.manga-title').first()).toContainText('Solo Leveling');
});

test('shows empty state when list is empty', async ({ page }) => {
	await setupAuth(page);
	await page.route('**/api/manga/', (route) => route.fulfill({ json: [] }));

	await page.goto('/');
	await expect(page.locator('.state-msg.empty')).toBeVisible();
});

test('shows all returned cards without duplicates', async ({ page }) => {
	await setupAuth(page);
	await page.route('**/api/manga/', (route) => route.fulfill({ json: [MANGA_1, MANGA_2] }));

	await page.goto('/');
	const titles = await page.locator('.manga-title').allTextContents();
	// Sort because the store sorts by title
	const sorted = [...titles].sort();
	assert_includes(sorted, 'Nano Machine');
	assert_includes(sorted, 'Solo Leveling');

	function assert_includes(arr: string[], value: string) {
		expect(arr.some((t) => t.includes(value))).toBe(true);
	}
});

// ── Tests: Add manga ──────────────────────────────────────────────────────────

test('add manga form submits title and shows new card', async ({ page }) => {
	let postCalled = false;
	const newManga = makeManga({ id: 3, title: 'My New Manga' });

	await setupAuth(page);
	// Start with empty list
	await page.route('**/api/manga/', (route) => {
		if (route.request().method() === 'GET') {
			route.fulfill({ json: [] });
		} else if (route.request().method() === 'POST') {
			postCalled = true;
			route.fulfill({ json: newManga });
		}
	});

	await page.goto('/');
	await expect(page.locator('.state-msg.empty')).toBeVisible();

	await page.locator('.add-input').fill('My New Manga');
	await page.locator('.add-btn').click();

	// Card should now appear
	await expect(page.locator('.manga-card')).toHaveCount(1);
	await expect(page.locator('.manga-title').first()).toContainText('My New Manga');
	expect(postCalled).toBe(true);
});

test('add form is cleared after a successful add', async ({ page }) => {
	const newManga = makeManga({ id: 4, title: 'Another Series' });

	await setupAuth(page);
	await page.route('**/api/manga/', (route) => {
		if (route.request().method() === 'GET') {
			route.fulfill({ json: [] });
		} else if (route.request().method() === 'POST') {
			route.fulfill({ json: newManga });
		}
	});

	await page.goto('/');
	await page.locator('.add-input').fill('Another Series');
	await page.locator('.add-btn').click();

	await expect(page.locator('.manga-card')).toHaveCount(1);
	await expect(page.locator('.add-input')).toHaveValue('');
});

test('add form shows error message when POST fails', async ({ page }) => {
	await setupAuth(page);
	await page.route('**/api/manga/', (route) => {
		if (route.request().method() === 'GET') {
			route.fulfill({ json: [] });
		} else if (route.request().method() === 'POST') {
			route.fulfill({ status: 400, json: { error: 'Manga not found' } });
		}
	});

	await page.goto('/');
	await page.locator('.add-input').fill('Unknown Manga');
	await page.locator('.add-btn').click();

	await expect(page.locator('.add-error')).toBeVisible();
});

// ── Tests: Reader opens ───────────────────────────────────────────────────────

test('clicking a source chapter link navigates to /reader', async ({ page }) => {
	await setupAuth(page);
	await page.route('**/api/manga/', (route) => route.fulfill({ json: [MANGA_1] }));
	// Mock the progress update and reader images for when the reader loads
	await page.route('**/api/manga/*/progress', (route) =>
		route.fulfill({ json: { id: 1, currentChapter: 10 } }),
	);
	await page.route('**/api/reader/images**', (route) =>
		route.fulfill({ json: { images: ['https://cdn.example.com/01.webp'] } }),
	);
	await page.route('**/api/reader/proxy-image**', (route) =>
		route.fulfill({
			status: 200,
			contentType: 'image/png',
			body: Buffer.from(
				'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
				'base64',
			),
		}),
	);

	await page.goto('/');
	// The source chapter link triggers openReader — it's an <a href="#"> with @click.prevent
	await page.locator('.chapter-link.accent, a.chapter-link').first().click();

	await expect(page).toHaveURL(/\/reader/);
});
