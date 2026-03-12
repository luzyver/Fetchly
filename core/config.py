import os
from typing import Any, Dict, List, Tuple


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


CONFIG: Dict[str, Any] = {
    'DOWNLOAD_FOLDER': 'downloads',
    'DB_PATH': os.path.join('downloads', 'tasks.db'),
    'COOKIE_FILE': 'cookies.txt',
    'MAX_WORKERS': 4,
    'CLEANUP_INTERVAL': 3600,
    'RETENTION_PERIOD': 86400,
    'MAX_FILE_SIZE': 1 * 1024 * 1024 * 1024,
    'ADMIN_PASSWORD': _require_env('ADMIN_PASSWORD'),
    'SECRET_KEY': _require_env('SECRET_KEY'),
    'TURNSTILE_SITE_KEY': os.getenv('TURNSTILE_SITE_KEY', ''),
    'TURNSTILE_SECRET_KEY': os.getenv('TURNSTILE_SECRET_KEY', ''),
    'ENABLE_CLEANUP_THREAD': os.getenv('ENABLE_CLEANUP_THREAD', 'true').lower() in ('1', 'true', 'yes'),
    'LOG_JSON': os.getenv('LOG_JSON', '').lower() in ('1', 'true', 'yes'),
    'RATE_LIMIT_WINDOW': int(os.getenv('RATE_LIMIT_WINDOW', '60')),
    'RATE_LIMIT_FETCH': int(os.getenv('RATE_LIMIT_FETCH', '30')),
    'RATE_LIMIT_CONVERT': int(os.getenv('RATE_LIMIT_CONVERT', '10')),
}

USER_AGENTS: Dict[str, str] = {
    'DESKTOP': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'MOBILE': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
}

SUPPORTED_DOMAINS: Dict[str, List[str]] = {
    'youtube': ['youtube.com', 'youtu.be', 'youtube-nocookie.com'],
    'tiktok': ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'],
    'twitter': ['twitter.com', 'x.com'],
    'facebook': ['facebook.com', 'fb.watch'],
    'instagram': ['instagram.com'],
    'other': ['vimeo.com', 'dailymotion.com', 'twitch.tv', 'bilibili.com']
}

DIRECT_SUPPORTED_DOMAINS: Tuple[str, ...] = tuple(
    domain
    for key in ['youtube', 'twitter', 'facebook', 'instagram', 'other']
    for domain in SUPPORTED_DOMAINS[key]
)

os.makedirs(CONFIG['DOWNLOAD_FOLDER'], exist_ok=True)
