import os
import logging
from typing import Dict, Any, Tuple
import yt_dlp
from core.config import CONFIG
from core.utils import format_size

logger = logging.getLogger(__name__)

PROXY = os.getenv('PROXY', '')


def fetch_instagram_formats(url: str) -> Dict[str, Any]:
    logger.info("Fetching Instagram formats with yt-dlp")
    
    ydl_opts = _get_base_opts()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("Could not fetch video info")

        return _build_format_response(info)

    except Exception as e:
        logger.error(f"Instagram fetch failed: {e}")
        raise Exception("Could not fetch Instagram video. Please check cookies or try again later.")


def _get_base_opts() -> Dict[str, Any]:
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'cookiefile': CONFIG['COOKIE_FILE'],
    }
    
    if PROXY:
        opts['proxy'] = PROXY
    
    return opts


def _build_format_response(info: Dict[str, Any]) -> Dict[str, Any]:
    title = info.get('title', 'Instagram Video')
    if len(title) > 50:
        title = title[:50] + "..."

    duration = info.get('duration', 0)
    formats = info.get('formats', [])
    
    height, filesize_bytes = _extract_best_quality(formats, duration)
    filesize_str = f"~{format_size(filesize_bytes)}" if filesize_bytes else ''
    resolution = f"{height}p (with audio)" if height else "HD (with audio)"

    return {
        'formats': [{
            'format_id': 'instagram_hd',
            'resolution': resolution,
            'height': height,
            'width': int(height * 16 / 9) if height else 1280,
            'ext': 'mp4',
            'filesize': filesize_str,
            'filesize_bytes': filesize_bytes,
            'bitrate': '',
            'has_audio': True
        }],
        'title': title,
        'duration': duration,
        'thumbnail': info.get('thumbnail', '')
    }


def _extract_best_quality(formats: list, duration: int) -> Tuple[int, int]:
    filesize_bytes = 0
    height = 720
    
    for fmt in formats:
        fs = fmt.get('filesize') or fmt.get('filesize_approx')
        if fs and fs > filesize_bytes:
            filesize_bytes = fs
        
        h = fmt.get('height')
        if h and h > height:
            height = h
    
    if not filesize_bytes and duration:
        for fmt in formats:
            tbr = fmt.get('tbr')
            if tbr:
                filesize_bytes = int((tbr * 1000 / 8) * duration)
                break
    
    return height, filesize_bytes


def download_instagram(url: str, output_path: str) -> Dict[str, Any]:
    logger.info(f"Downloading Instagram video: {url}")
    
    if not output_path.endswith('.mp4'):
        output_path = output_path.rsplit('.', 1)[0] + '.mp4'
    
    ydl_opts = {
        **_get_base_opts(),
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_path):
            return {"success": True, "file": output_path}
        return {"success": False, "error": "Download completed but file not found"}
    
    except Exception as e:
        logger.error(f"Instagram download failed: {e}")
        return {"success": False, "error": str(e)}
