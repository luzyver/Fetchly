import logging
from core.database import update_task_status
from core.tiktok import TikTokDownloader, download_tiktok_video
from core.twitter import is_twitter_url, download_twitter_video
from core.youtube import is_youtube_url, download_youtube_video
from core.generic import is_direct_supported, download_generic_video

logger = logging.getLogger(__name__)


def convert_m3u8(task_id, url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Task {task_id}: Starting conversion for {url} (format: {format_id or 'best'})")

    try:
        update_task_status(task_id, 'processing')

        if TikTokDownloader.is_tiktok_url(url):
            result = _handle_tiktok(url, output_path, format_id)
        elif is_twitter_url(url) and format_id and format_id.startswith('twitter_'):
            result = _handle_twitter(url, output_path, format_id)
        elif is_youtube_url(url):
            result = _handle_youtube(url, output_path, format_id)
        else:
            result = _handle_generic(url, output_path, referer, cookies, format_id)

        if result["success"]:
            update_task_status(task_id, 'completed', file=result.get('file', output_path))
            logger.info(f"Task {task_id}: Download successful")
        else:
            update_task_status(task_id, 'failed', error=result.get('error', 'Unknown error'))
            logger.error(f"Task {task_id}: Download failed - {result.get('error')}")

    except Exception as e:
        logger.critical(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))


def _handle_tiktok(url, output_path, format_id):
    tiktok_format = format_id if format_id and format_id.startswith('tiktok_') else 'tiktok_no_watermark'
    return download_tiktok_video(url, output_path, format_id=tiktok_format)


def _handle_twitter(url, output_path, format_id):
    return download_twitter_video(url, output_path, format_id=format_id)


def _handle_youtube(url, output_path, format_id):
    return download_youtube_video(url, output_path, format_id=format_id)


def _handle_generic(url, output_path, referer, cookies, format_id):
    return download_generic_video(url, output_path, referer=referer, cookies=cookies, format_id=format_id)
