import os
import logging
from typing import Dict, Any, Optional
from core.database import (
    update_task_status, update_task_filesize, add_usage,
    get_task_info, check_limit, record_abuse_attempt, set_full_usage
)
from core.config import CONFIG
from core.utils import is_tiktok_url, is_twitter_url, is_youtube_url, is_instagram_url
from core.tiktok import download_tiktok
from core.twitter import download_twitter
from core.youtube import download_youtube
from core.instagram import download_instagram
from core.generic import download_generic

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = CONFIG['MAX_FILE_SIZE']


def process_download(task_id: str, url: str, output_path: str, 
                     referer: Optional[str] = None, cookies: Optional[str] = None, 
                     format_id: Optional[str] = None) -> None:
    logger.info(f"Task {task_id}: Starting download for {url} (format: {format_id or 'best'})")

    try:
        update_task_status(task_id, 'processing')
        
        fingerprint, ip = get_task_info(task_id)
        limit_info = check_limit(fingerprint, ip)
        
        if limit_info.get('whitelisted'):
            max_size = None
        else:
            max_size = min(MAX_FILE_SIZE, limit_info['remaining'])
        
        result = _route_download(url, output_path, referer, cookies, format_id, max_size=max_size)

        if result["success"]:
            _handle_success(task_id, result.get('file', output_path))
        else:
            update_task_status(task_id, 'failed', error=result.get('error', 'Unknown error'))
            logger.error(f"Task {task_id}: Download failed - {result.get('error')}")

    except Exception as e:
        logger.critical(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))


def _handle_success(task_id: str, file_path: str) -> None:
    if not os.path.exists(file_path):
        update_task_status(task_id, 'completed', file=file_path)
        logger.info(f"Task {task_id}: Download successful")
        return

    filesize = os.path.getsize(file_path)
    fingerprint, ip = get_task_info(task_id)
    limit_info = check_limit(fingerprint, ip)
    is_whitelisted = limit_info.get('whitelisted', False)

    if not is_whitelisted:
        error_msg = _check_size_limits(filesize, limit_info, fingerprint, ip)
        if error_msg:
            os.remove(file_path)
            update_task_status(task_id, 'failed', error=error_msg)
            logger.warning(f"Task {task_id}: {error_msg}")
            return

    update_task_filesize(task_id, filesize)
    add_usage(fingerprint, ip, filesize)
    update_task_status(task_id, 'completed', file=file_path)
    logger.info(f"Task {task_id}: Download successful")


def _check_size_limits(filesize: int, limit_info: Dict[str, Any], 
                       fingerprint: str, ip: str) -> Optional[str]:
    exceeds_max = filesize > MAX_FILE_SIZE
    exceeds_remaining = filesize > limit_info['remaining']
    
    if not (exceeds_max or exceeds_remaining):
        return None

    should_penalize = record_abuse_attempt(fingerprint, ip)
    if should_penalize:
        set_full_usage(fingerprint, ip)
        return 'Too many oversized downloads. Daily limit fully consumed as penalty.'
    
    filesize_mb = round(filesize / (1024 * 1024))
    
    if exceeds_max:
        return f'File too large ({filesize_mb}MB). Maximum allowed is 1GB.'
    
    remaining_mb = round(limit_info['remaining'] / (1024 * 1024))
    return f'File ({filesize_mb}MB) exceeds remaining quota ({remaining_mb}MB).'


def _route_download(url: str, output_path: str, referer: Optional[str], 
                    cookies: Optional[str], format_id: Optional[str],
                    max_size: Optional[int] = None) -> Dict[str, Any]:
    if is_tiktok_url(url):
        tiktok_format = format_id if format_id and format_id.startswith('tiktok_') else 'tiktok_no_watermark'
        return download_tiktok(url, output_path, format_id=tiktok_format, max_size=max_size)

    if is_twitter_url(url) and format_id and format_id.startswith('twitter_'):
        return download_twitter(url, output_path, format_id=format_id, max_size=max_size)

    if is_youtube_url(url):
        return download_youtube(url, output_path, format_id=format_id, max_size=max_size)

    if is_instagram_url(url):
        return download_instagram(url, output_path, max_size=max_size)

    return download_generic(url, output_path, referer=referer, cookies=cookies, format_id=format_id, max_size=max_size)
