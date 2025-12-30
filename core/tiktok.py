import logging
import requests
from core.utils import format_size

logger = logging.getLogger(__name__)

TIKWM_API = "https://www.tikwm.com/api/"


def fetch_tiktok_info(url):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    })

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


def fetch_tiktok_formats(url):
    info = fetch_tiktok_info(url)
    hd_size = format_size(info.get('size_hd') or info.get('size'))
    hd_size_bytes = info.get('size_hd') or info.get('size') or 0

    return {
        'formats': [
            {'format_id': 'tiktok_no_watermark', 'resolution': 'No Watermark (HD)', 'height': 9999, 'width': 0, 'ext': 'mp4', 'filesize': hd_size, 'filesize_bytes': hd_size_bytes, 'bitrate': '', 'has_audio': True},
            {'format_id': 'tiktok_watermark', 'resolution': 'With Watermark', 'height': 9998, 'width': 0, 'ext': 'mp4', 'filesize': hd_size, 'filesize_bytes': hd_size_bytes, 'bitrate': '', 'has_audio': True},
            {'format_id': 'tiktok_audio', 'resolution': 'Audio Only', 'height': 0, 'width': 0, 'ext': 'mp3', 'filesize': '', 'filesize_bytes': 0, 'bitrate': '', 'has_audio': True}
        ],
        'title': info.get('title') or 'TikTok Video',
        'duration': info.get('duration'),
    }


def download_tiktok(url, output_path, format_id='tiktok_no_watermark'):
    logger.info(f"TikTok download: {url[:60]} (format: {format_id})")

    try:
        info = fetch_tiktok_info(url)

        if format_id == 'tiktok_audio':
            download_url = info.get("audio")
            if not download_url:
                return {"success": False, "error": "Audio URL not available"}
            if output_path.endswith('.mp4'):
                output_path = output_path[:-4] + '.mp3'
        elif format_id == 'tiktok_watermark':
            download_url = info.get("watermark") or info.get("no_watermark")
        else:
            download_url = info.get("no_watermark") or info.get("watermark")

        if not download_url:
            return {"success": False, "error": "No download URL available"}

        logger.info(f"Downloading: {download_url[:80]}...")

        resp = requests.get(download_url, stream=True, timeout=120)
        resp.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Download completed: {output_path}")
        return {"success": True, "file": output_path}

    except Exception as e:
        logger.error(f"TikTok download failed: {e}")
        return {"success": False, "error": str(e)}
