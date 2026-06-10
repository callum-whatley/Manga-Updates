export interface User {
  id: number;
  email: string;
  displayName: string;
  avatarUrl: string | null;
  isAdmin: boolean;
}

export interface MangaSource {
  siteId: number;
  siteName: string;
  latestChapter: number;
  latestChapterUrl: string | null;
  updatedAt: string | null;
}

export interface MangaEntry {
  id: number;
  title: string;
  coverUrl: string | null;
  latestChapter: number;
  sources: MangaSource[];
  currentChapter: number;
  currentChapterUrl: string | null;
  hasUpdate: boolean;
  updatedAt: string | null;
}

export interface ScraperSite {
  id: number;
  name: string;
  latestReleasesUrl: string;
  containerSelector: string | null;
  chapterImageSelector: string | null;
  titleSelector: string;
  coverSelector: string | null;
  chapterLinkSelector: string;
  isActive: boolean;
}

export interface TestPreviewItem {
  title: string;
  cover_url: string | null;
  chapter: number;
  chapter_url: string;
}

export interface TestResult {
  ok: boolean;
  error?: string;
  counts: { titles: number; chapterLinks: number; covers: number };
  results: TestPreviewItem[];
}

export interface SuggestionMatch {
  mangaId: number;
  title: string;
  matchedTitle: string;
  score: number;
  scraped: TestPreviewItem;
}
