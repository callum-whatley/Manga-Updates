import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '@/composables/useApi';
import type { MangaEntry } from '@/types';

export const useMangaStore = defineStore('manga', () => {
  const list = ref<MangaEntry[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchList() {
    try {
      loading.value = true;
      error.value = null;
      const { data } = await api.get<MangaEntry[]>('/manga/');
      list.value = data;
    } catch (e: any) {
      error.value = e.response?.data?.error ?? 'Failed to load manga list';
    } finally {
      loading.value = false;
    }
  }

  async function addManga(title: string): Promise<MangaEntry | null> {
    try {
      const { data } = await api.post<MangaEntry>('/manga/', { title });
      list.value.push(data);
      return data;
    } catch (e: any) {
      error.value = e.response?.data?.error ?? 'Failed to add manga';
      return null;
    }
  }

  async function removeManga(id: number) {
    await api.delete(`/manga/${id}`);
    list.value = list.value.filter((m) => m.id !== id);
  }

  async function updateProgress(id: number, chapter: number, url: string) {
    try {
      await api.patch(`/manga/${id}/progress`, { chapter, url });
      const item = list.value.find((m) => m.id === id);
      if (item) { item.currentChapter = chapter; item.currentChapterUrl = url; }
    } catch (e) {
      console.warn('Failed to save reading progress', e);
    }
  }

  async function checkUpdates(id: number) {
    const { data } = await api.post<MangaEntry>(`/manga/${id}/check`);
    const idx = list.value.findIndex((m) => m.id === id);
    if (idx !== -1) list.value[idx] = data;
    return data;
  }

  async function checkAll() {
    loading.value = true;
    try {
      const { data } = await api.post<MangaEntry[]>('/manga/check-all');
      list.value = data;
    } finally {
      loading.value = false;
    }
  }

  async function removeSource(mangaId: number, siteId: number) {
    try {
      const { data } = await api.delete<MangaEntry>(`/manga/${mangaId}/sources/${siteId}`);
      const idx = list.value.findIndex((m) => m.id === mangaId);
      if (idx !== -1) {
        // Replace with the server's updated entry so coverUrl falls back to the
        // next available source.
        list.value[idx] = data;
      }
    } catch (e: any) {
      error.value = e.response?.data?.error ?? 'Failed to remove source';
    }
  }

  return { list, loading, error, fetchList, addManga, removeManga, updateProgress, checkUpdates, checkAll, removeSource };
});
