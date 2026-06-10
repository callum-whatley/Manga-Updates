<template>
	<Teleport to="body">
		<div v-if="open" class="scraper-overlay" @click.self="$emit('close')">
			<div class="scraper-modal">
				<!-- Header -->
				<div class="modal-header">
					<div class="modal-title">
						<span class="modal-step">{{ stepLabel }}</span>
						{{ isEditMode ? 'Edit Source' : 'Add Source' }}
					</div>
					<button class="close-btn" @click="$emit('close')">✕</button>
				</div>

				<!-- Step 1: Enter URL + site name -->
				<div v-if="step === 'url'" class="modal-body">
					<p class="step-desc">Paste the URL of a manga site's latest-releases page and give the site a name.</p>
					<div class="field-group">
						<label class="field-label">Latest releases URL <span class="required">*</span></label>
						<input
							v-model="siteUrl"
							class="text-input"
							type="url"
							placeholder="https://asuracomic.net/series"
							@keydown.enter="step = 'selectors'"
						/>
					</div>
					<div class="field-group">
						<label class="field-label">Site name</label>
						<input
							v-model="siteName"
							class="text-input"
							type="text"
							placeholder="AsuraScans"
						/>
					</div>
					<div class="btn-row">
						<button class="primary-btn" :disabled="!siteUrl.trim()" @click="step = 'selectors'">
							Next — enter selectors →
						</button>
					</div>
				</div>

				<!-- Step 2: Manual CSS selector input -->
				<div v-else-if="step === 'selectors'" class="modal-body">
					<!-- Edit mode: show read-only URL; Add mode: show instructions -->
					<div v-if="isEditMode" class="field-group">
						<label class="field-label">URL <span class="optional">(read-only)</span></label>
						<input :value="siteUrl" class="text-input" type="text" disabled />
					</div>
					<p v-else class="step-desc">
						Open <a :href="siteUrl" target="_blank" rel="noopener" class="site-link">{{ siteUrl }} ↗</a> in a new tab,
						right-click each element and choose <strong>Inspect</strong>, then copy its CSS selector from DevTools.
						Only title and chapter link are required.
					</p>

					<div class="field-group">
						<label class="field-label">
							Card container selector
							<span class="optional">(recommended — prevents chapter misalignment)</span>
						</label>
						<input v-model="containerSelector" class="text-input mono" type="text" placeholder="div.series-card" />
						<p class="field-hint">The element that wraps each series. Other selectors will be searched within it.</p>
					</div>
					<div class="field-group">
						<label class="field-label">Title selector <span class="required">*</span></label>
						<input v-model="titleSelector" class="text-input mono" type="text" placeholder="span.title > a" />
					</div>
					<div class="field-group">
						<label class="field-label">Chapter link selector <span class="required">*</span></label>
						<input v-model="chapterSelector" class="text-input mono" type="text" placeholder="a.chapter-link" />
					</div>
					<div class="field-group">
						<label class="field-label">Cover image selector <span class="optional">(optional)</span></label>
						<input v-model="coverSelector" class="text-input mono" type="text" placeholder="img.series-cover" />
					</div>

					<div class="reader-section">
						<div class="reader-section-label">In-App Reader <span class="optional">(optional)</span></div>
						<p class="field-hint" style="margin-bottom: 0.75rem;">
							Enable the in-app vertical reader by providing a sample chapter URL and the CSS selector that matches chapter page images.
						</p>
						<div class="field-group">
							<label class="field-label">Sample chapter URL</label>
							<input v-model="chapterUrl" class="text-input" type="url" placeholder="https://asuracomic.net/series/title/chapter/1" />
						</div>
						<div class="field-group browser-toggle">
							<label class="toggle-label">
								<input type="checkbox" v-model="useBrowser" class="toggle-checkbox" />
								<span>Use headless browser</span>
							</label>
							<p class="field-hint">
								For sites that load images with JavaScript (e.g. AsuraScans).
								Slower but works on CSR pages.
							</p>
						</div>
						<div class="field-group">
							<label class="field-label">Chapter image selector</label>
							<input v-model="rawImageSelector" class="text-input mono" type="text" placeholder="img[src*=&quot;/chapters/&quot;]" />
							<p class="field-hint">Matches the manga page images on a chapter page.</p>
							<p v-if="useBrowser && rawImageSelector" class="field-hint" style="color: var(--accent); opacity: 1;">
								Saved as: browser:{{ rawImageSelector }}
							</p>
						</div>
						<div v-if="chapterUrl.trim() && chapterImageSelector.trim()" class="btn-row" style="margin-top: 0.5rem;">
							<button class="secondary-btn" :disabled="testingChapter" @click="runChapterTest">
								{{ testingChapter ? 'Testing…' : 'Test reader' }}
							</button>
						</div>
						<div v-if="chapterImageError" class="state-msg error" style="padding: 0.75rem 0;">{{ chapterImageError }}</div>
						<div v-if="chapterImages.length" class="chapter-thumb-row">
							<img v-for="(img, i) in chapterImages.slice(0, 3)" :key="i" :src="img" class="chapter-thumb" />
							<span class="chapter-img-count">{{ chapterImages.length }} images found</span>
						</div>
					</div>

					<div class="btn-row">
						<button v-if="!isEditMode" class="secondary-btn" @click="step = 'url'">← Back</button>
						<button
							class="primary-btn"
							:disabled="!titleSelector.trim() || !chapterSelector.trim()"
							@click="runTest"
						>
							Test selectors →
						</button>
					</div>
				</div>

				<!-- Step 3: Test preview -->
				<div v-else-if="step === 'test'" class="modal-body">
					<div v-if="testing" class="state-msg">Running test scrape…</div>
					<div v-else-if="testError" class="state-msg error">
						{{ testError }}
						<div class="mt-sm"><button class="secondary-btn" @click="step = 'selectors'">← Fix selectors</button></div>
					</div>
					<div v-else-if="testResult">
						<div class="test-meta">
							<span class="meta-item" :class="{ ok: testResult.counts.titles > 0 }">
								{{ testResult.counts.titles }} titles matched
							</span>
							<span class="meta-item" :class="{ ok: testResult.counts.chapterLinks > 0 }">
								{{ testResult.counts.chapterLinks }} chapter links matched
							</span>
							<span class="meta-item" :class="{ ok: testResult.counts.covers > 0 }">
								{{ testResult.counts.covers }} covers matched
							</span>
						</div>

						<div v-if="!testResult.ok" class="state-msg error">
							No results extracted — check your selectors and try again.
						</div>
						<div v-else class="preview-grid">
							<div v-for="(item, i) in testResult.results" :key="i" class="preview-card">
								<div class="preview-cover">
									<img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" />
									<span v-else class="no-cover">巻</span>
								</div>
								<div class="preview-info">
									<p class="preview-title">{{ item.title }}</p>
									<p class="preview-chapter">Ch. {{ item.chapter }}</p>
									<a :href="item.chapter_url" target="_blank" rel="noopener" class="preview-link">View link ↗</a>
								</div>
							</div>
						</div>

						<div class="btn-row">
							<button class="secondary-btn" @click="step = 'selectors'">← Fix selectors</button>
							<button class="primary-btn" :disabled="!testResult.ok" @click="saveSite">
								Looks good — save source
							</button>
						</div>
					</div>
				</div>

				<!-- Step 4: Results + suggestions -->
				<div v-else-if="step === 'done'" class="modal-body">
					<div v-if="saving" class="state-msg">Saving and matching your list…</div>
					<div v-else>
						<p class="step-desc done-title">Source added!</p>

						<div v-if="autoLinked.length" class="result-section">
							<h4 class="result-heading">Auto-linked ({{ autoLinked.length }})</h4>
							<ul class="result-list">
								<li v-for="m in autoLinked" :key="m.mangaId">{{ m.title }}</li>
							</ul>
						</div>

						<div v-if="suggestions.length" class="result-section">
							<h4 class="result-heading">Possible matches — confirm to link</h4>
							<div v-for="s in suggestions" :key="s.mangaId" class="suggestion-row">
								<div class="suggestion-info">
									<span class="sug-library">{{ s.title }}</span>
									<span class="sug-arrow">→</span>
									<span class="sug-scraped">{{ s.matchedTitle }}</span>
									<span class="sug-score">{{ s.score }}%</span>
								</div>
								<div class="suggestion-actions">
									<button class="confirm-btn" @click="confirmSuggestion(s)">Link</button>
									<button class="dismiss-btn" @click="dismissSuggestion(s)">Dismiss</button>
								</div>
							</div>
						</div>

						<div v-if="!autoLinked.length && !suggestions.length" class="state-msg">
							No matches found in your current list for this source.
						</div>

						<button class="primary-btn mt" @click="$emit('close'); reset()">Done</button>
					</div>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useScraperStore } from '@/stores/scraper';
