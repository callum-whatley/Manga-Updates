import logging
import threading
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from ..api.sanitize import validate_external_url

logger = logging.getLogger(__name__)
TIMEOUT = 30_000  # ms
_browser_sem = threading.Semaphore(3)


def scrape_page_html(url: str) -> str:
    """
    Render a page with headless Chromium and return the fully hydrated HTML.
    Used for CSR sites where requests.get returns empty HTML.
    Returns '' on failure.
    """
    if not validate_external_url(url):
        logger.warning('scrape_page_html: rejected URL %s', url)
        return ''
    with _browser_sem:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(extra_http_headers={
                    'User-Agent': (
                        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                    )
                })
                page.route('**/*', lambda route: (
                    route.abort('blockedbyclient')
                    if not validate_external_url(route.request.url)
                    else route.continue_()
                ))
                page.goto(url, wait_until='load', timeout=TIMEOUT)
                page.wait_for_timeout(1500)
                return page.content()
            except PWTimeoutError:
                logger.warning('browser scrape timed out for %s', url)
                return ''
            except Exception as e:
                logger.error('browser scrape failed for %s: %s', url, e)
                return ''
            finally:
                browser.close()


def fetch_json_in_browser(url: str) -> str:
    """
    Navigate to the site origin first (acquires Cloudflare cookies), then call
    fetch(url) from within the page to bypass bot detection.
    Returns the response body text, or '' on failure.
    """
    from urllib.parse import urlparse as _up
    parsed = _up(url)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    if not validate_external_url(origin):
        return ''
    with _browser_sem:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(extra_http_headers={
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                    )
                })
                page.route('**/*', lambda route: (
                    route.abort('blockedbyclient')
                    if not validate_external_url(route.request.url)
                    else route.continue_()
                ))
                page.goto(origin, wait_until='load', timeout=TIMEOUT)
                page.wait_for_timeout(1000)
                result = page.evaluate(
                    """async (apiUrl) => {
                        try {
                            const r = await fetch(apiUrl, {credentials: 'include'});
                            return await r.text();
                        } catch (e) { return ''; }
                    }""",
                    url,
                )
                return result or ''
            except PWTimeoutError:
                logger.warning('fetch_json_in_browser timed out for %s', url)
                return ''
            except Exception as e:
                logger.error('fetch_json_in_browser failed for %s: %s', url, e)
                return ''
            finally:
                browser.close()


def scrape_chapter_images(url: str, selector: str) -> list[str]:
    """
    Render a chapter page with headless Chromium and return image src values
    matching `selector`. Used for CSR sites where requests.get returns empty HTML.
    """
    with _browser_sem:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(extra_http_headers={
                    'User-Agent': (
                        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                    )
                })
                page.route('**/*', lambda route: (
                    route.abort('blockedbyclient')
                    if not validate_external_url(route.request.url)
                    else route.continue_()
                ))
                page.goto(url, wait_until='load', timeout=TIMEOUT)
                page.wait_for_timeout(1500)
                srcs = page.evaluate(
                    """(sel) => Array.from(document.querySelectorAll(sel))
                           .map(el => el.src || el.getAttribute('data-src') || '')
                           .filter(Boolean)""",
                    selector,
                )
                return srcs
            except PWTimeoutError:
                logger.warning('browser scrape timed out for %s', url)
                return []
            except Exception as e:
                logger.error('browser scrape failed for %s: %s', url, e)
                return []
            finally:
                browser.close()
