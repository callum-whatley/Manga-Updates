<template>
	<div class="reader-page" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
		<header class="reader-header">
			<button class="back-btn" @click="router.back()">
				<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
					<polyline points="15 18 9 12 15 6" />
				</svg>
				Back
			</button>

			<div v-if="chapterNumFromUrl !== null" class="chapter-nav">
				<button class="nav-btn" :disabled="navigating || chapterNumFromUrl <= 1" title="Previous chapter" @click="navigateTo(chapterNumFromUrl - 1)">
					<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
						<polyline points="15 18 9 12 15 6" />
					</svg>
				</button>

				<div class="chapter-input-wrap">
					<span class="chapter-label">Ch.</span>
					<input
						v-model="chapterInput"
						class="chapter-input"
						type="number"
						min="1"
						step="1"
						@keydown.enter="goToInput"
					/>
					<button class="go-btn" :disabled="navigating" @click="goToInput">Go</button>
				</div>

				<button class="nav-btn" :disabled="isAtLastChapter || navigating" title="Next chapter" @click="navigateTo(chapterNumFromUrl + 1)">
					<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5">
						<polyline points="9 18 15 12 9 6" />
					</svg>
				</button>
			</div>

			<button class="mode-btn" :title="displayMode === 'strip' ? 'Switch to paged mode' : 'Switch to strip mode'" @click="toggleDisplayMode">
				<svg v-if="displayMode === 'strip'" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
					<rect x="3" y="3" width="18" height="5" rx="1" />
					<rect x="3" y="10" width="18" height="5" rx="1" />
					<rect x="3" y="17" width="18" height="5" rx="1" />
				</svg>
				<svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
					<rect x="3" y="3" width="18" height="18" rx="1" />
					<line x1="12" y1="3" x2="12" y2="21" />
				</svg>
			</button>
		</header>

		<div v-if="loading" class="reader-state">
			<div class="spinner" />
		</div>
		<div v-else-if="error" class="reader-state error">
			<p>{{ error }}</p>
			<button class="retry-btn" @click="fetchImages">
				<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2">
					<polyline points="23 4 23 10 17 10" />
					<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
				</svg>
				Retry
			</button>
		</div>

		<!-- Strip mode -->
		<div v-else-if="displayMode === 'strip'" class="reader-images reader-images--strip">
			<div
				v-for="(src, i) in images"
				:key="i"
				class="image-wrap"
				:ref="(el) => { if (i === images.length - 1) lastImageEl = el as HTMLElement | null }"
			>
				<div v-if="imageStates[i] !== 'loaded'" class="image-overlay">
					<div v-if="imageStates[i] === 'loading'" class="spinner" />
					<button v-else class="retry-btn" title="Retry" @click="retryImage(i)">
						<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2">
							<polyline points="23 4 23 10 17 10" />
							<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
						</svg>
					</button>
				</div>
				<img
					:src="imageSrc(i)"
					loading="lazy"
					class="reader-image"
					:class="{ invisible: imageStates[i] !== 'loaded' }"
					@load="onImageLoad(i)"
					@error="imageStates[i] = 'error'"
				/>
			</div>
		</div>

		<!-- Paged mode -->
		<div v-else class="reader-images reader-images--paged">
			<div v-for="(src, i) in images" :key="i" class="image-wrap">
				<div v-if="imageStates[i] !== 'loaded'" class="image-overlay">
					<div v-if="imageStates[i] === 'loading'" class="spinner" />
					<button v-else class="retry-btn" title="Retry" @click="retryImage(i)">
						<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2">
							<polyline points="23 4 23 10 17 10" />
							<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
						</svg>
					</button>
				</div>
				<img
					:src="imageSrc(i)"
					class="reader-image"
					:class="{ invisible: imageStates[i] !== 'loaded' }"
					@load="onImageLoad(i)"
					@error="imageStates[i] = 'error'"
				/>
			</div>
		</div>

		<Transition name="fade">
			<button v-if="showScrollTop" class="scroll-top-btn" title="Back to top" @click="scrollToTop">
				<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5">
					<polyline points="18 15 12 9 6 15" />
				</svg>
			</button>
		</Transition>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, type Ref, type ComputedRef } from 'vue';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import axios from 'axios';