import type { TestResult, SuggestionMatch, ScraperSite } from '@/types';

const props = defineProps<{ open: boolean; editSite?: ScraperSite | null }>();
defineEmits<{ close: [] }>();

const scraper = useScraperStore();

type Step = 'url' | 'selectors' | 'test' | 'done';
const step = ref<Step>('url');
const siteUrl = ref('');
const siteName = ref('');
const containerSelector = ref('');
const titleSelector = ref('');
const chapterSelector = ref('');
const coverSelector = ref('');
const chapterUrl = ref('');
const useBrowser = ref(false);
const rawImageSelector = ref('');
const chapterImageSelector = computed(() =>
  useBrowser.value ? `browser:${rawImageSelector.value}` : rawImageSelector.value
);
const testing = ref(false);
const saving = ref(false);
const testingChapter = ref(false);
const testError = ref('');
const chapterImageError = ref('');
const testResult = ref<TestResult | null>(null);
const chapterImages = ref<string[]>([]);
const autoLinked = ref<any[]>([]);
const suggestions = ref<SuggestionMatch[]>([]);
const savedSiteId = ref<number | null>(null);

watch(
  () => props.editSite,
  (site) => {
    if (site) {
      siteUrl.value = site.latestReleasesUrl;
      siteName.value = site.name;
      containerSelector.value = site.containerSelector ?? '';
      titleSelector.value = site.titleSelector;
      chapterSelector.value = site.chapterLinkSelector;
      coverSelector.value = site.coverSelector ?? '';
      const raw = site.chapterImageSelector ?? '';
      if (raw.startsWith('browser:')) {
        useBrowser.value = true;
        rawImageSelector.value = raw.slice(8);
      } else {
        useBrowser.value = false;
        rawImageSelector.value = raw;
      }
      step.value = 'selectors';
    }
  },
  { immediate: true },
);

