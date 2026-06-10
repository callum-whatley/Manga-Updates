"""Input sanitization helpers."""
import ipaddress
from urllib.parse import urlparse


def validate_external_url(url: str, max_length: int = 2048) -> str | None:
    """
    Return the URL if it is a safe, external HTTP/HTTPS URL, else None.
    Blocks private/loopback addresses to prevent SSRF.
    """
    if not url or len(url) > max_length:
        return None
    try:
        p = urlparse(url)
    except Exception:
        return None
    if p.scheme not in ('http', 'https'):
        return None
    host = p.hostname
    if not host:
        return None
    # Block localhost variants
    if host in ('localhost', '0.0.0.0'):
        return None
    # Block private/loopback IP ranges
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved:
            return None
    except ValueError:
        pass  # hostname, not an IP — allow it
    return url


def sanitize_str(value: str | None, max_length: int = 500) -> str:
    """Strip and truncate a plain string field."""
    if not value:
        return ''
    return value.strip()[:max_length]
