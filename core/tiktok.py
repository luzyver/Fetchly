import re
import json
import logging
import requests
from urllib.parse import urlparse, parse_qs, urlencode

logger = logging.getLogger(__name__)

class TikTokDownloader:
    API_DOMAIN = "https://api16-normal-c-useast1a.tiktokv.com"
    
    HEADERS = {
        "User-Agent": "com.zhiliaoapp.musically/2023501030 (Linux; U; Android 12; en_US; Pixel 6; Build/SD1A.210817.023; Cronet/TTNetVersion:b4d74d15 2023-04-21 QuicVersion:0144d358 2023-03-10)",
        "Accept": "application/json",
    }
    
    URL_PATTERNS = [
        r'tiktok\.com/@[\w.-]+/video/(\d+)',
        r'tiktok\.com/t/(\w+)',
        r'vm\.tiktok\.com/(\w+)',
        r'vt\.tiktok\.com/(\w+)',
    ]
    
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
    
    @staticmethod
    def is_tiktok_url(url):
        parsed = urlparse(url)
        return any(domain in parsed.netloc for domain in ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'])
    
    def _resolve_short_url(self, url):
        try:
            resp = self.session.head(url, allow_redirects=True, timeout=10)
            return resp.url
        except Exception as e:
            logger.error(f"Failed to resolve short URL: {e}")
            return url
    
    def _extract_video_id(self, url):
        if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url or '/t/' in url:
            url = self._resolve_short_url(url)
        
        for pattern in self.URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                if video_id.isdigit():
                    return video_id
        
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1)
        
        raise ValueError(f"Cannot extract video ID from URL: {url}")
    
    def _get_video_info_api(self, video_id):
        api_url = f"{self.API_DOMAIN}/aweme/v1/feed/"
        
        params = {
            "aweme_id": video_id,
            "version_code": "2023501030",
            "app_name": "musical_ly",
            "device_platform": "android",
            "device_type": "Pixel 6",
            "os_version": "12",
        }
        
        try:
            resp = self.session.get(api_url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("aweme_list"):
                return data["aweme_list"][0]
            return None
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def _get_video_info_web(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            
            patterns = [
                r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([^<]+)</script>',
                r'<script id="SIGI_STATE"[^>]*>([^<]+)</script>',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, resp.text)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        return self._parse_web_data(data)
                    except json.JSONDecodeError:
                        continue
            
            return None
        except Exception as e:
            logger.error(f"Web scraping failed: {e}")
            return None
    
    def _parse_web_data(self, data):
        try:
            if "__DEFAULT_SCOPE__" in data:
                video_detail = data["__DEFAULT_SCOPE__"].get("webapp.video-detail", {})
                item_info = video_detail.get("itemInfo", {}).get("itemStruct", {})
                if item_info:
                    return item_info
            
            if "ItemModule" in data:
                items = data["ItemModule"]
                if items:
                    return list(items.values())[0]
            
            return None
        except Exception as e:
            logger.error(f"Failed to parse web data: {e}")
            return None
    
    def get_download_urls(self, url):
        result = {
            "success": False,
            "no_watermark": None,
            "watermark": None,
            "audio": None,
            "cover": None,
            "title": None,
            "author": None,
            "error": None
        }
        
        try:
            video_id = self._extract_video_id(url)
            logger.info(f"Extracted video ID: {video_id}")
            
            video_info = self._get_video_info_api(video_id)
            
            if video_info:
                result = self._extract_urls_from_api(video_info)
            else:
                logger.info("API failed, trying web scraping...")
                video_info = self._get_video_info_web(url)
                if video_info:
                    result = self._extract_urls_from_web(video_info)
                else:
                    result["error"] = "Failed to get video info from both API and web"
            
            return result
            
        except Exception as e:
            logger.error(f"TikTok download failed: {e}")
            result["error"] = str(e)
            return result
    
    def _extract_urls_from_api(self, video_info):
        result = {
            "success": False,
            "no_watermark": None,
            "watermark": None,
            "audio": None,
            "cover": None,
            "title": None,
            "author": None,
            "error": None
        }
        
        try:
            video = video_info.get("video", {})
            play_addr = video.get("play_addr", {})
            url_list = play_addr.get("url_list", [])
            if url_list:
                result["no_watermark"] = url_list[0]
            
            download_addr = video.get("download_addr", {})
            download_list = download_addr.get("url_list", [])
            if download_list:
                result["watermark"] = download_list[0]
            
            music = video_info.get("music", {})
            play_url = music.get("play_url", {})
            music_urls = play_url.get("url_list", [])
            if music_urls:
                result["audio"] = music_urls[0]
            
            cover = video.get("cover", {})
            cover_urls = cover.get("url_list", [])
            if cover_urls:
                result["cover"] = cover_urls[0]
            
            result["title"] = video_info.get("desc", "TikTok Video")
            author = video_info.get("author", {})
            result["author"] = author.get("nickname", author.get("unique_id", "Unknown"))
            
            result["success"] = bool(result["no_watermark"] or result["watermark"])
            
        except Exception as e:
            logger.error(f"Failed to extract URLs from API: {e}")
            result["error"] = str(e)
        
        return result
    
    def _extract_urls_from_web(self, video_info):
        result = {
            "success": False,
            "no_watermark": None,
            "watermark": None,
            "audio": None,
            "cover": None,
            "title": None,
            "author": None,
            "error": None
        }
        
        try:
            video = video_info.get("video", {})
            
            play_addr = video.get("playAddr")
            if isinstance(play_addr, str):
                result["no_watermark"] = play_addr
            elif isinstance(play_addr, dict):
                result["no_watermark"] = play_addr.get("src") or play_addr.get("url")
            
            download_addr = video.get("downloadAddr")
            if isinstance(download_addr, str):
                result["watermark"] = download_addr
            elif isinstance(download_addr, dict):
                result["watermark"] = download_addr.get("src") or download_addr.get("url")
            
            music = video_info.get("music", {})
            result["audio"] = music.get("playUrl")
            
            result["cover"] = video.get("cover") or video.get("originCover")
            
            result["title"] = video_info.get("desc", "TikTok Video")
            result["author"] = video_info.get("author", {}).get("nickname", "Unknown")
            
            result["success"] = bool(result["no_watermark"] or result["watermark"])
            
        except Exception as e:
            logger.error(f"Failed to extract URLs from web: {e}")
            result["error"] = str(e)
        
        return result


def download_tiktok_video(url, output_path, no_watermark=True):
    downloader = TikTokDownloader()
    result = downloader.get_download_urls(url)
    
    if not result["success"]:
        return {"success": False, "error": result.get("error", "Failed to get download URL")}
    
    video_url = result["no_watermark"] if no_watermark and result["no_watermark"] else result["watermark"]
    
    if not video_url:
        return {"success": False, "error": "No video URL available"}
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        }
        
        resp = requests.get(video_url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return {
            "success": True,
            "file": output_path,
            "title": result.get("title"),
            "author": result.get("author")
        }
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {"success": False, "error": str(e)}