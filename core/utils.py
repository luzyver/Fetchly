import os
import ipaddress
from typing import Optional, List
from urllib.parse import urlparse
from core.config import CONFIG, SUPPORTED_DOMAINS, DIRECT_SUPPORTED_DOMAINS


def format_size(size_bytes: Optional[int]) -> str:
    if not size_bytes:
        return ''
    if size_bytes > 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024*1024):.1f} GB"
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def get_domain(url: str) -> str:
    return urlparse(url).netloc


def is_domain_match(url: str, domains: List[str]) -> bool:
    netloc = get_domain(url)
    return any(domain in netloc for domain in domains)


def is_youtube_url(url: str) -> bool:
    return is_domain_match(url, SUPPORTED_DOMAINS['youtube'])


def is_tiktok_url(url: str) -> bool:
    return is_domain_match(url, SUPPORTED_DOMAINS['tiktok'])


def is_twitter_url(url: str) -> bool:
    return is_domain_match(url, SUPPORTED_DOMAINS['twitter'])


def is_instagram_url(url: str) -> bool:
    return is_domain_match(url, SUPPORTED_DOMAINS['instagram'])


def is_direct_supported(url: str) -> bool:
    return is_domain_match(url, DIRECT_SUPPORTED_DOMAINS)


def validate_public_url(url: str) -> Optional[str]:
    parsed = urlparse(url)

    if parsed.scheme not in ('http', 'https'):
        return "Invalid URL scheme"

    if not parsed.netloc:
        return "URL host is required"

    hostname = parsed.hostname or ''
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return "URL host is not allowed"
    except ValueError:
        lowered = hostname.lower()
        if lowered in ('localhost',):
            return "URL host is not allowed"

    return None


def has_cookie_file() -> bool:
    cookie_file = CONFIG.get('COOKIE_FILE')
    return bool(cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100)


def get_cookie_file() -> Optional[str]:
    return CONFIG.get('COOKIE_FILE') if has_cookie_file() else None


_ERROR_MAP = {
    ('login required', 'cookies'): "This video requires authentication.",
    ('private',): "This video is private.",
    ('not available', 'unavailable'): "This video is not available.",
    ('rate', 'limit'): "Rate limit reached. Try again later.",
    ('timeout',): "Request timed out. Try again.",
}


def get_user_error(error_msg: Optional[str]) -> str:
    if not error_msg:
        return "Unable to fetch video formats."

    error_lower = error_msg.lower()
    
    for keywords, message in _ERROR_MAP.items():
        if any(kw in error_lower for kw in keywords):
            return message

    return "Unable to fetch video formats."
