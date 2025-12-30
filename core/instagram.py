import os
import re
import logging
import requests
import yt_dlp
from core.config import CONFIG

logger = logging.getLogger(__name__)

PROXY = os.getenv('PROXY', '')


def _get_proxy():
    if PROXY:
        return {'http': PROXY, 'https': PROXY}
    return None


def _fetch_with_ytdlp(url):
    logger.info("Fetching Instagram with yt-dlp")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'cookiefile': CONFIG['COOKIE_FILE'],
    }
    
    if PROXY:
        ydl_opts['proxy'] = PROXY

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise Exception("Could not fetch video info")

    title = info.get('title', 'Instagram Video')
    if len(title) > 50:
        title = title[:50] + "..."
    
    video_url = info.get('url')
    if not video_url and info.get('formats'):
        for fmt in reversed(info['formats']):
            if fmt.get('url') and fmt.get('vcodec') != 'none':
                video_url = fmt['url']
                break

    if not video_url:
        raise Exception("Could not find video URL")

    return {
        'title': title,
        'duration': info.get('duration'),
        'video_url': video_url
    }


def fetch_instagram_formats(url):
    try:
        info = _fetch_with_ytdlp(url)
        logger.info("Successfully fetched Instagram video")
    except Exception as e:
        logger.error(f"Instagram fetch failed: {e}")
        raise Exception("Could not download Instagram video. Please check cookies or try again later.")

    return {
        'formats': [{
            'format_id': 'best',
            'resolution': 'Best Quality',
            'height': 9999,
            'width': 0,
            'ext': 'mp4',
            'filesize': '',
            'filesize_bytes': 0,
            'bitrate': '',
            'has_audio': True
        }],
        'title': info['title'],
        'duration': info['duration'],
        'video_url': info['video_url'],
        'thumbnail': ''
    }


def download_instagram(url, output_path):
    try:
        info = fetch_instagram_formats(url)
        video_url = info['video_url']

        response = requests.get(
            video_url, 
            stream=True, 
            timeout=60, 
            proxies=_get_proxy(),
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return {"success": True, "file": output_path}
    except Exception as e:
        logger.error(f"Instagram download failed: {e}")
        return {"success": False, "error": str(e)}
