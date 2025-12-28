"""
TikTok Downloader using TikWM API
"""

import re
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TikTokDownloader:
    TIKWM_API = "https://www.tikwm.com/api/"
    
    URL_PATTERNS = [
        r'tiktok\.com/@[\w.-]+/video/(\d+)',
        r'tiktok\.com/t/(\w+)',
        r'vm\.tiktok\.com/(\w+)',
        r'vt\.tiktok\.com/(\w+)',
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
    
    @staticmethod
    def is_tiktok_url(url):
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'])
    
    def get_download_urls(self, url):
        """Get download URLs using TikWM API"""
        result = {
            "success": False,
            "no_watermark": None,
            "watermark": None,
            "audio": None,
            "cover": None,
            "title": None,
            "author": None,
            "duration": None,
            "size": None,
            "size_hd": None,
            "error": None
        }
        
        try:
            logger.info(f"Fetching TikTok video via TikWM: {url[:60]}...")
            
            resp = self.session.post(self.TIKWM_API, data={"url": url, "hd": 1}, timeout=20)
            
            if resp.status_code != 200:
                result["error"] = f"TikWM API returned status {resp.status_code}"
                return result
            
            data = resp.json()
            
            if data.get("code") != 0:
                result["error"] = data.get("msg", "TikWM API error")
                return result
            
            video_data = data.get("data", {})
            
            if not video_data:
                result["error"] = "No video data returned"
                return result
            
            result["no_watermark"] = video_data.get("hdplay") or video_data.get("play")
            result["watermark"] = video_data.get("wmplay")
            result["audio"] = video_data.get("music")
            result["cover"] = video_data.get("cover")
            result["title"] = video_data.get("title", "TikTok Video")
            result["duration"] = video_data.get("duration")
            result["size"] = video_data.get("size")  # size in bytes
            result["size_hd"] = video_data.get("hd_size")  # HD size in bytes
            
            author = video_data.get("author", {})
            if isinstance(author, dict):
                result["author"] = author.get("nickname", author.get("unique_id", "Unknown"))
            else:
                result["author"] = "Unknown"
            
            result["success"] = bool(result["no_watermark"] or result["watermark"])
            
            if result["success"]:
                logger.info(f"TikWM success: {result['title'][:50]}")
            else:
                result["error"] = "No video URL found"
            
            return result
            
        except requests.Timeout:
            result["error"] = "Request timeout"
            return result
        except Exception as e:
            logger.error(f"TikWM API failed: {e}")
            result["error"] = str(e)
            return result


def download_tiktok_video(url, output_path, format_id='tiktok_no_watermark'):
    """Download TikTok video"""
    logger.info(f"TikTok download: {url[:60]} (format: {format_id})")
    
    downloader = TikTokDownloader()
    result = downloader.get_download_urls(url)
    
    if not result["success"]:
        return {"success": False, "error": result.get("error", "Failed to get download URL")}
    
    # Select URL based on format
    if format_id == 'tiktok_audio':
        download_url = result.get("audio")
        if not download_url:
            return {"success": False, "error": "Audio URL not available"}
        if output_path.endswith('.mp4'):
            output_path = output_path[:-4] + '.mp3'
    elif format_id == 'tiktok_watermark':
        download_url = result.get("watermark") or result.get("no_watermark")
    else:
        download_url = result.get("no_watermark") or result.get("watermark")
    
    if not download_url:
        return {"success": False, "error": "No download URL available"}
    
    logger.info(f"Downloading: {download_url[:80]}...")
    
    try:
        resp = requests.get(download_url, stream=True, timeout=120)
        resp.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Download completed: {output_path}")
        return {
            "success": True,
            "file": output_path,
            "title": result.get("title"),
            "author": result.get("author")
        }
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {"success": False, "error": str(e)}