const isEditMode = computed(() => !!props.editSite);

const stepLabel = computed(() => {
  if (props.editSite) {
    const editMap: Partial<Record<Step, string>> = {
      selectors: '1 / 3',
      test: '2 / 3',
      done: '3 / 3',
    };
    return editMap[step.value] ?? '';
  }
  const map: Record<Step, string> = {
    url: '1 / 4',
    selectors: '2 / 4',
    test: '3 / 4',
    done: '4 / 4',
  };
  return map[step.value];
});

async function runTest() {
	step.value = 'test';
	testing.value = true;
	testError.value = '';
	testResult.value = null;
	try {
		testResult.value = await scraper.testSelectors({
			url: siteUrl.value,
			containerSelector: containerSelector.value || undefined,
			titleSelector: titleSelector.value,
			coverSelector: coverSelector.value || undefined,
			chapterLinkSelector: chapterSelector.value,
		});
	} catch (e: any) {
		testError.value = e.response?.data?.error ?? 'Test failed';
	} finally {
		testing.value = false;
	}
}

async function runChapterTest() {
	testingChapter.value = true;
	chapterImageError.value = '';
	chapterImages.value = [];
	try {
		const result = await scraper.testChapterImages({
			url: chapterUrl.value,
			chapterImageSelector: chapterImageSelector.value,
		});
		chapterImages.value = result.images;
		if (!result.images.length) {
			chapterImageError.value = 'No images found — check the selector and try again.';
		}
	} catch (e: any) {
		chapterImageError.value = e.response?.data?.error ?? 'Test failed';
	} finally {
		testingChapter.value = false;
	}
}

