import subprocess
import logging
from core.config import USER_AGENTS
from core.utils import get_cookie_file

logger = logging.getLogger(__name__)

def download_youtube(url, output_path, format_id='best'):
    logger.info(f"YouTube download: {url[:60]} (format: {format_id})")

    cookie_file = get_cookie_file()
    fmt = f'{format_id}+bestaudio/best' if format_id and format_id != 'best' else 'bestvideo+bestaudio/best'

    base_cmd = ['yt-dlp', '--no-check-certificate', '--no-playlist',
                '-f', fmt, '--merge-output-format', 'mp4', '-o', output_path, url]

    if cookie_file:
        base_cmd[1:1] = ['--cookies', cookie_file]

    last_error = None

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        cmd = base_cmd.copy()
        cmd[1:1] = ['--user-agent', ua]

        logger.info(f"YouTube attempt {i+1}/2")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()

        if process.returncode == 0:
            logger.info(f"YouTube download completed: {output_path}")
            return {"success": True, "file": output_path}

        last_error = stderr.decode().strip()[-300:]
        logger.warning(f"YouTube attempt {i+1} failed: {last_error}")

    return {"success": False, "error": last_error}
