import json
import subprocess
import logging
from core.utils import format_size, get_cookie_file

logger = logging.getLogger(__name__)

TWITTER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def fetch_twitter_formats(url):
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
        error_msg = err.decode().strip()[-200:]
        if 'protected' in error_msg.lower():
            raise Exception("This account's tweets are protected")
        if 'not exist' in error_msg.lower() or '404' in error_msg:
            raise Exception("Tweet not found or deleted")
        raise Exception(error_msg)

    video_info = json.loads(out.decode())
    entries = video_info.get('entries', [video_info])

    formats = []
    for idx, entry in enumerate(entries):
        entry_formats = entry.get('formats', [])

        best_height = 0
        best_size = None
        for fmt in entry_formats:
            height = fmt.get('height', 0)
            if height and height > best_height:
                best_height = height
                best_size = fmt.get('filesize') or fmt.get('filesize_approx')

        formats.append({
            'format_id': f'twitter_{idx}',
            'resolution': f'Video {idx + 1}' + (f' ({best_height}p)' if best_height else ''),
            'height': 10000 - idx,
            'width': 0,
            'ext': 'mp4',
            'filesize': format_size(best_size) if best_size else '',
            'bitrate': '',
            'has_audio': True
        })

    return {
        'formats': formats or [{'format_id': 'best', 'resolution': 'Best Quality', 'height': 9999, 'width': 0, 'ext': 'mp4', 'filesize': '', 'bitrate': '', 'has_audio': True}],
        'title': video_info.get('title', 'Twitter Video'),
        'duration': video_info.get('duration'),
        'video_count': len(entries)
    }


def download_twitter(url, output_path, format_id='twitter_0'):
    logger.info(f"Twitter download: {url[:60]} (format: {format_id})")

    video_index = int(format_id.replace('twitter_', '')) if format_id.startswith('twitter_') else 0
    cookie_file = get_cookie_file()

    cmd = ['yt-dlp', '--no-check-certificate', '--user-agent', TWITTER_USER_AGENT,
           '-f', 'bestvideo+bestaudio/best', '--merge-output-format', 'mp4',
           '--playlist-items', str(video_index + 1), '-o', output_path, url]

    if cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    logger.info(f"Downloading Twitter video {video_index + 1}")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        process.kill()
        return {"success": False, "error": "Download timeout"}

    if process.returncode == 0:
        logger.info(f"Twitter download completed: {output_path}")
        return {"success": True, "file": output_path}

    error = stderr.decode().strip()[-300:]
    logger.error(f"Twitter download failed: {error}")
    return {"success": False, "error": error}