async function saveSite() {
	step.value = 'done';
	saving.value = true;
	try {
		const result = await scraper.saveSite({
			url: siteUrl.value,
			name: siteName.value || new URL(siteUrl.value).hostname,
			containerSelector: containerSelector.value || undefined,
			chapterImageSelector: chapterImageSelector.value || undefined,
			titleSelector: titleSelector.value,
			coverSelector: coverSelector.value || undefined,
			chapterLinkSelector: chapterSelector.value,
		});
		savedSiteId.value = result.site.id;
		autoLinked.value = result.autoLinked;
		suggestions.value = result.suggestions;
	} finally {
		saving.value = false;
	}
}

async function confirmSuggestion(s: SuggestionMatch) {
	if (!savedSiteId.value) return;
	await scraper.confirmMatch(savedSiteId.value, s.mangaId, s.scraped);
	suggestions.value = suggestions.value.filter((x) => x.mangaId !== s.mangaId);
	autoLinked.value.push({ mangaId: s.mangaId, title: s.title });
}

function dismissSuggestion(s: SuggestionMatch) {
	suggestions.value = suggestions.value.filter((x) => x.mangaId !== s.mangaId);
}

function reset() {
	step.value = 'url';
	siteUrl.value = '';
	siteName.value = '';
	containerSelector.value = '';
	titleSelector.value = '';
	chapterSelector.value = '';
	coverSelector.value = '';
	chapterUrl.value = '';
	useBrowser.value = false;
	rawImageSelector.value = '';
	chapterImages.value = [];
	chapterImageError.value = '';
	testResult.value = null;
	autoLinked.value = [];
	suggestions.value = [];
	savedSiteId.value = null;
}
</script>

<style scoped>
.scraper-overlay {
	position: fixed;
	inset: 0;
	z-index: 1000;
	background: rgba(0, 0, 0, 0.75);
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 1rem;
}

.scraper-modal {
	background: var(--surface);
	border: 1px solid var(--border);
	border-radius: 8px;
	width: 100%;
	max-width: 700px;
	max-height: 90vh;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.5rem;
	border-bottom: 1px solid var(--border);
	flex-shrink: 0;
}

.modal-title {
	font-family: 'Cinzel', serif;
	font-size: 1rem;
	font-weight: 600;
	letter-spacing: 0.06em;
	display: flex;
	align-items: center;
	gap: 0.75rem;
}

.modal-step {
	font-family: 'Inter', sans-serif;
	font-size: 0.7rem;
	color: var(--muted);
	letter-spacing: 0.1em;
}

.close-btn {
	background: none;
	border: none;
	color: var(--muted);
	font-size: 1rem;
	line-height: 1;
	transition: color 0.2s;
}
.close-btn:hover { color: var(--text); }

.modal-body {
	padding: 1.5rem;
	overflow-y: auto;
	flex: 1;
}

.step-desc {
	font-size: 0.85rem;
	color: var(--muted);
	margin-bottom: 1.5rem;
	line-height: 1.7;
}

.site-link {
	color: var(--accent);
}

.field-group {
	margin-bottom: 1.1rem;
}

.field-label {
	display: block;
	font-size: 0.75rem;
	color: var(--muted);
	letter-spacing: 0.06em;
	margin-bottom: 0.4rem;
}

.required { color: var(--accent); }
.optional { color: var(--muted); font-style: italic; }
.field-hint { font-size: 0.72rem; color: var(--muted); margin-top: 0.3rem; opacity: 0.75; }

.text-input {
	width: 100%;
	background: var(--surface-2);
	border: 1px solid var(--border);
	border-radius: 4px;
	padding: 0.6rem 1rem;
	color: var(--text);
	font-family: inherit;
	font-size: 0.875rem;
	outline: none;
	transition: border-color 0.2s;
}
.text-input:focus { border-color: var(--accent); }
.text-input::placeholder { color: var(--muted); }
.text-input.mono { font-family: monospace; font-size: 0.8rem; }

