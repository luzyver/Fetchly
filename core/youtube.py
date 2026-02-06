import logging
from typing import Dict, Any, Optional
from core.config import USER_AGENTS
from core.utils import get_cookie_file, run_with_size_monitor

logger = logging.getLogger(__name__)


def download_youtube(url: str, output_path: str, format_id: str = 'best',
                     max_size: Optional[int] = None) -> Dict[str, Any]:
    logger.info(f"YouTube download: {url[:60]} (format: {format_id})")

    cookie_file = get_cookie_file()
    fmt = _build_format_string(format_id)
    


    base_cmd = ['yt-dlp', '--no-check-certificate', '--no-playlist',
                '-f', fmt, '--merge-output-format', 'mp4', '--recode-video', 'mp4', '-o', output_path, url]

    if cookie_file:
        base_cmd[1:1] = ['--cookies', cookie_file]

    last_error = None

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        cmd = base_cmd.copy()
        cmd[1:1] = ['--user-agent', ua]

        logger.info(f"YouTube attempt {i+1}/2")
        
        result = run_with_size_monitor(cmd, output_path, max_size, logger=logger)
        
        if result['success']:
            logger.info(f"YouTube download completed: {output_path}")
            return result
        
        if result.get('size_exceeded'):
            return result
            
        last_error = result.get('error', 'Unknown error')
        logger.warning(f"YouTube attempt {i+1} failed: {last_error}")

    return {"success": False, "error": last_error}


def _build_format_string(format_id: Optional[str]) -> str:
    if format_id and format_id != 'best':
        return f'{format_id}+bestaudio/{format_id}'
    return 'bestvideo+bestaudio/best'
