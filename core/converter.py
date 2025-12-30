import os
import logging
from core.database import update_task_status, update_task_filesize, add_usage, get_task_info
from core.utils import is_tiktok_url, is_twitter_url, is_youtube_url, is_instagram_url
from core.tiktok import download_tiktok
from core.twitter import download_twitter
from core.youtube import download_youtube
from core.instagram import download_instagram
from core.generic import download_generic

logger = logging.getLogger(__name__)


def process_download(task_id, url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Task {task_id}: Starting download for {url} (format: {format_id or 'best'})")

    try:
        update_task_status(task_id, 'processing')

        result = _route_download(url, output_path, referer, cookies, format_id)

        if result["success"]:
            file_path = result.get('file', output_path)
            update_task_status(task_id, 'completed', file=file_path)

            if os.path.exists(file_path):
                filesize = os.path.getsize(file_path)
                update_task_filesize(task_id, filesize)

                fingerprint, ip = get_task_info(task_id)
                add_usage(fingerprint, ip, filesize)

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