.btn-row {
	display: flex;
	gap: 0.75rem;
	align-items: center;
	margin-top: 1.5rem;
}

.primary-btn {
	padding: 0.6rem 1.25rem;
	background: var(--accent);
	color: #fff;
	border: none;
	border-radius: 4px;
	font-family: inherit;
	font-size: 0.875rem;
	transition: opacity 0.2s;
}
.primary-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.primary-btn:not(:disabled):hover { opacity: 0.88; }

.secondary-btn {
	padding: 0.6rem 1rem;
	background: transparent;
	color: var(--muted);
	border: 1px solid var(--border);
	border-radius: 4px;
	font-family: inherit;
	font-size: 0.875rem;
	transition: color 0.2s, border-color 0.2s;
}
.secondary-btn:hover { color: var(--text); border-color: rgba(255,255,255,0.15); }

/* Test step */
.test-meta { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
.meta-item { font-size: 0.75rem; color: var(--muted); }
.meta-item.ok { color: #4CAF50; }

.preview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 0.75rem; margin-bottom: 1.25rem; }
.preview-card { background: var(--surface-2); border-radius: 4px; overflow: hidden; border: 1px solid var(--border); }
.preview-cover { aspect-ratio: 2/3; background: var(--bg); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.preview-cover img { width: 100%; height: 100%; object-fit: cover; }
.no-cover { font-size: 2rem; color: var(--border); }
.preview-info { padding: 0.5rem; }
.preview-title { font-size: 0.7rem; color: var(--text); margin-bottom: 2px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.preview-chapter { font-size: 0.65rem; color: var(--muted); }
.preview-link { font-size: 0.65rem; color: var(--accent); }

/* Done step */
.done-title { font-size: 1rem; color: var(--text); font-weight: 500; margin-bottom: 1.5rem; }
.result-section { margin-bottom: 1.5rem; }
.result-heading { font-size: 0.75rem; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.75rem; }
.result-list { list-style: none; display: flex; flex-direction: column; gap: 0.3rem; }
.result-list li { font-size: 0.875rem; color: var(--text); }
.result-list li::before { content: '✓ '; color: #4CAF50; }

.suggestion-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid var(--border); }
.suggestion-info { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; flex-wrap: wrap; }
.sug-library { color: var(--text); }
.sug-arrow { color: var(--muted); }
.sug-scraped { color: var(--accent); }
.sug-score { font-size: 0.7rem; color: var(--muted); }
.suggestion-actions { display: flex; gap: 0.5rem; flex-shrink: 0; }

.confirm-btn { padding: 4px 12px; background: var(--accent-dim); border: 1px solid var(--accent-glow); color: var(--accent); border-radius: 3px; font-size: 0.75rem; font-family: inherit; }
.dismiss-btn { padding: 4px 12px; background: transparent; border: 1px solid var(--border); color: var(--muted); border-radius: 3px; font-size: 0.75rem; font-family: inherit; }

.state-msg { color: var(--muted); font-size: 0.875rem; padding: 2rem 0; text-align: center; }
.state-msg.error { color: var(--accent); }
.mt { margin-top: 1.5rem; }
.mt-sm { margin-top: 0.75rem; }

/* Reader section */
.reader-section { border-top: 1px solid var(--border); margin-top: 1.25rem; padding-top: 1.25rem; }
.reader-section-label { font-size: 0.75rem; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.5rem; }
.chapter-thumb-row { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
.chapter-thumb { width: 60px; height: 80px; object-fit: cover; border-radius: 3px; border: 1px solid var(--border); }
.chapter-img-count { font-size: 0.75rem; color: var(--muted); }

.browser-toggle { margin-bottom: 0.9rem; }
.toggle-label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8rem; color: var(--text); cursor: pointer; }
.toggle-checkbox { accent-color: var(--accent); width: 14px; height: 14px; cursor: pointer; }
</style>