import api from '@/composables/useApi';
import { useMangaStore } from '@/stores/manga';
import { useAuthStore } from '@/stores/auth';
import { chapterNumFromUrl as parseChapterNum, buildChapterUrl } from '@/utils/reader';

// ── Module-level state ─────────────────────────────────────────────────────────

const prefetchCache = new Map<number, string[]>();
let intersectionObserver: IntersectionObserver | null = null;
let prefetchAbortController: AbortController | null = null;

// ── Setup ──────────────────────────────────────────────────────────────────────

const route = useRoute();
const router = useRouter();
const manga = useMangaStore();
const auth = useAuthStore();

const imageToken = ref<string>('');
let imageTokenTimer: ReturnType<typeof setInterval> | null = null;

async function fetchImageToken() {
	try {
		const { data } = await api.get<{ token: string }>('/reader/image-token');
		imageToken.value = data.token;
	} catch {
		// Fall back to session token — proxy accepts it via Authorization header path,
		// but that path won't work for <img> tags. Best-effort; images will 401 if this fails.
		imageToken.value = auth.token ?? '';
	}
}

const siteId = route.query.siteId as string;
const mangaId = Number(route.query.mangaId);

// Mutable — updated when navigating between chapters
const currentUrl = ref(route.query.url as string);
const currentChapter = ref(Number(route.query.chapter));

const images = ref<string[]>([]);
const loading = ref(true);
const error = ref('');
const navigating = ref(false);
const imageStates = ref<('loading' | 'loaded' | 'error')[]>([]);
const imageRetries = ref<number[]>([]);
const showScrollTop = ref(false);

// New refs
const displayMode: Ref<'strip' | 'paged'> = ref(
	(localStorage.getItem('readerDisplayMode') as 'strip' | 'paged') ?? 'strip',
);
const progressSaved: Ref<boolean> = ref(false);
const lastImageEl: Ref<HTMLElement | null> = ref(null);
const loadedImageCount: Ref<number> = ref(0);

// ── Computeds ──────────────────────────────────────────────────────────────────

const isMangaDex = computed(() => currentUrl.value.includes('mangadex.org/chapter/'));

// Chapter number extracted from the URL path (e.g. /chapter/166 → 166).
// For MangaDex UUID URLs, falls back to the route query chapter number.
const chapterNumFromUrl = computed<number | null>(() => {
	const fromUrl = parseChapterNum(currentUrl.value);
	if (fromUrl !== null) return fromUrl;
	if (isMangaDex.value && currentChapter.value > 0) return currentChapter.value;
	return null;
});

const chapterInput = ref(chapterNumFromUrl.value?.toString() ?? '');

const mangaEntry = computed(() => manga.list.find((m) => m.id === mangaId));

const maxChapter: ComputedRef<number> = computed(() => mangaEntry.value?.latestChapter ?? Infinity);

const isAtLastChapter: ComputedRef<boolean> = computed(
	() => chapterNumFromUrl.value !== null && chapterNumFromUrl.value >= maxChapter.value,
);

// ── Chapter URL resolution ─────────────────────────────────────────────────────

async function resolveChapterUrl(baseUrl: string, chapterNum: number, mangaIdParam?: number | string, signal?: AbortSignal): Promise<string> {
	if (baseUrl.includes('mangadex.org/chapter/') && mangaIdParam) {
		try {
			const { data } = await api.get<{ chapter_url: string }>('/reader/mangadex-chapter', {
				params: { manga_id: mangaIdParam, chapter: chapterNum },
				...(signal ? { signal } : {}),
			});
			return data.chapter_url;
		} catch {
			return buildChapterUrl(baseUrl, chapterNum) ?? baseUrl;
		}
	}
	if (baseUrl.includes('fanfox.net')) {
		try {
			const { data } = await api.get<{ chapter_url: string }>('/reader/fanfox-chapter', {
				params: { latest_chapter_url: baseUrl, chapter: chapterNum },
				...(signal ? { signal } : {}),
			});
			return data.chapter_url;
		} catch (err) {
			const fallback = buildChapterUrl(baseUrl, chapterNum);
			if (fallback === null) {
				throw new Error(`Cannot navigate to Fanfox chapter ${chapterNum}: volume-prefixed URL cannot be resolved client-side.`);
			}
			return fallback;
		}
	}
	return buildChapterUrl(baseUrl, chapterNum) ?? baseUrl;
}

