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
