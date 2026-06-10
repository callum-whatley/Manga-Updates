# Manage Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Manage Sources" modal that lets users view existing scraper sources, test whether selectors still work, edit them via the existing flow, and delete them.

**Architecture:** New `ManageSources.vue` modal owns the source list, test state (per-site badge + result popup), inline delete confirm, and emits `edit-site` to the parent. `ScraperTool.vue` gains an optional `editSite` prop that pre-fills fields and starts at the selectors step. `HomeView.vue` orchestrates both modals and passes `editSite` through. The scraper store gains a `deleteSite` action.

**Tech Stack:** Vue 3 Composition API, TypeScript, Pinia, Playwright (e2e tests), existing Axios API client at `@/composables/useApi`.

---

## File Map

| Action | File |
|--------|------|
| Modify | `frontend/src/stores/scraper.ts` |
| Modify | `frontend/src/components/NavBar.vue` |
| Modify | `frontend/src/views/HomeView.vue` |
| Create | `frontend/src/components/ManageSources.vue` |
| Modify | `frontend/src/components/ScraperTool.vue` |
| Create | `frontend/e2e/manage-sources.spec.ts` |

---

## Task 1: Add `deleteSite` to scraper store

**Files:**
- Modify: `frontend/src/stores/scraper.ts`

- [ ] **Step 1: Add `deleteSite` action and export it**

Replace the `return` line at the bottom of `frontend/src/stores/scraper.ts` with the following (the rest of the file is unchanged):

```ts
  async function deleteSite(id: number): Promise<void> {
    await api.delete(`/scraper/sites/${id}`)
    await fetchSites()
  }

  return { sites, fetchSites, testSelectors, testChapterImages, saveSite, confirmMatch, deleteSite }
```

- [ ] **Step 2: Verify the store builds cleanly**

```bash
cd "/home/cwhat/Documents/Coding/Projects/Manga Updates/frontend"
yarn build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

---

## Task 2: Add "Manage Sources" button to NavBar and wire HomeView

**Files:**
- Modify: `frontend/src/components/NavBar.vue`
- Modify: `frontend/src/views/HomeView.vue`

- [ ] **Step 1: Add `open-manage` emit and button to NavBar**

In `frontend/src/components/NavBar.vue`, replace the `defineEmits` line:

```ts
defineEmits<{ 'open-scraper': [], 'open-manage': [] }>();
```

Add the "Sources" button after the closing `</button>` of `.add-source-btn` (before `.check-all-btn`):

```html
<button class="manage-sources-btn" @click="$emit('open-manage')" title="Manage source sites">
  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
    <line x1="8" y1="6" x2="21" y2="6"/>
    <line x1="8" y1="12" x2="21" y2="12"/>
    <line x1="8" y1="18" x2="21" y2="18"/>
    <line x1="3" y1="6" x2="3.01" y2="6"/>
    <line x1="3" y1="12" x2="3.01" y2="12"/>
    <line x1="3" y1="18" x2="3.01" y2="18"/>
  </svg>
  <span>Sources</span>
</button>
```

Add this style block in `<style scoped>`:

```css
.manage-sources-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.85rem;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  transition: color 0.2s, border-color 0.2s;
}
.manage-sources-btn:hover {
  color: var(--text);
  border-color: rgba(255,255,255,0.15);
}
```

- [ ] **Step 2: Wire ManageSources into HomeView**

Replace the entire content of `frontend/src/views/HomeView.vue` with:

```vue
<template>
  <div class="home">
    <NavBar @open-scraper="scraperOpen = true" @open-manage="manageSourcesOpen = true" />
    <ScraperTool :open="scraperOpen" :edit-site="scraperEditSite" @close="handleScraperClose" />
    <ManageSources :open="manageSourcesOpen" @close="manageSourcesOpen = false" @edit-site="handleEditSite" />

    <main class="main">
      <div class="content">
        <div class="page-header">
          <div class="header-left">
            <h2 class="page-title">My List</h2>
            <span class="count" v-if="!loading">{{ updatedCount }} update{{ updatedCount !== 1 ? 's' : '' }}</span>
          </div>
          <AddMangaForm />
        </div>

        <div v-if="loading && !list.length" class="state-msg">Loading…</div>
        <div v-else-if="!list.length" class="state-msg empty">
          <span class="empty-icon">巻</span>
          <p>Your list is empty. Add a manga above to get started.</p>
        </div>

        <div v-else class="grid">
          <MangaCard v-for="entry in sortedList" :key="entry.id" :entry="entry" />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import NavBar from '@/components/NavBar.vue';
