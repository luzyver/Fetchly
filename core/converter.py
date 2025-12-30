import os
import logging
from core.database import update_task_status, update_task_filesize, add_usage, get_task_info, check_limit, DAILY_LIMIT_BYTES
from core.utils import is_tiktok_url, is_twitter_url, is_youtube_url, is_instagram_url
from core.tiktok import download_tiktok
from core.twitter import download_twitter
from core.youtube import download_youtube
from core.instagram import download_instagram
from core.generic import download_generic

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1GB max per file


def process_download(task_id, url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Task {task_id}: Starting download for {url} (format: {format_id or 'best'})")

    try:
        update_task_status(task_id, 'processing')

        result = _route_download(url, output_path, referer, cookies, format_id)

        if result["success"]:
            file_path = result.get('file', output_path)

            if os.path.exists(file_path):
                filesize = os.path.getsize(file_path)
                fingerprint, ip = get_task_info(task_id)
                limit_info = check_limit(fingerprint, ip)
                is_whitelisted = limit_info.get('whitelisted', False)

                # Skip all limits for whitelisted users
                if not is_whitelisted:
                    # Check if file exceeds max size limit
                    if filesize > MAX_FILE_SIZE:
                        os.remove(file_path)
                        filesize_mb = round(filesize / (1024 * 1024))
                        error_msg = f'File too large ({filesize_mb}MB). Maximum allowed is 1GB.'
                        update_task_status(task_id, 'failed', error=error_msg)
                        logger.warning(f"Task {task_id}: {error_msg}")
                        return

                    # Check if file exceeds remaining quota
                    if filesize > limit_info['remaining']:
                        os.remove(file_path)
                        filesize_mb = round(filesize / (1024 * 1024))
                        remaining_mb = round(limit_info['remaining'] / (1024 * 1024))
                        error_msg = f'File ({filesize_mb}MB) exceeds remaining quota ({remaining_mb}MB).'
                        update_task_status(task_id, 'failed', error=error_msg)
                        logger.warning(f"Task {task_id}: {error_msg}")
                        return

                update_task_filesize(task_id, filesize)
                add_usage(fingerprint, ip, filesize)

            update_task_status(task_id, 'completed', file=file_path)
            logger.info(f"Task {task_id}: Download successful")
        else:
            update_task_status(task_id, 'failed', error=result.get('error', 'Unknown error'))
            logger.error(f"Task {task_id}: Download failed - {result.get('error')}")

    except Exception as e:
        logger.critical(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))


def _route_download(url, output_path, referer, cookies, format_id):
    if is_tiktok_url(url):
        tiktok_format = format_id if format_id and format_id.startswith('tiktok_') else 'tiktok_no_watermark'
        return download_tiktok(url, output_path, format_id=tiktok_format)

    if is_twitter_url(url) and format_id and format_id.startswith('twitter_'):
        return download_twitter(url, output_path, format_id=format_id)

    if is_youtube_url(url):
        return download_youtube(url, output_path, format_id=format_id)

    if is_instagram_url(url):
        return download_instagram(url, output_path)

    return download_generic(url, output_path, referer=referer, cookies=cookies, format_id=format_id)
