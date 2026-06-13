<template>
	<article class="manga-card" :class="{ 'has-update': entry.hasUpdate }">
		<div class="cover-wrap">
			<img v-if="entry.coverUrl" :src="proxiedCoverUrl(entry.coverUrl)" :alt="entry.title" class="cover" loading="lazy" />
			<div v-else class="cover-placeholder">
				<span>巻</span>
			</div>
			<div v-if="entry.hasUpdate" class="update-badge">NEW</div>
		</div>

		<div class="card-body">
			<h3 class="manga-title" :title="entry.title">{{ entry.title }}</h3>

			<div class="chapter-row">
				<div class="chapter-info">
					<span class="chapter-label">Reading</span>
					<span class="chapter-val">
						<a
							v-if="entry.currentChapterUrl"
							:href="entry.currentChapterUrl"
							target="_blank"
							rel="noopener"
							class="chapter-link"
							@click="onChapterClick(entry.currentChapter, entry.currentChapterUrl)"
						>Ch. {{ entry.currentChapter }}</a>
						<span v-else>Ch. {{ entry.currentChapter }}</span>
					</span>
				</div>

				<!-- Multiple sources: one row per source -->
				<template v-if="entry.sources && entry.sources.length">
					<div v-for="src in entry.sources" :key="src.siteId" class="chapter-info source-row">
						<span class="chapter-label source-label">{{ src.siteName }}</span>
						<span class="chapter-val" :class="{ accent: src.latestChapter > entry.currentChapter }">
							<a
								v-if="src.latestChapterUrl"
								href="#"
								class="chapter-link"
								:class="{ accent: src.latestChapter > entry.currentChapter }"
								@click.prevent="openReader(src)"
							>Ch. {{ nextChapterNum(src) }}</a>
							<span v-else>Ch. {{ nextChapterNum(src) }}</span>
						</span>
						<button
							class="source-remove-btn"
							title="Remove this source"
							@click.stop="handleRemoveSource(src.siteId)"
						>×</button>
					</div>
				</template>
				<!-- Fallback if no sources yet -->
				<div v-else class="chapter-info">
					<span class="chapter-label">Latest</span>
					<span class="chapter-val" :class="{ accent: entry.hasUpdate }">Ch. {{ entry.latestChapter }}</span>
				</div>
			</div>

			<div class="card-actions">
				<button class="action-btn refresh-btn" @click="handleCheck" title="Check for updates">
					<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5">
						<polyline points="23 4 23 10 17 10" />
						<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
					</svg>
				</button>
				<button class="action-btn remove-btn" @click="handleRemove" title="Remove from list">
					<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5">
						<polyline points="3 6 5 6 21 6" />
						<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
						<path d="M10 11v6M14 11v6" />
					</svg>
				</button>
			</div>
		</div>
	</article>
</template>

<script setup lang="ts">
import type { MangaEntry, MangaSource } from '@/types';
import { useMangaStore } from '@/stores/manga';
import { useRouter } from 'vue-router';
import api from '@/composables/useApi';
import { buildChapterUrl } from '@/utils/reader';

const props = defineProps<{ entry: MangaEntry }>();
const manga = useMangaStore();
const router = useRouter();

function proxiedCoverUrl(url: string): string {
	return `${import.meta.env.VITE_API_URL ?? ''}/api/manga/cover?url=${encodeURIComponent(url)}`;
}

function onChapterClick(chapter: number, url: string) {
	manga.updateProgress(props.entry.id, chapter, url);
}

function nextChapterNum(src: MangaSource): number {
	const current = props.entry.currentChapter;
	if (current === 0) return 1;
	return Math.min(current + 1, src.latestChapter);
}

