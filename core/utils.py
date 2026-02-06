import os
import glob
import time
import threading
import subprocess
from typing import Optional, List, Dict, Any
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


def _normalize_host(hostname: Optional[str]) -> str:
    if not hostname:
        return ''
    return hostname.lower().rstrip('.')


def is_domain_match(url: str, domains: List[str]) -> bool:
    host = _normalize_host(urlparse(url).hostname)
    if not host:
        return False
    for domain in domains:
        d = _normalize_host(domain)
        if host == d or host.endswith(f".{d}"):
            return True
    return False


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


def get_download_size(base_path: str) -> int:
    max_size = 0
    for filepath in glob.glob(f"{base_path}*"):
        if not os.path.isfile(filepath):
            continue
        try:
            size = os.path.getsize(filepath)
            if size > max_size:
                max_size = size
        except OSError:
            pass
    return max_size


def cleanup_partial(output_path: str, logger=None) -> None:
    base_path = output_path.rsplit('.', 1)[0]
    for pattern in [f"{base_path}*", f"{output_path}*"]:
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
                if logger:
                    logger.info(f"Cleaned up: {filepath}")
            except OSError:
                pass


def run_with_size_monitor(cmd: list, output_path: str, max_size: Optional[int],
                          logger, timeout: Optional[int] = None) -> Dict[str, Any]:
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if max_size is None:
        try:
            _, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            return {"success": False, "error": "Download timeout"}
        if process.returncode == 0 and os.path.exists(output_path):
            return {"success": True, "file": output_path}
        return {"success": False, "error": stderr.decode().strip()[-300:] if stderr else "Download failed"}

    size_exceeded = [False]
    final_size = [0]
    monitor_stop = threading.Event()

    def monitor():
        base_path = output_path.rsplit('.', 1)[0]
        while not monitor_stop.is_set():
            current_size = get_download_size(base_path)
            final_size[0] = current_size
            if current_size > max_size:
                size_exceeded[0] = True
                if logger:
                    logger.warning(f"Size limit exceeded: {current_size} > {max_size}, killing process")
                process.kill()
                break
            time.sleep(1)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    try:
        _, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        monitor_stop.set()
        return {"success": False, "error": "Download timeout"}
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=2)

    if size_exceeded[0]:
        cleanup_partial(output_path, logger=logger)
        return {
            "success": False,
            "error": "Download cancelled: file size exceeded limit",
            "size_exceeded": True,
            "downloaded_size": final_size[0]
        }

    if process.returncode == 0 and os.path.exists(output_path):
        return {"success": True, "file": output_path}

    return {"success": False, "error": stderr.decode().strip()[-300:] if stderr else "Download failed"}