// ── Image helpers ──────────────────────────────────────────────────────────────

function proxied(imgUrl: string): string {
	return `${import.meta.env.VITE_API_URL ?? ''}/api/reader/proxy-image?url=${encodeURIComponent(imgUrl)}&token=${encodeURIComponent(imageToken.value)}`;
}

function imageSrc(i: number): string {
	const base = proxied(images.value[i]);
	const retry = imageRetries.value[i];
	return retry > 0 ? `${base}&_r=${retry}` : base;
}

function retryImage(i: number) {
	imageStates.value[i] = 'loading';
	imageRetries.value[i]++;
}

// ── IntersectionObserver ───────────────────────────────────────────────────────

function disconnectObserver() {
	intersectionObserver?.disconnect();
	intersectionObserver = null;
}

function setupObserver() {
	if (!lastImageEl.value) return;
	intersectionObserver = new IntersectionObserver(
		(entries) => {
			for (const entry of entries) {
				if (entry.isIntersecting && !progressSaved.value) {
					progressSaved.value = true;
					manga.updateProgress(mangaId, currentChapter.value, currentUrl.value);
					disconnectObserver();
				}
			}
		},
		{ threshold: 0.5 },
	);
	intersectionObserver.observe(lastImageEl.value);
}

// ── Image load / prefetch ──────────────────────────────────────────────────────

function onImageLoad(i: number) {
	imageStates.value[i] = 'loaded';
	loadedImageCount.value++;
	if (loadedImageCount.value === images.value.length && images.value.length > 0) {
		prefetchNextChapter();
	}
}

async function prefetchNextChapter() {
	const nextNum = (chapterNumFromUrl.value ?? 0) + 1;
	if (nextNum > maxChapter.value) return;
	if (prefetchCache.has(nextNum)) return;
	prefetchAbortController?.abort();
	prefetchAbortController = new AbortController();

	let nextUrl: string;
	try {
		nextUrl = await resolveChapterUrl(currentUrl.value, nextNum, mangaId, prefetchAbortController.signal);
	} catch {
		return;
	}

	try {
		const { data } = await api.get<{ images: string[] }>('/reader/images', {
			params: { url: nextUrl, site_id: siteId },
			signal: prefetchAbortController.signal,
		});
		prefetchCache.set(nextNum, data.images);
	} catch (e: any) {
		if (!axios.isCancel(e)) {
			// Silent fail — prefetch is best-effort
		}
	}
}

// ── Display mode toggle ────────────────────────────────────────────────────────

function toggleDisplayMode() {
	disconnectObserver();
	displayMode.value = displayMode.value === 'strip' ? 'paged' : 'strip';
	localStorage.setItem('readerDisplayMode', displayMode.value);
	if (displayMode.value === 'strip') {
		nextTick(() => setupObserver());
	}
}

// ── Fetch ──────────────────────────────────────────────────────────────────────

async function fetchImages() {
	disconnectObserver();
	loading.value = true;
	error.value = '';
	images.value = [];
	imageStates.value = [];
	imageRetries.value = [];
	progressSaved.value = false;
	loadedImageCount.value = 0;

	// Check prefetch cache first
	const chNum = chapterNumFromUrl.value;
	if (chNum !== null && prefetchCache.has(chNum)) {
		const cached = prefetchCache.get(chNum)!;
		images.value = cached;
		imageStates.value = cached.map(() => 'loading' as const);
		imageRetries.value = cached.map(() => 0);
		loading.value = false;
		await nextTick();
		if (displayMode.value === 'strip') setupObserver();
		return;
	}

	try {
		const { data } = await api.get<{ images: string[] }>('/reader/images', {
			params: { url: currentUrl.value, site_id: siteId },
		});
		images.value = data.images;
		imageStates.value = data.images.map(() => 'loading' as const);
		imageRetries.value = data.images.map(() => 0);
	} catch (e: any) {
		error.value = e.response?.data?.error ?? 'Failed to load chapter images.';
	} finally {
		loading.value = false;
		if (!error.value && displayMode.value === 'strip') {
			nextTick(() => setupObserver());
		}
	}
}

