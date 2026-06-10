/**
 * Unit tests for the manga Pinia store.
 *
 * The mocha setup file (test/setup.cjs) pre-stubs `@/composables/useApi` and
 * exposes the stub as `global.__apiStub`.  Each test replaces the stub's
 * methods to control what the API returns, then restores them in afterEach.
 */

import { strict as assert } from 'assert';
import { createPinia, setActivePinia } from 'pinia';
// Path alias @/ is resolved to src/ by the mocha setup file.
// We use the resolved relative path here so tsx/cjs can find the file.
import { useMangaStore } from '../src/stores/manga';
import type { MangaEntry } from '../src/types';

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeManga(overrides: Partial<MangaEntry> = {}): MangaEntry {
	return {
		id: 1,
		title: 'Test Manga',
		coverUrl: null,
		latestChapter: 10,
		sources: [],
		currentChapter: 5,
		currentChapterUrl: 'https://site.com/series/test/chapter/5',
		hasUpdate: false,
		updatedAt: null,
		...overrides,
	};
}

// The api stub is pre-registered by test/setup.cjs and exposed as a global.
// Cast to any to avoid TypeScript complaints about the global augmentation.
const apiStub: {
	get: (...args: any[]) => any;
	post: (...args: any[]) => any;
	patch: (...args: any[]) => any;
	delete: (...args: any[]) => any;
} = (globalThis as any).__apiStub;

// ── Test suite ────────────────────────────────────────────────────────────────

describe('manga store', () => {
	let savedGet: typeof apiStub.get;
	let savedPost: typeof apiStub.post;
	let savedPatch: typeof apiStub.patch;

	beforeEach(() => {
		setActivePinia(createPinia());
		savedGet = apiStub.get;
		savedPost = apiStub.post;
		savedPatch = apiStub.patch;
	});

	afterEach(() => {
		apiStub.get = savedGet;
		apiStub.post = savedPost;
		apiStub.patch = savedPatch;
	});

	// ── fetchList ──────────────────────────────────────────────────────────────

	describe('fetchList', () => {
		it('populates list on success', async () => {
			const entries = [makeManga({ id: 1 }), makeManga({ id: 2, title: 'Another Manga' })];
			apiStub.get = async () => ({ data: entries });

			const store = useMangaStore();
			await store.fetchList();

			assert.equal(store.list.length, 2);
			assert.equal(store.list[0].id, 1);
			assert.equal(store.list[1].title, 'Another Manga');
			assert.equal(store.error, null);
			assert.equal(store.loading, false);
		});

		it('sets error on failure', async () => {
			apiStub.get = async () => {
				throw { response: { data: { error: 'Network error' } } };
			};

			const store = useMangaStore();
			await store.fetchList();

			assert.equal(store.list.length, 0);
			assert.equal(store.error, 'Network error');
			assert.equal(store.loading, false);
		});

		it('sets generic error message when response has no error field', async () => {
			apiStub.get = async () => {
				throw new Error('Something went wrong');
			};

			const store = useMangaStore();
			await store.fetchList();

			assert.equal(store.error, 'Failed to load manga list');
		});

		it('sets loading to false regardless of success or failure', async () => {
			apiStub.get = async () => {
				throw new Error('fail');
			};

			const store = useMangaStore();
			assert.equal(store.loading, false);
			await store.fetchList();
			assert.equal(store.loading, false);
		});
	});

	// ── updateProgress ─────────────────────────────────────────────────────────

	describe('updateProgress', () => {
		it('calls PATCH with correct endpoint and body', async () => {
			let capturedUrl = '';
			let capturedBody: unknown = null;

			apiStub.patch = async (url: string, body: unknown) => {
				capturedUrl = url;
				capturedBody = body;
				return { data: {} };
			};

			const store = useMangaStore();
			store.list.push(makeManga({ id: 42 }));
			await store.updateProgress(42, 7, 'https://site.com/series/test/chapter/7');

			assert.equal(capturedUrl, '/manga/42/progress');
			assert.deepEqual(capturedBody, {
				chapter: 7,
				url: 'https://site.com/series/test/chapter/7',
			});
		});

		it('updates the local list item on success', async () => {
			apiStub.patch = async () => ({ data: {} });

			const store = useMangaStore();
			store.list.push(makeManga({ id: 1, currentChapter: 5, currentChapterUrl: 'https://site.com/chapter/5' }));

			await store.updateProgress(1, 9, 'https://site.com/chapter/9');

			const item = store.list.find((m) => m.id === 1);
			assert.equal(item?.currentChapter, 9);
			assert.equal(item?.currentChapterUrl, 'https://site.com/chapter/9');
		});

		it('does not throw on network error (silent fail)', async () => {
			apiStub.patch = async () => {
				throw new Error('Network error');
			};

			const store = useMangaStore();
			await assert.doesNotReject(() => store.updateProgress(1, 1, 'https://site.com/chapter/1'));
		});

		it('does not update local item when the id is not in the list', async () => {
			apiStub.patch = async () => ({ data: {} });

			const store = useMangaStore();
			store.list.push(makeManga({ id: 1, currentChapter: 5 }));

			// id 99 does not exist — should not throw and should leave id 1 untouched
			await store.updateProgress(99, 10, 'https://site.com/chapter/10');

			assert.equal(store.list[0].currentChapter, 5);
		});
	});

	// ── addManga ───────────────────────────────────────────────────────────────

	describe('addManga', () => {
		it('calls POST /manga/ with the title', async () => {
			let capturedUrl = '';
			let capturedBody: unknown = null;
			const newEntry = makeManga({ id: 99, title: 'New Manga' });

			apiStub.post = async (url: string, body: unknown) => {
				capturedUrl = url;
				capturedBody = body;
				return { data: newEntry };
			};

			const store = useMangaStore();
			await store.addManga('New Manga');

			assert.equal(capturedUrl, '/manga/');
			assert.deepEqual(capturedBody, { title: 'New Manga' });
		});

		it('adds the returned manga to list', async () => {
			const newEntry = makeManga({ id: 99, title: 'New Manga' });
			apiStub.post = async () => ({ data: newEntry });

			const store = useMangaStore();
			const result = await store.addManga('New Manga');

			assert.equal(store.list.length, 1);
			assert.equal(store.list[0].id, 99);
			assert.equal(store.list[0].title, 'New Manga');
			assert.deepEqual(result, newEntry);
		});

		it('returns null and sets error on failure', async () => {
			apiStub.post = async () => {
				throw { response: { data: { error: 'Duplicate title' } } };
			};

			const store = useMangaStore();
			const result = await store.addManga('Existing Manga');

			assert.equal(result, null);
			assert.equal(store.error, 'Duplicate title');
			assert.equal(store.list.length, 0);
		});

		it('appends to an existing list without replacing it', async () => {
			const existingEntry = makeManga({ id: 1, title: 'Existing' });
			const newEntry = makeManga({ id: 2, title: 'Newly Added' });

			apiStub.post = async () => ({ data: newEntry });

			const store = useMangaStore();
			store.list.push(existingEntry);
			await store.addManga('Newly Added');

			assert.equal(store.list.length, 2);
			assert.equal(store.list[0].title, 'Existing');
			assert.equal(store.list[1].title, 'Newly Added');
		});
	});
});
