import os
import json
import subprocess
import logging
from urllib.parse import urlparse
from core.config import CONFIG, USER_AGENTS

logger = logging.getLogger(__name__)

TWITTER_DOMAINS = ['twitter.com', 'x.com']


def is_twitter_url(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in TWITTER_DOMAINS)


def fetch_twitter_formats(url):
    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    cmd = ['yt-dlp', '--no-check-certificate', '-J', url]
    if has_cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate(timeout=30)

    if process.returncode != 0:
        raise Exception(err.decode().strip()[-200:])

    video_info = json.loads(out.decode())
    entries = video_info.get('entries', [video_info])

    formats = []
    for idx, entry in enumerate(entries):
        video_num = idx + 1
        entry_formats = entry.get('formats', [])

        best_height = 0
        best_format = None
        for fmt in entry_formats:
            height = fmt.get('height', 0)
            if height and height > best_height:
                best_height = height
                best_format = fmt

        filesize = ''
        if best_format:
            size = best_format.get('filesize') or best_format.get('filesize_approx')
            if size:
                if size > 1024 * 1024:
                    filesize = f"{size / (1024*1024):.1f} MB"
                elif size > 1024:
                    filesize = f"{size / 1024:.1f} KB"

        formats.append({
            'format_id': f'twitter_{idx}',
            'resolution': f'Video {video_num}' + (f' ({best_height}p)' if best_height else ''),
            'height': 10000 - idx,
            'width': 0,
            'ext': 'mp4',
            'filesize': filesize,
            'bitrate': '',
            'has_audio': True
        })

    return {
        'formats': formats or [{'format_id': 'best', 'resolution': 'Best Quality', 'height': 9999, 'width': 0, 'ext': 'mp4', 'filesize': '', 'bitrate': '', 'has_audio': True}],
        'title': video_info.get('title', 'Twitter Video'),
        'duration': video_info.get('duration'),
        'video_count': len(entries)
    }


def download_twitter_video(url, output_path, format_id='twitter_0'):
    logger.info(f"Twitter download: {url[:60]} (format: {format_id})")

    video_index = int(format_id.replace('twitter_', '')) if format_id.startswith('twitter_') else 0

    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    cmd = ['yt-dlp', '--no-check-certificate', '-f', 'bestvideo+bestaudio/best',
           '--merge-output-format', 'mp4', '--playlist-items', str(video_index + 1),
           '-o', output_path, url]

    if has_cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    logger.info(f"Downloading Twitter video {video_index + 1}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, stderr = process.communicate()

    if process.returncode == 0:
        logger.info(f"Twitter download completed: {output_path}")
        return {"success": True, "file": output_path}
    else:
        error = stderr.decode().strip()[-300:]
        logger.error(f"Twitter download failed: {error}")
        return {"success": False, "error": error}
