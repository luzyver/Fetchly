import os
import subprocess
import logging
from urllib.parse import urlparse
from core.config import CONFIG, USER_AGENTS, DIRECT_SUPPORTED_DOMAINS
from core.database import update_task_status
from core.tiktok import TikTokDownloader, download_tiktok_video

logger = logging.getLogger(__name__)


def is_direct_supported(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in DIRECT_SUPPORTED_DOMAINS)


def is_twitter_url(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in ['twitter.com', 'x.com'])


def convert_m3u8(task_id, url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Task {task_id}: Starting conversion for {url} (format: {format_id or 'best'})")

    try:
        update_task_status(task_id, 'processing')

        if TikTokDownloader.is_tiktok_url(url):
            _handle_tiktok(task_id, url, output_path, format_id)
            return

        if is_twitter_url(url) and format_id and format_id.startswith('twitter_'):
            _handle_twitter(task_id, url, output_path, format_id)
            return

        _handle_generic(task_id, url, output_path, referer, cookies, format_id)

    except Exception as e:
        logger.critical(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))


def _handle_tiktok(task_id, url, output_path, format_id):
    logger.info(f"Task {task_id}: Detected TikTok URL (format: {format_id})")
    tiktok_format = format_id if format_id and format_id.startswith('tiktok_') else 'tiktok_no_watermark'
    result = download_tiktok_video(url, output_path, format_id=tiktok_format)

    if result["success"]:
        update_task_status(task_id, 'completed', file=result.get('file', output_path))
        logger.info(f"Task {task_id}: TikTok download successful - {result.get('title', 'Unknown')}")
    else:
        logger.error(f"Task {task_id}: TikTok download failed: {result.get('error')}")
        update_task_status(task_id, 'failed', error=f"TikTok: {result.get('error')}")


def _handle_twitter(task_id, url, output_path, format_id):
    logger.info(f"Task {task_id}: Detected Twitter URL with video selection (format: {format_id})")
    
    video_index = int(format_id.replace('twitter_', ''))
    
    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    cmd = ['yt-dlp', '--no-check-certificate', '-f', 'bestvideo+bestaudio/best',
           '--merge-output-format', 'mp4', '--playlist-items', str(video_index + 1),
           '-o', output_path, url]

    if has_cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    try:
        logger.info(f"Task {task_id}: Downloading Twitter video {video_index + 1}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()

        if process.returncode == 0:
            update_task_status(task_id, 'completed', file=output_path)
            logger.info(f"Task {task_id}: Twitter download successful")
        else:
            last_error = stderr.decode().strip()[-300:]
            logger.error(f"Task {task_id}: Twitter download failed: {last_error}")
            update_task_status(task_id, 'failed', error=f"Twitter: {last_error}")

    except Exception as e:
        logger.error(f"Task {task_id}: Twitter exception: {e}")
        update_task_status(task_id, 'failed', error=str(e))


def _handle_generic(task_id, url, output_path, referer, cookies, format_id):
    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    current_referer = referer or domain
    direct_supported = is_direct_supported(url)

    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    success = False
    last_error = None

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        try:
            cmd = _build_ytdlp_cmd(ua, output_path, has_cookie_file, cookie_file, direct_supported,
                                   format_id, current_referer, domain, cookies, url)

            logger.info(f"Task {task_id}: Attempt {i+1}/2 (UA: {'Mobile' if 'Mobile' in ua else 'Desktop'})")

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = process.communicate()

            if process.returncode == 0:
                update_task_status(task_id, 'completed', file=output_path)
                logger.info(f"Task {task_id}: Conversion successful")
                success = True
                break
            else:
                last_error = stderr.decode().strip()[-300:]
                logger.warning(f"Task {task_id}: Attempt {i+1} failed. Error: {last_error}")

        except Exception as e:
            logger.error(f"Task {task_id}: Attempt {i+1} exception: {e}")
            last_error = str(e)

    if not success:
        logger.error(f"Task {task_id}: All attempts failed")
        update_task_status(task_id, 'failed', error=f"Failed: {last_error}")


def _build_ytdlp_cmd(ua, output_path, has_cookie_file, cookie_file, direct_supported,
                     format_id, referer, domain, cookies, url):
    cmd = ['yt-dlp', '--user-agent', ua, '--no-check-certificate', '--no-playlist', '-o', output_path]

    if has_cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    if direct_supported:
        fmt = f'{format_id}+bestaudio/best' if format_id and format_id != 'best' else 'bestvideo+bestaudio/best'
        cmd.extend(['-f', fmt, '--merge-output-format', 'mp4'])
    else:
        cmd.extend(['--add-header', f'Referer: {referer}', '--add-header', f'Origin: {domain}', '--concurrent-fragments', '4'])
        if format_id and format_id != 'best':
            cmd.extend(['-f', format_id])
        if cookies:
            cmd.extend(['--add-header', f'Cookie: {cookies}'])

    cmd.append(url)
    return cmd
