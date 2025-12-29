import os
import subprocess
import logging
from urllib.parse import urlparse
from core.config import CONFIG, USER_AGENTS

logger = logging.getLogger(__name__)

YOUTUBE_DOMAINS = ['youtube.com', 'youtu.be', 'youtube-nocookie.com']


def is_youtube_url(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in YOUTUBE_DOMAINS)


def download_youtube_video(url, output_path, format_id='best'):
    logger.info(f"YouTube download: {url[:60]} (format: {format_id})")

    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    fmt = f'{format_id}+bestaudio/best' if format_id and format_id != 'best' else 'bestvideo+bestaudio/best'

    cmd = ['yt-dlp', '--no-check-certificate', '--no-playlist',
           '-f', fmt, '--merge-output-format', 'mp4', '-o', output_path, url]

    if has_cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        try:
            run_cmd = cmd.copy()
            run_cmd[1:1] = ['--user-agent', ua]

            logger.info(f"YouTube attempt {i+1}/2")
            process = subprocess.Popen(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = process.communicate()

            if process.returncode == 0:
                logger.info(f"YouTube download completed: {output_path}")
                return {"success": True, "file": output_path}

            last_error = stderr.decode().strip()[-300:]
            logger.warning(f"YouTube attempt {i+1} failed: {last_error}")

        except Exception as e:
            last_error = str(e)
            logger.error(f"YouTube attempt {i+1} exception: {e}")

    return {"success": False, "error": last_error}