// ── Chapter navigation ─────────────────────────────────────────────────────────

async function navigateTo(newNum: number) {
	if (newNum < 1 || navigating.value) return;
	navigating.value = true;

	// Record progress for the chapter we're leaving; gate the observer too
	progressSaved.value = true;
	manga.updateProgress(mangaId, currentChapter.value, currentUrl.value);

	try {
		currentUrl.value = await resolveChapterUrl(currentUrl.value, newNum, mangaId);
	} catch {
		error.value = `Chapter ${newNum} not found.`;
		navigating.value = false;
		return;
	}

	currentChapter.value = newNum;
	chapterInput.value = String(newNum);

	router.replace({
		name: 'reader',
		query: { url: currentUrl.value, siteId, mangaId, chapter: newNum },
	});

	scrollToTop();
	await fetchImages();
	navigating.value = false;
}

function goToInput() {
	const num = parseFloat(chapterInput.value);
	if (!isNaN(num) && num > 0 && num !== chapterNumFromUrl.value) {
		if (num > maxChapter.value) return;
		navigateTo(num);
	}
}

// ── Keyboard shortcuts ─────────────────────────────────────────────────────────

function handleKeydown(e: KeyboardEvent) {
	if ((e.target as HTMLElement).tagName === 'INPUT') return;
	if (e.key === 'ArrowLeft') navigateTo((chapterNumFromUrl.value ?? 1) - 1);
	else if (e.key === 'ArrowRight') navigateTo((chapterNumFromUrl.value ?? 0) + 1);
}

// ── Touch / swipe gestures ─────────────────────────────────────────────────────

let touchStartX = 0;
let touchStartY = 0;

function onTouchStart(e: TouchEvent) {
	touchStartX = e.touches[0].clientX;
	touchStartY = e.touches[0].clientY;
}

function onTouchEnd(e: TouchEvent) {
	const dx = e.changedTouches[0].clientX - touchStartX;
	const dy = e.changedTouches[0].clientY - touchStartY;
	if (Math.abs(dx) < 60 || Math.abs(dy) > Math.abs(dx)) return;
	if (chapterNumFromUrl.value === null) return;
	if (dx < 0) navigateTo(chapterNumFromUrl.value + 1); // swipe left → next
	else navigateTo(chapterNumFromUrl.value - 1);         // swipe right → prev
}

// ── Scroll to top ──────────────────────────────────────────────────────────────

function onScroll() {
	showScrollTop.value = window.scrollY > 400;
}

