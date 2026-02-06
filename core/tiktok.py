import os
import logging
from typing import Dict, Any, Optional, Tuple
import requests
import threading
from core.utils import format_size

logger = logging.getLogger(__name__)

TIKWM_API = "https://www.tikwm.com/api/"
_session_lock = threading.Lock()
_session: requests.Session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                session = requests.Session()
                session.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                })
                _session = session
    return _session


def fetch_tiktok_info(url: str) -> Dict[str, Any]:
    session = _get_session()

    logger.info(f"Fetching TikTok: {url[:60]}...")
    resp = session.post(TIKWM_API, data={"url": url, "hd": 1}, timeout=20)

    if resp.status_code != 200:
        raise Exception(f"TikWM API returned status {resp.status_code}")

    data = resp.json()
    if data.get("code") != 0:
        raise Exception(data.get("msg", "TikWM API error"))

    video_data = data.get("data", {})
    if not video_data:
        raise Exception("No video data returned")

    author = video_data.get("author", {})
    author_name = author.get("nickname", author.get("unique_id", "Unknown")) if isinstance(author, dict) else "Unknown"

    return {
        "no_watermark": video_data.get("hdplay") or video_data.get("play"),
        "watermark": video_data.get("wmplay"),
        "audio": video_data.get("music"),
        "cover": video_data.get("cover"),
        "title": video_data.get("title", "TikTok Video"),
        "author": author_name,
        "duration": video_data.get("duration"),
        "size": video_data.get("size"),
        "size_hd": video_data.get("hd_size"),
    }


def fetch_tiktok_formats(url: str) -> Dict[str, Any]:
    info = fetch_tiktok_info(url)
    hd_size_bytes = info.get('size_hd') or info.get('size') or 0
    hd_size = format_size(hd_size_bytes)

    return {
        'formats': [
            {'format_id': 'tiktok_no_watermark', 'resolution': 'No Watermark (HD)', 'height': 9999, 'width': 0, 'ext': 'mp4', 'filesize': hd_size, 'filesize_bytes': hd_size_bytes, 'bitrate': '', 'has_audio': True},
            {'format_id': 'tiktok_watermark', 'resolution': 'With Watermark', 'height': 9998, 'width': 0, 'ext': 'mp4', 'filesize': hd_size, 'filesize_bytes': hd_size_bytes, 'bitrate': '', 'has_audio': True},
            {'format_id': 'tiktok_audio', 'resolution': 'Audio Only', 'height': 0, 'width': 0, 'ext': 'mp3', 'filesize': '', 'filesize_bytes': 0, 'bitrate': '', 'has_audio': True}
        ],
        'title': info.get('title') or 'TikTok Video',
        'duration': info.get('duration'),
    }


def download_tiktok(url: str, output_path: str, format_id: str = 'tiktok_no_watermark',
                    max_size: Optional[int] = None) -> Dict[str, Any]:
    logger.info(f"TikTok download: {url[:60]} (format: {format_id})")

    try:
        info = fetch_tiktok_info(url)
        download_url, output_path = _get_download_url(info, format_id, output_path)

        if not download_url:
            return {"success": False, "error": "No download URL available"}

        logger.info(f"Downloading: {download_url[:80]}...")
        result = _download_file(download_url, output_path, max_size)

        if result['success']:
            logger.info(f"Download completed: {output_path}")
        
        return result

    except Exception as e:
        logger.error(f"TikTok download failed: {e}")
        return {"success": False, "error": str(e)}


def _get_download_url(info: Dict[str, Any], format_id: str, output_path: str) -> Tuple[Optional[str], str]:
    if format_id == 'tiktok_audio':
        download_url = info.get("audio")
        if output_path.endswith('.mp4'):
            output_path = output_path[:-4] + '.mp3'
    elif format_id == 'tiktok_watermark':
        download_url = info.get("watermark") or info.get("no_watermark")
    else:
        download_url = info.get("no_watermark") or info.get("watermark")

    return download_url, output_path


def _download_file(url: str, output_path: str, max_size: Optional[int]) -> Dict[str, Any]:
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    
    downloaded = 0

    try:
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    downloaded += len(chunk)
                    if max_size is not None and downloaded > max_size:
                        logger.warning(f"Size limit exceeded: {downloaded} > {max_size}")
                        f.close()
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        return {"success": False, "error": "Download cancelled: file size exceeded limit", "size_exceeded": True, "downloaded_size": downloaded}
                    f.write(chunk)
        
        return {"success": True, "file": output_path}
    except Exception as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise e
