import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '@/composables/useApi';
import type { ScraperSite, TestResult, SuggestionMatch } from '@/types';

export const useScraperStore = defineStore('scraper', () => {
  const sites = ref<ScraperSite[]>([]);

  async function fetchSites() {
    const { data } = await api.get<ScraperSite[]>('/scraper/sites');
    sites.value = data;
  }

  async function testSelectors(payload: {
    url: string;
    containerSelector?: string;
    titleSelector: string;
    coverSelector?: string;
    chapterLinkSelector: string;
  }): Promise<TestResult> {
    const { data } = await api.post<TestResult>('/scraper/test', payload);
    return data;
  }

  async function testChapterImages(payload: {
    url: string;
    chapterImageSelector: string;
  }): Promise<{ images: string[] }> {
    const { data } = await api.post<{ images: string[] }>('/scraper/test-chapter', payload);
    return data;
  }

  async function saveSite(payload: {
    url: string;
    name: string;
    containerSelector?: string;
    chapterImageSelector?: string;
    titleSelector: string;
    coverSelector?: string;
    chapterLinkSelector: string;
  }): Promise<{ site: ScraperSite; autoLinked: any[]; suggestions: SuggestionMatch[] }> {
    const { data } = await api.post('/scraper/sites', payload);
    await fetchSites();
    return data;
  }

  async function confirmMatch(siteId: number, mangaId: number, scraped: any) {
    await api.post(`/scraper/sites/${siteId}/confirm-match`, { mangaId, scraped });
  }

  async function deleteSite(id: number): Promise<void> {
    await api.delete(`/scraper/sites/${id}`)
    await fetchSites()
  }

  return { sites, fetchSites, testSelectors, testChapterImages, saveSite, confirmMatch, deleteSite };
});
