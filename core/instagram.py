import os
import logging
import yt_dlp
from core.config import CONFIG

logger = logging.getLogger(__name__)

PROXY = os.getenv('PROXY', '')

def fetch_instagram_formats(url):
    logger.info("Fetching Instagram formats with yt-dlp")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'cookiefile': CONFIG['COOKIE_FILE'],
    }
    
    if PROXY:
        ydl_opts['proxy'] = PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("Could not fetch video info")

        title = info.get('title', 'Instagram Video')
        if len(title) > 50:
            title = title[:50] + "..."

        return {
            'formats': [{
                'format_id': 'instagram_hd',
                'resolution': 'HD (with audio)',
                'height': 720,
                'width': 1280,
                'ext': 'mp4',
                'filesize': '',
                'filesize_bytes': 0,
                'bitrate': '',
                'has_audio': True
            }],
            'title': title,
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail', '')
        }
    except Exception as e:
        logger.error(f"Instagram fetch failed: {e}")
        raise Exception("Could not fetch Instagram video. Please check cookies or try again later.")

def download_instagram(url, output_path):
    logger.info(f"Downloading Instagram video: {url}")
    
    if not output_path.endswith('.mp4'):
        output_path = output_path.rsplit('.', 1)[0] + '.mp4'
    
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': CONFIG['COOKIE_FILE'],
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    
    if PROXY:
        ydl_opts['proxy'] = PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_path):
            return {"success": True, "file": output_path}
        else:
            return {"success": False, "error": "Download completed but file not found"}
    except Exception as e:
        logger.error(f"Instagram download failed: {e}")
        return {"success": False, "error": str(e)}
