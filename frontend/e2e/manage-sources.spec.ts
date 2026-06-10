import { test, expect, type Page } from '@playwright/test';

const MOCK_SITES = [
  {
    id: 1,
    name: 'AsuraScans',
    latestReleasesUrl: 'https://asuracomic.net/series',
    containerSelector: '.series-card',
    titleSelector: 'span.title',
    coverSelector: 'img.cover',
    chapterLinkSelector: 'a.chapter',
    chapterImageSelector: null,
    isActive: true,
  },
];

const TEST_RESULT_PASS = {
  ok: true,
  counts: { titles: 10, chapterLinks: 10, covers: 8 },
  results: [
    { title: 'Solo Leveling', cover_url: null, chapter: 200, chapter_url: 'https://asuracomic.net/series/solo/chapter/200' },
    { title: 'Nano Machine', cover_url: null, chapter: 180, chapter_url: 'https://asuracomic.net/series/nano/chapter/180' },
  ],
};

const TEST_RESULT_FAIL = {
  ok: false,
  counts: { titles: 0, chapterLinks: 0, covers: 0 },
  results: [],
};

async function setupMocks(page: Page, testResult = TEST_RESULT_PASS) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
  });
  await page.route('**/api/user/me', (route) =>
    route.fulfill({ json: { id: 1, displayName: 'Test', email: 'test@test.com', isAdmin: true, avatarUrl: null } }),
  );
  await page.route('**/api/manga/', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/scraper/sites', (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ json: MOCK_SITES });
    } else if (route.request().method() === 'DELETE') {
      route.fulfill({ status: 204, body: '' });
    }
  });
  await page.route('**/api/scraper/test', (route) =>
    route.fulfill({ json: testResult }),
  );
}

async function openManageModal(page: Page) {
  await page.goto('/');
  await page.locator('button:has-text("Sources")').click();
  await expect(page.locator('.manage-modal')).toBeVisible();
}

test('Manage Sources button opens modal with source list', async ({ page }) => {
  await setupMocks(page);
  await openManageModal(page);
  await expect(page.locator('.site-name')).toHaveText('AsuraScans');
  await expect(page.locator('.site-url')).toContainText('asuracomic.net');
});

test('Test button shows pass badge when selectors work', async ({ page }) => {
  await setupMocks(page, TEST_RESULT_PASS);
  await openManageModal(page);
  await page.locator('button:has-text("Test")').click();
  await expect(page.locator('.badge.pass')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('.badge.pass')).toContainText('✓ Pass');
});

test('Test button shows fail badge when selectors return no results', async ({ page }) => {
  await setupMocks(page, TEST_RESULT_FAIL);
  await openManageModal(page);
  await page.locator('button:has-text("Test")').click();
  await expect(page.locator('.badge.fail')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('.badge.fail')).toContainText('✗ Fail');
});

test('Clicking pass badge shows popup with match counts', async ({ page }) => {
  await setupMocks(page, TEST_RESULT_PASS);
  await openManageModal(page);
  await page.locator('button:has-text("Test")').click();
  await expect(page.locator('.badge.pass')).toBeVisible({ timeout: 5000 });
  await page.locator('.badge.pass').click();
  await expect(page.locator('.test-popup')).toBeVisible();
  await expect(page.locator('.popup-counts')).toContainText('10 titles');
  await expect(page.locator('.popup-counts')).toContainText('10 chapter links');
});

test('Popup shows preview cards', async ({ page }) => {
  await setupMocks(page, TEST_RESULT_PASS);
  await openManageModal(page);
  await page.locator('button:has-text("Test")').click();
  await expect(page.locator('.badge.pass')).toBeVisible({ timeout: 5000 });
  await page.locator('.badge.pass').click();
  await expect(page.locator('.popup-card')).toHaveCount(2);
  await expect(page.locator('.popup-title').first()).toContainText('Solo Leveling');
});

test('Delete button shows inline confirm prompt', async ({ page }) => {
  await setupMocks(page);
  await openManageModal(page);
  await page.locator('button:has-text("Delete")').click();
  await expect(page.locator('.confirm-text')).toContainText('Sure?');
  await expect(page.locator('button:has-text("Yes")')).toBeVisible();
  await expect(page.locator('button:has-text("No")')).toBeVisible();
});

test('Cancelling delete restores the delete button', async ({ page }) => {
  await setupMocks(page);
  await openManageModal(page);
  await page.locator('button:has-text("Delete")').click();
  await page.locator('button:has-text("No")').click();
  await expect(page.locator('button:has-text("Delete")')).toBeVisible();
  await expect(page.locator('.confirm-text')).not.toBeVisible();
});

test('Confirming delete removes the source row', async ({ page }) => {
  // Track whether a DELETE has been performed so the subsequent GET returns empty
  let deleted = false;
  await page.addInitScript(() => {
    localStorage.setItem('token', 'test-token');
  });
  await page.route('**/api/user/me', (route) =>
    route.fulfill({ json: { id: 1, displayName: 'Test', email: 'test@test.com', isAdmin: true, avatarUrl: null } }),
  );
  await page.route('**/api/manga/', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/scraper/sites', (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ json: deleted ? [] : MOCK_SITES });
    } else if (route.request().method() === 'DELETE') {
      deleted = true;
      route.fulfill({ status: 204, body: '' });
    }
  });
  await page.route('**/api/scraper/test', (route) =>
    route.fulfill({ json: TEST_RESULT_PASS }),
  );
  await openManageModal(page);
  await page.locator('button:has-text("Delete")').click();
  await page.locator('button:has-text("Yes")').click();
  await expect(page.locator('.site-name')).not.toBeVisible({ timeout: 3000 });
});

test('Edit button closes manage modal and opens ScraperTool pre-filled', async ({ page }) => {
  await setupMocks(page);
  await openManageModal(page);
  await page.locator('button:has-text("Edit")').click();
  await expect(page.locator('.manage-modal')).not.toBeVisible();
  await expect(page.locator('.scraper-modal')).toBeVisible();
  // URL field should be read-only and pre-filled
  await expect(page.locator('.scraper-modal input[type="text"][disabled]')).toHaveValue(
    'https://asuracomic.net/series',
  );
});