import AddMangaForm from '@/components/AddMangaForm.vue';
import MangaCard from '@/components/MangaCard.vue';
import ScraperTool from '@/components/ScraperTool.vue';
import ManageSources from '@/components/ManageSources.vue';
import { useMangaStore } from '@/stores/manga';
import type { ScraperSite } from '@/types';

const scraperOpen = ref(false);
const manageSourcesOpen = ref(false);
const scraperEditSite = ref<ScraperSite | null>(null);

const manga = useMangaStore();
const list = computed(() => manga.list);
const loading = computed(() => manga.loading);

const updatedCount = computed(() => list.value.filter((m) => m.hasUpdate).length);

const sortedList = computed(() =>
  [...list.value].sort((a, b) => {
    if (a.hasUpdate !== b.hasUpdate) return a.hasUpdate ? -1 : 1;
    return a.title.localeCompare(b.title);
  }),
);

function handleEditSite(site: ScraperSite) {
  manageSourcesOpen.value = false;
  scraperEditSite.value = site;
  scraperOpen.value = true;
}

function handleScraperClose() {
  scraperOpen.value = false;
  scraperEditSite.value = null;
}

onMounted(() => {
  manga.fetchList();
});
</script>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main {
  flex: 1;
  padding: 2.5rem 2rem;
}

.content {
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 2rem;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.page-title {
  font-family: 'Cinzel', serif;
  font-size: 1.4rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text);
}

.count {
  font-size: 0.75rem;
  color: var(--accent);
  letter-spacing: 0.06em;
}

