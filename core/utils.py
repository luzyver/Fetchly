import os
from urllib.parse import urlparse
from core.config import CONFIG, SUPPORTED_DOMAINS, DIRECT_SUPPORTED_DOMAINS


def format_size(size_bytes):
    if not size_bytes:
        return ''
    if size_bytes > 1024 * 1024 * 1024:
        return f"{size_bytes / (1024*1024*1024):.1f} GB"
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def get_domain(url):
    return urlparse(url).netloc


def is_domain_match(url, domains):
    netloc = get_domain(url)
    return any(domain in netloc for domain in domains)


def is_youtube_url(url):
    return is_domain_match(url, SUPPORTED_DOMAINS['youtube'])


def is_tiktok_url(url):
    return is_domain_match(url, SUPPORTED_DOMAINS['tiktok'])


def is_twitter_url(url):
    return is_domain_match(url, SUPPORTED_DOMAINS['twitter'])


def is_direct_supported(url):
    return is_domain_match(url, DIRECT_SUPPORTED_DOMAINS)


def has_cookie_file():
    cookie_file = CONFIG.get('COOKIE_FILE')
    return cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100


def get_cookie_file():
    return CONFIG.get('COOKIE_FILE') if has_cookie_file() else None


def get_user_error(error_msg):
    if not error_msg:
        return "Unable to fetch video formats."

    error_lower = error_msg.lower()
    
    error_map = {
        ('login required', 'cookies'): "This video requires authentication.",
        ('private',): "This video is private.",
        ('not available', 'unavailable'): "This video is not available.",
        ('rate', 'limit'): "Rate limit reached. Try again later.",
        ('timeout',): "Request timed out. Try again.",
    }

    for keywords, message in error_map.items():
        if any(kw in error_lower for kw in keywords):
            return message

    return "Unable to fetch video formats."