async function openReader(src: MangaSource) {
	const next = nextChapterNum(src);
	let url: string;
	if (next === src.latestChapter) {
		url = src.latestChapterUrl!;
	} else if (src.latestChapterUrl?.includes('mangadex.org/chapter/')) {
		try {
			const { data } = await api.get<{ chapter_url: string }>('/reader/mangadex-chapter', {
				params: { manga_id: props.entry.id, chapter: next },
			});
			url = data.chapter_url;
		} catch {
			url = src.latestChapterUrl!;
		}
	} else if (src.latestChapterUrl?.includes('fanfox.net')) {
		try {
			const { data } = await api.get<{ chapter_url: string }>('/reader/fanfox-chapter', {
				params: { latest_chapter_url: src.latestChapterUrl, chapter: next },
			});
			url = data.chapter_url;
		} catch (err) {
			const fallback = buildChapterUrl(src.latestChapterUrl!, next);
			if (fallback === null) {
				console.error('Cannot navigate to Fanfox chapter: volume-prefixed URL cannot be resolved client-side.', err);
				return;
			}
			url = fallback;
		}
	} else {
		url = buildChapterUrl(src.latestChapterUrl!, next) ?? src.latestChapterUrl!;
	}
	manga.updateProgress(props.entry.id, next, url);
	router.push({ name: 'reader', query: { url, siteId: src.siteId, mangaId: props.entry.id, chapter: next } });
}

async function handleCheck() {
	await manga.checkUpdates(props.entry.id);
}

async function handleRemove() {
	await manga.removeManga(props.entry.id);
}

async function handleRemoveSource(siteId: number) {
	await manga.removeSource(props.entry.id, siteId);
}
</script>

<style scoped>
.manga-card {
	background: var(--surface);
	border: 1px solid var(--border);
	border-radius: 6px;
	overflow: hidden;
	display: flex;
	flex-direction: column;
	transition: border-color 0.2s, transform 0.2s;
}

.manga-card:hover {
	transform: translateY(-2px);
	border-color: rgba(255,255,255,0.14);
}

.manga-card.has-update {
	border-color: var(--accent-glow);
}

.cover-wrap {
	position: relative;
	aspect-ratio: 2 / 3;
	background: var(--surface-2);
	overflow: hidden;
}

.cover {
	width: 100%;
	height: 100%;
	object-fit: cover;
	display: block;
}

.cover-placeholder {
	width: 100%;
	height: 100%;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 3rem;
	color: var(--border);
}

.update-badge {
	position: absolute;
	top: 8px;
	right: 8px;
	background: var(--accent);
	color: #fff;
	font-size: 0.6rem;
	font-weight: 500;
	letter-spacing: 0.12em;
	padding: 2px 6px;
	border-radius: 2px;
}

.card-body {
	padding: 0.85rem;
	display: flex;
	flex-direction: column;
	gap: 0.6rem;
	flex: 1;
}

.manga-title {
	font-family: 'Cinzel', serif;
	font-size: 0.8rem;
	font-weight: 400;
	line-height: 1.4;
	color: var(--text);
	overflow: hidden;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
}

.chapter-row {
	display: flex;
	flex-direction: column;
	gap: 0.3rem;
}

.chapter-info {
	display: flex;
	justify-content: space-between;
	align-items: center;
	font-size: 0.75rem;
}

.chapter-label {
	color: var(--muted);
}

.source-label {
	font-style: italic;
}

.chapter-val {
	color: var(--text);
}

.chapter-link {
	transition: color 0.2s;
}

.chapter-link:hover,
.chapter-link.accent {
	color: var(--accent);
}

.accent {
	color: var(--accent);
}

.card-actions {
	display: flex;
	gap: 0.4rem;
	margin-top: auto;
}

.action-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	border-radius: 3px;
	border: 1px solid var(--border);
	background: transparent;
	color: var(--muted);
	transition: color 0.2s, border-color 0.2s;
}

.refresh-btn:hover {
	color: var(--text);
	border-color: rgba(255,255,255,0.15);
}

.remove-btn:hover {
	color: var(--accent);
	border-color: var(--accent-glow);
}

.source-row {
	position: relative;
}

.source-remove-btn {
	opacity: 0.4;
	border: none;
	background: transparent;
	color: var(--muted);
	font-size: 0.8rem;
	line-height: 1;
	padding: 0 2px;
	cursor: pointer;
	transition: color 0.15s, opacity 0.15s;
}

.source-remove-btn:hover {
	color: var(--accent);
	opacity: 1;
}
</style>