.state-msg {
  text-align: center;
  color: var(--muted);
  font-size: 0.875rem;
  padding: 4rem 0;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.empty-icon {
  font-size: 3rem;
  color: var(--border);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1.25rem;
}

@media (min-width: 640px) {
  .grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
}
</style>
```

- [ ] **Step 3: Verify build**

```bash
cd "/home/cwhat/Documents/Coding/Projects/Manga Updates/frontend"
yarn build 2>&1 | tail -20
```

Expected: build succeeds (ManageSources import will fail until Task 3 — that's OK, verify the NavBar changes compile).

---

## Task 3: Create ManageSources.vue

**Files:**
- Create: `frontend/src/components/ManageSources.vue`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ManageSources.vue` with the following content:

```vue
<template>
  <Teleport to="body">
    <div v-if="open" class="manage-overlay" @click.self="$emit('close')">
      <div class="manage-modal">
        <div class="modal-header">
          <span class="modal-title">Manage Sources</span>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="loading" class="state-msg">Loading…</div>
          <div v-else-if="!sites.length" class="state-msg">
            No sources added yet. Use "Add Source" to add one.
          </div>
          <div v-else class="site-list">
            <div v-for="site in sites" :key="site.id" class="site-row">
              <div class="site-info">
                <span class="site-name">{{ site.name }}</span>
                <span class="site-url">{{ truncateUrl(site.latestReleasesUrl) }}</span>
              </div>
              <div class="site-actions">
                <!-- Badge (only shown after a test has run) -->
                <button
                  v-if="stateOf(site.id).badge === 'pass' || stateOf(site.id).badge === 'fail'"
                  class="badge"
                  :class="stateOf(site.id).badge"
                  :ref="(el) => { if (el) badgeRefs[site.id] = el as HTMLElement }"
                  @click="togglePopup(site.id)"
                >
                  {{ stateOf(site.id).badge === 'pass' ? '✓ Pass' : '✗ Fail' }}
                </button>
                <span v-else-if="stateOf(site.id).badge === 'testing'" class="badge testing">…</span>

                <button
                  class="action-btn"
                  :disabled="stateOf(site.id).badge === 'testing'"
                  @click="runTest(site)"
                >Test</button>

                <button class="action-btn" @click="$emit('edit-site', site)">Edit</button>

                <template v-if="confirmDeleteId === site.id">
                  <span class="confirm-text">Sure?</span>
                  <button class="action-btn danger" @click="doDelete(site.id)">Yes</button>
                  <button class="action-btn" @click="confirmDeleteId = null">No</button>
                </template>
                <button v-else class="action-btn" @click="confirmDeleteId = site.id">Delete</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Test result popup — Teleported to body to avoid modal overflow clipping -->
    <div
      v-if="popupSiteId !== null && stateOf(popupSiteId).result"
      class="test-popup"
      :style="popupStyle"
      @click.stop
    >
      <button class="popup-close" @click="popupSiteId = null">✕</button>
      <div class="popup-counts">
        <span :class="{ ok: (stateOf(popupSiteId).result?.counts.titles ?? 0) > 0 }">
          {{ stateOf(popupSiteId).result?.counts.titles }} titles
        </span>
        <span :class="{ ok: (stateOf(popupSiteId).result?.counts.chapterLinks ?? 0) > 0 }">
          {{ stateOf(popupSiteId).result?.counts.chapterLinks }} chapter links
        </span>
        <span :class="{ ok: (stateOf(popupSiteId).result?.counts.covers ?? 0) > 0 }">
          {{ stateOf(popupSiteId).result?.counts.covers }} covers
        </span>
      </div>
      <div v-if="stateOf(popupSiteId).result?.error" class="popup-error">
        {{ stateOf(popupSiteId).result?.error }}
      </div>
      <div v-else-if="stateOf(popupSiteId).result?.results.length" class="popup-preview">
        <div
          v-for="(item, i) in stateOf(popupSiteId).result?.results.slice(0, 4)"
          :key="i"
          class="popup-card"
        >
          <div class="popup-cover">
            <img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" />
            <span v-else class="no-cover">巻</span>
          </div>
          <div class="popup-info">
            <p class="popup-title">{{ item.title }}</p>
            <p class="popup-chapter">Ch. {{ item.chapter }}</p>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue';
import { useScraperStore } from '@/stores/scraper';
import type { ScraperSite, TestResult } from '@/types';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; 'edit-site': [site: ScraperSite] }>();

const scraper = useScraperStore();
const sites = computed(() => scraper.sites);

type BadgeState = 'idle' | 'testing' | 'pass' | 'fail';
interface SiteTestState {
  badge: BadgeState;
  result: TestResult | null;
}

const testState = reactive<Record<number, SiteTestState>>({});
const confirmDeleteId = ref<number | null>(null);
const popupSiteId = ref<number | null>(null);
const badgeRefs: Record<number, HTMLElement> = {};
const loading = ref(false);

function stateOf(id: number): SiteTestState {
  return testState[id] ?? { badge: 'idle', result: null };
}

const popupStyle = computed(() => {
  if (popupSiteId.value === null) return {};
  const el = badgeRefs[popupSiteId.value];
  if (!el) return {};
  const rect = el.getBoundingClientRect();
  return {
    position: 'fixed' as const,
    top: `${rect.bottom + 8}px`,
    left: `${Math.min(rect.left, window.innerWidth - 320)}px`,
    zIndex: 9999,
  };
});

watch(
  () => props.open,
  async (val) => {
    if (val) {
      loading.value = true;
      await scraper.fetchSites();
      loading.value = false;
      confirmDeleteId.value = null;
      popupSiteId.value = null;
    }
  },
);

async function runTest(site: ScraperSite) {
  testState[site.id] = { badge: 'testing', result: null };
  popupSiteId.value = null;
  try {
    const result = await scraper.testSelectors({
      url: site.latestReleasesUrl,
      containerSelector: site.containerSelector ?? undefined,
      titleSelector: site.titleSelector,
      coverSelector: site.coverSelector ?? undefined,
      chapterLinkSelector: site.chapterLinkSelector,
    });
    testState[site.id] = { badge: result.ok ? 'pass' : 'fail', result };
  } catch (e: any) {
    testState[site.id] = {
      badge: 'fail',
      result: {
        ok: false,
        error: e.response?.data?.error ?? 'Test failed',
        counts: { titles: 0, chapterLinks: 0, covers: 0 },
        results: [],
      },
    };
  }
}

function togglePopup(siteId: number) {
  popupSiteId.value = popupSiteId.value === siteId ? null : siteId;
}

async function doDelete(id: number) {
  await scraper.deleteSite(id);
  confirmDeleteId.value = null;
  delete testState[id];
}

function truncateUrl(url: string): string {
  try {
    const u = new URL(url);
    const path = u.pathname.length > 24 ? u.pathname.slice(0, 24) + '…' : u.pathname;
    return u.hostname + path;
  } catch {
    return url.slice(0, 40);
  }
}
</script>

<style scoped>
.manage-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.manage-modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  width: 100%;
  max-width: 680px;
  max-height: 80vh;
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
  padding: 1rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.state-msg {
  color: var(--muted);
  font-size: 0.875rem;
  padding: 2rem 0;
  text-align: center;
}

.site-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.site-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
}
.site-row:last-child { border-bottom: none; }

.site-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.site-name {
  font-size: 0.875rem;
  color: var(--text);
  font-weight: 500;
}

.site-url {
  font-size: 0.72rem;
  color: var(--muted);
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.site-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  font-family: inherit;
  letter-spacing: 0.02em;
}
.badge.pass { background: rgba(76,175,80,0.15); color: #4CAF50; }
.badge.fail { background: rgba(230,57,70,0.15); color: var(--accent); }
.badge.testing { background: var(--surface-2); color: var(--muted); cursor: default; }

.action-btn {
  padding: 4px 10px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 3px;
  font-size: 0.75rem;
  font-family: inherit;
  transition: color 0.2s, border-color 0.2s;
}
.action-btn:hover:not(:disabled) { color: var(--text); border-color: rgba(255,255,255,0.15); }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.action-btn.danger { color: var(--accent); border-color: var(--accent-glow); }
.action-btn.danger:hover { background: var(--accent-dim); }

.confirm-text {
  font-size: 0.75rem;
  color: var(--muted);
}

/* Test result popup */
.test-popup {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1rem;
  width: 300px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.6);
}

.popup-close {
  float: right;
  background: none;
  border: none;
  color: var(--muted);
  font-size: 0.75rem;
  cursor: pointer;
  line-height: 1;
  padding: 0;
  margin-left: 0.5rem;
}
.popup-close:hover { color: var(--text); }

.popup-counts {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
  font-size: 0.72rem;
  color: var(--muted);
}
.popup-counts .ok { color: #4CAF50; }

.popup-error {
  font-size: 0.8rem;
  color: var(--accent);
}

.popup-preview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.popup-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.popup-cover {
  aspect-ratio: 2/3;
  background: var(--bg);
  border-radius: 3px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
}
.popup-cover img { width: 100%; height: 100%; object-fit: cover; }
.no-cover { font-size: 1.2rem; color: var(--border); }

.popup-info { }
.popup-title {
  font-size: 0.62rem;
  color: var(--text);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.popup-chapter { font-size: 0.6rem; color: var(--muted); }
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd "/home/cwhat/Documents/Coding/Projects/Manga Updates/frontend"
yarn build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

---

## Task 4: Update ScraperTool.vue for edit mode

**Files:**
- Modify: `frontend/src/components/ScraperTool.vue`

- [ ] **Step 1: Add `editSite` prop and import**

In the `<script setup lang="ts">` block of `ScraperTool.vue`, replace:

```ts
defineProps<{ open: boolean }>();
defineEmits<{ close: [] }>();
```

with:

```ts
const props = defineProps<{ open: boolean; editSite?: ScraperSite | null }>();
defineEmits<{ close: [] }>();
```

And add `watch` to the imports and the `ScraperSite` type import:

```ts
import { ref, computed, watch } from 'vue';
import { useScraperStore } from '@/stores/scraper';
import type { TestResult, SuggestionMatch, ScraperSite } from '@/types';
```

- [ ] **Step 2: Add watcher to pre-fill fields when editSite changes**

After the existing `ref` declarations (after `savedSiteId`), add:

```ts
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
      chapterImageSelector.value = site.chapterImageSelector ?? '';
      step.value = 'selectors';
    }
  },
  { immediate: true },
);
```

- [ ] **Step 3: Update step label for edit mode**

Replace the existing `stepLabel` computed:

```ts
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
```

- [ ] **Step 4: Update modal title**

In the template, replace the `Add Source` text in the modal header:

```html
<div class="modal-title">
  <span class="modal-step">{{ stepLabel }}</span>
  {{ editSite ? 'Edit Source' : 'Add Source' }}
