import { test, expect, type Page } from '@playwright/test';

// ── Helpers ───────────────────────────────────────────────────────────────────

// 1×1 transparent PNG — used as the mock proxy-image response
const TINY_PNG = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
	'base64',
);

const READER_URL =
	'/reader?url=https%3A%2F%2Fsite.com%2Fseries%2Ffoo%2Fchapter%2F10&siteId=1&mangaId=1&chapter=10';

const CH1_URL =
	'/reader?url=https%3A%2F%2Fsite.com%2Fseries%2Ffoo%2Fchapter%2F1&siteId=1&mangaId=1&chapter=1';

async function setupMocks(page: Page) {
	// Auth token so the router guard passes
	await page.addInitScript(() => {
		localStorage.setItem('token', 'test-token');
	});

	// Auth / user endpoints
	await page.route('**/api/user/me', (route) =>
		route.fulfill({ json: { id: 1, displayName: 'Test', email: 'test@test.com' } }),
	);

	// Manga list (called by HomeView, harmless here)
	await page.route('**/api/manga/', (route) => route.fulfill({ json: [] }));

	// Progress updates triggered on navigation / route leave
	await page.route('**/api/manga/*/progress', (route) =>
		route.fulfill({ json: { id: 1, currentChapter: 10 } }),
	);

	// Reader images endpoint — return 3 test pages
	await page.route('**/api/reader/images**', (route) =>
		route.fulfill({
			json: {
				images: [
					'https://cdn.example.com/01.webp',
					'https://cdn.example.com/02.webp',
					'https://cdn.example.com/03.webp',
				],
			},
		}),
	);

	// Image proxy — return a valid tiny image for every proxied URL
	await page.route('**/api/reader/proxy-image**', (route) =>
		route.fulfill({ status: 200, contentType: 'image/png', body: TINY_PNG }),
	);
}

// ── Image loading ─────────────────────────────────────────────────────────────

test('renders all images returned by the API', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await expect(page.locator('.reader-images')).toBeVisible();
	await expect(page.locator('.reader-image')).toHaveCount(3);
});

test('shows error state when the images endpoint fails', async ({ page }) => {
	await setupMocks(page);
	await page.unroute('**/api/reader/images**');
	await page.route('**/api/reader/images**', (route) =>
		route.fulfill({ status: 400, json: { error: 'No selector configured' } }),
	);
	await page.goto(READER_URL);
	await expect(page.locator('.reader-state.error')).toBeVisible();
	await expect(page.locator('.reader-state.error')).toContainText('No selector configured');
});

// ── Chapter navigation controls ───────────────────────────────────────────────

test('displays the current chapter number in the input', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await expect(page.locator('.chapter-input')).toHaveValue('10');
});

test('prev button is disabled at chapter 1', async ({ page }) => {
	await setupMocks(page);
	await page.goto(CH1_URL);
	await expect(page.locator('.nav-btn').first()).toBeDisabled();
});

test('prev button is enabled when chapter > 1', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await expect(page.locator('.nav-btn').first()).toBeEnabled();
});

test('next button navigates to the next chapter', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await page.locator('.nav-btn').last().click();
	await expect(page.locator('.chapter-input')).toHaveValue('11');
	await expect(page).toHaveURL(/[?&]chapter=11/);
});

test('prev button navigates to the previous chapter', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await page.locator('.nav-btn').first().click();
	await expect(page.locator('.chapter-input')).toHaveValue('9');
	await expect(page).toHaveURL(/[?&]chapter=9/);
});

test('Go button navigates to the entered chapter number', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await page.locator('.chapter-input').fill('25');
	await page.locator('.go-btn').click();
	await expect(page.locator('.chapter-input')).toHaveValue('25');
	await expect(page).toHaveURL(/[?&]chapter=25/);
});

test('pressing Enter in the chapter input navigates', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await page.locator('.chapter-input').fill('30');
	await page.locator('.chapter-input').press('Enter');
	await expect(page.locator('.chapter-input')).toHaveValue('30');
	await expect(page).toHaveURL(/[?&]chapter=30/);
});

test('navigation fetches fresh images for the new chapter', async ({ page }) => {
	await setupMocks(page);
	let imageRequestCount = 0;
	page.on('request', (req) => {
		if (req.url().includes('/api/reader/images')) imageRequestCount++;
	});
	await page.goto(READER_URL);
	await page.locator('.nav-btn').last().click();
	await expect(page.locator('.chapter-input')).toHaveValue('11');
	expect(imageRequestCount).toBe(2); // initial load + navigation
});

// ── Scroll-to-top button ──────────────────────────────────────────────────────

test('scroll-to-top button is hidden on initial load', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await expect(page.locator('.reader-images')).toBeVisible();
	await expect(page.locator('.scroll-top-btn')).not.toBeVisible();
});

test('scroll-to-top button appears after scrolling more than 400px', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	// Wait for images to render, then make page tall enough to scroll
	await expect(page.locator('.reader-images')).toBeVisible();
	await page.evaluate(() => {
		(document.querySelector('.reader-images') as HTMLElement).style.minHeight = '2000px';
	});
	await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'instant' }));
	await expect(page.locator('.scroll-top-btn')).toBeVisible({ timeout: 2000 });
});

test('scroll-to-top button scrolls the page back to the top', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await expect(page.locator('.reader-images')).toBeVisible();
	await page.evaluate(() => {
		(document.querySelector('.reader-images') as HTMLElement).style.minHeight = '2000px';
	});
	await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'instant' }));
	await expect(page.locator('.scroll-top-btn')).toBeVisible({ timeout: 2000 });
	await page.locator('.scroll-top-btn').click();
	await page.waitForFunction(() => window.scrollY < 50);
	const scrollY = await page.evaluate(() => window.scrollY);
	expect(scrollY).toBeLessThan(50);
});

test('scroll-to-top button is hidden again after scrolling back to top', async ({ page }) => {
	await setupMocks(page);
	await page.goto(READER_URL);
	await expect(page.locator('.reader-images')).toBeVisible();
	await page.evaluate(() => {
		(document.querySelector('.reader-images') as HTMLElement).style.minHeight = '2000px';
	});
	await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'instant' }));
	await expect(page.locator('.scroll-top-btn')).toBeVisible({ timeout: 2000 });
	await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
	await expect(page.locator('.scroll-top-btn')).not.toBeVisible({ timeout: 2000 });
});

// ── Back button ───────────────────────────────────────────────────────────────

test('back button leaves the reader view', async ({ page }) => {
	await setupMocks(page);
	// Navigate to home first so browser history has a prior entry
	await page.goto('/');
	await page.goto(READER_URL);
	await page.locator('.back-btn').click();
	await expect(page).not.toHaveURL(/\/reader/);
});
