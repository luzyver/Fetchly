import os
import json
import subprocess
import logging
from typing import Dict, Any, List, Tuple, Optional
from core.utils import format_size, get_cookie_file

logger = logging.getLogger(__name__)

TWITTER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def fetch_twitter_formats(url: str) -> Dict[str, Any]:
    cookie_file = get_cookie_file()

    cmd = ['yt-dlp', '--no-check-certificate', '--user-agent', TWITTER_USER_AGENT, '-J', url]
    if cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        raise Exception("Request timeout")

    if process.returncode != 0:
        _handle_twitter_error(err.decode().strip()[-200:])

    video_info = json.loads(out.decode())
    entries = video_info.get('entries', [video_info])
    duration = video_info.get('duration', 0)

    formats = _build_twitter_formats(entries, duration)

    return {
        'formats': formats or [_default_twitter_format()],
        'title': video_info.get('title', 'Twitter Video'),
        'duration': duration,
        'video_count': len(entries)
    }


def _handle_twitter_error(error_msg: str) -> None:
    error_lower = error_msg.lower()
    if 'protected' in error_lower:
        raise Exception("This account's tweets are protected")
    if 'not exist' in error_lower or '404' in error_msg:
        raise Exception("Tweet not found or deleted")
    raise Exception(error_msg)


def _build_twitter_formats(entries: List[Dict], default_duration: int) -> List[Dict]:
    formats = []
    
    for idx, entry in enumerate(entries):
        entry_formats = entry.get('formats', [])
        entry_duration = entry.get('duration', default_duration)

        best_height, best_tbr = _find_best_quality(entry_formats)
        estimated_size = _estimate_size(best_tbr, entry_duration)

        formats.append({
            'format_id': f'twitter_{idx}',
            'resolution': f'Video {idx + 1}' + (f' ({best_height}p)' if best_height else ''),
            'height': 10000 - idx,
            'width': 0,
            'ext': 'mp4',
            'filesize': f"~{format_size(estimated_size)}" if estimated_size else '',
            'filesize_bytes': estimated_size,
            'bitrate': '',
            'has_audio': True
        })

    return formats


def _find_best_quality(formats: List[Dict]) -> Tuple[int, int]:
    best_height = 0
    best_tbr = 0
    
    for fmt in formats:
        height = fmt.get('height', 0)
        vcodec = fmt.get('vcodec', 'none')
        
        if vcodec != 'none' and height and height > best_height:
            best_height = height
            best_tbr = fmt.get('tbr', 0)
    
    return best_height, best_tbr


def _estimate_size(tbr: int, duration: int) -> int:
    if tbr and duration:
        return int((tbr * 1000 / 8) * duration)
    return 0


def _default_twitter_format() -> Dict:
    return {
        'format_id': 'twitter_0', 'resolution': 'Video 1', 'height': 10000, 'width': 0,
        'ext': 'mp4', 'filesize': '', 'filesize_bytes': 0, 'bitrate': '', 'has_audio': True
    }


def download_twitter(url: str, output_path: str, format_id: str = 'twitter_0',
                     max_size: Optional[int] = None) -> Dict[str, Any]:
    logger.info(f"Twitter download: {url[:60]} (format: {format_id})")

    video_index = int(format_id.replace('twitter_', '')) if format_id.startswith('twitter_') else 0
    cookie_file = get_cookie_file()
    
    if max_size is None:
        max_size = CONFIG['MAX_FILE_SIZE']

    cmd = ['yt-dlp', '--no-check-certificate', '--user-agent', TWITTER_USER_AGENT,
           '-f', 'bestvideo+bestaudio/best', '--merge-output-format', 'mp4',
           '--playlist-items', str(video_index + 1), '-o', output_path, url]

    if cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    logger.info(f"Downloading Twitter video {video_index + 1}")

    result = _run_with_size_monitor(cmd, output_path, max_size)
    
    if result['success']:
        logger.info(f"Twitter download completed: {output_path}")
    elif result.get('size_exceeded'):
        logger.warning(f"Twitter download cancelled: size exceeded")
    else:
        logger.error(f"Twitter download failed: {result.get('error')}")
    
    return result


def _run_with_size_monitor(cmd: list, output_path: str, max_size: Optional[int]) -> Dict[str, Any]:
    import time
    import glob
    import threading
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if max_size is None:
        try:
            _, stderr = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            return {"success": False, "error": "Download timeout"}
        if process.returncode == 0 and os.path.exists(output_path):
            return {"success": True, "file": output_path}
        return {"success": False, "error": stderr.decode().strip()[-300:] if stderr else "Download failed"}
    
    size_exceeded = [False]
    monitor_stop = threading.Event()
    
    def monitor():
        base_path = output_path.rsplit('.', 1)[0]
        while not monitor_stop.is_set():
            current_size = _get_download_size(base_path)
            if current_size > max_size:
                size_exceeded[0] = True
                logger.warning(f"Size limit exceeded: {current_size} > {max_size}, killing process")
                process.kill()
                break
            time.sleep(1)
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    
    try:
        _, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        process.kill()
        monitor_stop.set()
        return {"success": False, "error": "Download timeout"}
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=2)
    
    if size_exceeded[0]:
        _cleanup_partial(output_path)
        return {"success": False, "error": "Download cancelled: file size exceeded limit", "size_exceeded": True}
    
    if process.returncode == 0 and os.path.exists(output_path):
        return {"success": True, "file": output_path}
    
    return {"success": False, "error": stderr.decode().strip()[-300:] if stderr else "Download failed"}


def _get_download_size(base_path: str) -> int:
    import glob
    total = 0
    for pattern in [f"{base_path}*", f"{base_path}.*"]:
        for filepath in glob.glob(pattern):
            try:
                total += os.path.getsize(filepath)
            except OSError:
                pass
    return total


def _cleanup_partial(output_path: str) -> None:
    import glob
    base_path = output_path.rsplit('.', 1)[0]
    for pattern in [f"{base_path}*", f"{output_path}*"]:
        for filepath in glob.glob(pattern):
            try:
                os.remove(filepath)
                logger.info(f"Cleaned up: {filepath}")
            except OSError:
                pass
