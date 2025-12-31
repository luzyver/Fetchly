import os
from typing import Dict, List, Tuple

CONFIG: Dict[str, any] = {
    'DOWNLOAD_FOLDER': 'downloads',
    'DB_PATH': os.path.join('downloads', 'tasks.db'),
    'COOKIE_FILE': 'cookies.txt',
    'MAX_WORKERS': 4,
    'CLEANUP_INTERVAL': 3600,
    'RETENTION_PERIOD': 86400,
    'MAX_FILE_SIZE': 1 * 1024 * 1024 * 1024,
    'ADMIN_PASSWORD': os.getenv('ADMIN_PASSWORD', 'admin123'),
    'SECRET_KEY': os.getenv('SECRET_KEY', 'change-me-in-production'),
    'TURNSTILE_SITE_KEY': os.getenv('TURNSTILE_SITE_KEY', ''),
    'TURNSTILE_SECRET_KEY': os.getenv('TURNSTILE_SECRET_KEY', ''),
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