function scrollToTop() {
	window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(async () => {
	if (!currentUrl.value || !siteId) {
		error.value = 'Missing chapter URL or site ID.';
		loading.value = false;
		return;
	}
	window.addEventListener('scroll', onScroll, { passive: true });
	window.addEventListener('keydown', handleKeydown);
	await fetchImageToken();
	imageTokenTimer = setInterval(fetchImageToken, 4 * 60 * 1000);
	await fetchImages();
});

onUnmounted(() => {
	window.removeEventListener('scroll', onScroll);
	window.removeEventListener('keydown', handleKeydown);
	disconnectObserver();
	if (imageTokenTimer !== null) clearInterval(imageTokenTimer);
});

onBeforeRouteLeave(() => {
	prefetchCache.clear();
	prefetchAbortController?.abort();
	if (mangaId && currentChapter.value && currentUrl.value) {
		manga.updateProgress(mangaId, currentChapter.value, currentUrl.value);
	}
});
</script>

<style scoped>
.reader-page {
	min-height: 100vh;
	background: #0a0a0a;
	display: flex;
	flex-direction: column;
	align-items: center;
}

/* ── Header ── */
.reader-header {
	position: sticky;
	top: 0;
	z-index: 10;
	width: 100%;
	max-width: 800px;
	padding: 0.6rem 1rem;
	padding-top: max(0.6rem, env(safe-area-inset-top));
	display: flex;
	align-items: center;
	justify-content: space-between;
	background: rgba(10, 10, 10, 0.92);
	backdrop-filter: blur(8px);
	border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.back-btn {
	display: flex;
	align-items: center;
	gap: 0.4rem;
	background: transparent;
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 4px;
	color: rgba(255, 255, 255, 0.7);
	padding: 0.4rem 0.85rem;
	font-family: inherit;
	font-size: 0.85rem;
	cursor: pointer;
	transition: color 0.2s, border-color 0.2s;
	flex-shrink: 0;
}
.back-btn:hover { color: #fff; border-color: rgba(255, 255, 255, 0.3); }

/* ── Chapter nav ── */
.chapter-nav {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.nav-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 32px;
	height: 32px;
	background: transparent;
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 4px;
	color: rgba(255, 255, 255, 0.7);
	cursor: pointer;
	transition: color 0.2s, border-color 0.2s;
}
.nav-btn:hover:not(:disabled) { color: #fff; border-color: rgba(255, 255, 255, 0.3); }
.nav-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.chapter-input-wrap {
	display: flex;
	align-items: center;
	gap: 0.3rem;
	background: rgba(255, 255, 255, 0.05);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 4px;
	padding: 0 0.5rem;
	height: 32px;
}

.chapter-label {
	font-size: 0.75rem;
	color: rgba(255, 255, 255, 0.4);
}

.chapter-input {
	width: 52px;
	background: transparent;
	border: none;
	color: #fff;
	font-family: inherit;
	font-size: 0.85rem;
	text-align: center;
	outline: none;
	/* hide number spinners */
	-moz-appearance: textfield;
}
.chapter-input::-webkit-outer-spin-button,
.chapter-input::-webkit-inner-spin-button { -webkit-appearance: none; }

.go-btn {
	background: transparent;
	border: none;
	color: rgba(255, 255, 255, 0.5);
	font-family: inherit;
	font-size: 0.75rem;
	cursor: pointer;
	padding: 0;
	transition: color 0.2s;
}
.go-btn:hover:not(:disabled) { color: #fff; }
.go-btn:disabled { opacity: 0.3; cursor: not-allowed; }

/* ── Mode toggle button ── */
.mode-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 32px;
	height: 32px;
	background: transparent;
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 4px;
	color: rgba(255, 255, 255, 0.7);
	cursor: pointer;
	transition: color 0.2s, border-color 0.2s;
	flex-shrink: 0;
}
.mode-btn:hover { color: #fff; border-color: rgba(255, 255, 255, 0.3); }

/* ── Reader states ── */
.reader-state {
	padding: 4rem 1rem;
	color: rgba(255, 255, 255, 0.5);
	font-size: 0.9rem;
	text-align: center;
	display: flex;
	justify-content: center;
}
.reader-state.error { color: #e63946; }

/* ── Images ── */
.reader-images {
	width: 100%;
	max-width: 800px;
	display: flex;
	flex-direction: column;
}

.reader-images--paged {
	align-items: center;
}

.image-wrap {
	position: relative;
	width: 100%;
	min-height: 200px;
}

.image-overlay {
	position: absolute;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	background: #111;
}

.reader-image {
	width: 100%;
	height: auto;
	display: block;
}
.reader-image.invisible {
	opacity: 0;
	position: absolute;
	top: 0;
	left: 0;
}

.retry-btn {
	background: transparent;
	border: 1px solid rgba(255, 255, 255, 0.15);
	border-radius: 50%;
	width: 52px;
	height: 52px;
	display: flex;
	align-items: center;
	justify-content: center;
	color: rgba(255, 255, 255, 0.5);
	cursor: pointer;
	transition: color 0.2s, border-color 0.2s;
}
.retry-btn:hover { color: #fff; border-color: rgba(255, 255, 255, 0.4); }

/* ── Scroll to top ── */
.scroll-top-btn {
	position: fixed;
	bottom: 1.5rem;
	right: 1.5rem;
	width: 44px;
	height: 44px;
	border-radius: 50%;
	background: rgba(30, 30, 30, 0.9);
	border: 1px solid rgba(255, 255, 255, 0.15);
	color: rgba(255, 255, 255, 0.7);
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	backdrop-filter: blur(6px);
	transition: color 0.2s, border-color 0.2s;
}
.scroll-top-btn:hover { color: #fff; border-color: rgba(255, 255, 255, 0.35); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ── Spinner ── */
.spinner {
	width: 32px;
	height: 32px;
	border: 2px solid rgba(255, 255, 255, 0.1);
	border-top-color: rgba(255, 255, 255, 0.6);
	border-radius: 50%;
	animation: spin 0.75s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
