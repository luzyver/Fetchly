import os

CONFIG = {
    'DOWNLOAD_FOLDER': 'downloads',
    'DB_PATH': os.path.join('downloads', 'tasks.db'),
    'MAX_WORKERS': 4,
    'CLEANUP_INTERVAL': 3600,
    'RETENTION_PERIOD': 86400,
}

USER_AGENTS = {
    'DESKTOP': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'MOBILE': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
}

os.makedirs(CONFIG['DOWNLOAD_FOLDER'], exist_ok=True)
