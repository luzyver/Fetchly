import os
import glob
import time
import subprocess
import logging
import threading
from typing import Dict, Any, Optional
from core.config import CONFIG, USER_AGENTS
from core.utils import get_cookie_file

logger = logging.getLogger(__name__)


def download_youtube(url: str, output_path: str, format_id: str = 'best',
                     max_size: Optional[int] = None) -> Dict[str, Any]:
    logger.info(f"YouTube download: {url[:60]} (format: {format_id})")

    cookie_file = get_cookie_file()
    fmt = _build_format_string(format_id)
    


    base_cmd = ['yt-dlp', '--no-check-certificate', '--no-playlist',
                '-f', fmt, '--merge-output-format', 'mp4', '-o', output_path, url]

    if cookie_file:
        base_cmd[1:1] = ['--cookies', cookie_file]

    last_error = None

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        cmd = base_cmd.copy()
        cmd[1:1] = ['--user-agent', ua]

        logger.info(f"YouTube attempt {i+1}/2")
        
        result = _run_with_size_monitor(cmd, output_path, max_size)
        
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


def _run_with_size_monitor(cmd: list, output_path: str, max_size: Optional[int]) -> Dict[str, Any]:
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if max_size is None:
        _, stderr = process.communicate()
        if process.returncode == 0 and os.path.exists(output_path):
            return {"success": True, "file": output_path}
        return {"success": False, "error": stderr.decode().strip()[-300:] if stderr else "Download failed"}
    
    size_exceeded = [False]
    final_size = [0]
    monitor_stop = threading.Event()
    
    def monitor():
        base_path = output_path.rsplit('.', 1)[0]
        while not monitor_stop.is_set():
            current_size = _get_download_size(base_path)
            final_size[0] = current_size
            if current_size > max_size:
                size_exceeded[0] = True
                logger.warning(f"Size limit exceeded: {current_size} > {max_size}, killing process")
                process.kill()
                break
            time.sleep(1)
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    
    try:
        _, stderr = process.communicate()
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=2)
    
    if size_exceeded[0]:
        _cleanup_partial(output_path)
        return {
            "success": False, 
            "error": "Download cancelled: file size exceeded limit",
            "size_exceeded": True,
            "downloaded_size": final_size[0]
        }
    
    if process.returncode == 0 and os.path.exists(output_path):
        return {"success": True, "file": output_path}
    
    return {"success": False, "error": stderr.decode().strip()[-300:] if stderr else "Download failed"}


def _get_download_size(base_path: str) -> int:
    output_mp4 = f"{base_path}.mp4"
    
    if os.path.exists(output_mp4):
        try:
            return os.path.getsize(output_mp4)
        except OSError:
            pass
    
    return 0


def _cleanup_partial(output_path: str) -> None:
    base_path = output_path.rsplit('.', 1)[0]
    
    for pattern in [f"{base_path}*", f"{output_path}*"]:
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
                logger.info(f"Cleaned up: {filepath}")
            except OSError:
                pass
