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
