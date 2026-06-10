from .mangadex import fetch_mangadex_releases
from .generic import scrape_with_selectors, test_selectors


def scrape_site(site) -> list[dict]:
    """
    Scrape a ScraperSite and return a list of
    {'title', 'cover_url', 'chapter', 'chapter_url'} dicts.
    MangaDex (and any API-backed site) has empty selectors — skip those.
    """
    if not site.title_selector or not site.chapter_link_selector:
        return []
    return scrape_with_selectors(
        url=site.latest_releases_url,
        title_selector=site.title_selector,
        cover_selector=site.cover_selector,
        chapter_link_selector=site.chapter_link_selector,
        container_selector=site.container_selector,
    )