</div>
```

Since we switched to `props`, we need to reference `props.editSite` in the template or destructure. Update the template reference to use `props.editSite` or add a computed alias. Add this after the `stepLabel` computed:

```ts
const isEditMode = computed(() => !!props.editSite);
```

Then use `isEditMode` in the template instead of `editSite`:

```html
{{ isEditMode ? 'Edit Source' : 'Add Source' }}
```

- [ ] **Step 5: Show read-only URL and hide Back button in selectors step when in edit mode**

In the `selectors` step section of the template, replace the existing `step-desc` paragraph block with:

```html
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
```

In the `btn-row` at the bottom of the selectors step, change the Back button to hide in edit mode:

```html
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
```

- [ ] **Step 6: Verify build**

```bash
cd "/home/cwhat/Documents/Coding/Projects/Manga Updates/frontend"
yarn build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

---

## Task 5: Write e2e tests

**Files:**
- Create: `frontend/e2e/manage-sources.spec.ts`

- [ ] **Step 1: Create the test file**

Create `frontend/e2e/manage-sources.spec.ts`:

```ts
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
  await setupMocks(page);
  // After deletion the GET returns empty list
  await page.route('**/api/scraper/sites', (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ json: [] });
    } else if (route.request().method() === 'DELETE') {
      route.fulfill({ status: 204, body: '' });
    }
  });
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
```

- [ ] **Step 2: Run the tests**

```bash
cd "/home/cwhat/Documents/Coding/Projects/Manga Updates/frontend"
yarn test:e2e manage-sources.spec.ts 2>&1 | tail -40
```

Expected: all 9 tests pass. Playwright will auto-start the dev server via the `webServer` config.
