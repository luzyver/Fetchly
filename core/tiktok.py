"""
TikTok Downloader with Cookie Support
For videos that require login (age-restricted, private, region-locked)
"""

import os
import re
import json
import logging
import requests
from http.cookiejar import MozillaCookieJar
from urllib.parse import urlparse
from core.config import CONFIG

logger = logging.getLogger(__name__)


def load_cookies_from_file(cookie_file):
    """Load cookies from Netscape format cookie file"""
    cookies = {}
    if not cookie_file or not os.path.exists(cookie_file):
        return cookies
    
    try:
        jar = MozillaCookieJar(cookie_file)
        jar.load(ignore_discard=True, ignore_expires=True)
        for cookie in jar:
            if 'tiktok' in cookie.domain:
                cookies[cookie.name] = cookie.value
        logger.info(f"Loaded {len(cookies)} TikTok cookies from {cookie_file}")
    except Exception as e:
        logger.warning(f"Failed to load cookies: {e}")
    
    return cookies


class TikTokDownloader:
    API_ENDPOINTS = [
        "https://api22-normal-c-useast2a.tiktokv.com/aweme/v1/feed/",
        "https://api16-normal-c-useast1a.tiktokv.com/aweme/v1/feed/",
        "https://api19-normal-c-useast1a.tiktokv.com/aweme/v1/feed/",
    ]
    
    URL_PATTERNS = [
        r'tiktok\.com/@[\w.-]+/video/(\d+)',
        r'tiktok\.com/t/(\w+)',
        r'vm\.tiktok\.com/(\w+)',
        r'vt\.tiktok\.com/(\w+)',
    ]
    
    def __init__(self, cookie_file=None):
        self.session = requests.Session()
        
        # Load cookies
        cf = cookie_file or CONFIG.get('TIKTOK_COOKIE_FILE')
        self.cookies = load_cookies_from_file(cf)
        
        # Set headers
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
        })
        
        if self.cookies:
            self.session.cookies.update(self.cookies)
    
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
                    return video_id, url
        
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1), url
        
        raise ValueError(f"Cannot extract video ID from URL: {url}")

    def _get_video_info_api(self, video_id):
        """Try multiple API endpoints"""
        params = {
            "aweme_id": video_id,
            "version_code": "300904",
            "device_platform": "android",
            "device_type": "Pixel 6",
            "os_version": "12",
            "app_name": "trill",
            "region": "US",
            "language": "en",
            "aid": "1180",
        }
        
        headers = {
            "User-Agent": "com.ss.android.ugc.trill/300904 (Linux; U; Android 12; en_US; Pixel 6; Build/SD1A.210817.023)",
            "Accept": "application/json",
        }
        
        for api_url in self.API_ENDPOINTS:
            try:
                logger.info(f"Trying API: {api_url}")
                resp = requests.get(api_url, params=params, headers=headers, timeout=15)
                
                if resp.status_code == 200 and resp.text.strip():
                    data = resp.json()
                    if data.get("aweme_list"):
                        logger.info("API request successful")
                        return data["aweme_list"][0]
            except Exception as e:
                logger.warning(f"API {api_url} failed: {e}")
                continue
        
        return None
    
    def _get_video_info_tikwm(self, url):
        """Use tikwm.com API as fallback - more reliable for blocked regions"""
        try:
            api_url = "https://www.tikwm.com/api/"
            
            resp = requests.post(api_url, data={"url": url, "hd": 1}, timeout=15)
            
            if resp.status_code != 200:
                logger.warning(f"TikWM API failed with status {resp.status_code}")
                return None
            
            data = resp.json()
            
            if data.get("code") != 0:
                logger.warning(f"TikWM API error: {data.get('msg')}")
                return None
            
            video_data = data.get("data", {})
            
            return {
                "no_watermark": video_data.get("play") or video_data.get("hdplay"),
                "watermark": video_data.get("wmplay"),
                "audio": video_data.get("music"),
                "cover": video_data.get("cover"),
                "title": video_data.get("title", "TikTok Video"),
                "author": video_data.get("author", {}).get("nickname", "Unknown"),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"TikWM API failed: {e}")
            return None

    def _get_video_info_web(self, url):
        """Scrape video info from web page (with cookies for login-required videos)"""
        try:
            logger.info(f"Trying web scraping: {url[:80]}...")
            
            resp = self.session.get(url, timeout=15, allow_redirects=True)
            
            logger.info(f"Web response status: {resp.status_code}, URL: {resp.url[:80]}")
            
            if resp.status_code != 200:
                logger.warning(f"Web request failed with status {resp.status_code}")
                return None
            
            # Check if login required or redirected
            if 'login' in resp.url.lower() or 'LoginModal' in resp.text:
                logger.warning("Video requires login - cookies may be invalid or expired")
            
            # Log page content length for debug
            logger.info(f"Page content length: {len(resp.text)} chars")
            
            patterns = [
                r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([^<]+)</script>',
                r'<script id="SIGI_STATE"[^>]*>([^<]+)</script>',
                r'"webapp\.video-detail":\s*(\{.+?\})\s*,\s*"webapp\.',
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, resp.text)
                if match:
                    logger.info(f"Pattern {i+1} matched")
                    try:
                        data = json.loads(match.group(1))
                        result = self._parse_web_data(data)
                        if result:
                            logger.info("Successfully parsed web data")
                            return result
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode failed for pattern {i+1}: {e}")
                        continue
            
            logger.warning("No patterns matched in page")
            
            # Try to find video URL directly
            video_urls = re.findall(r'(https://[^"\'\\]+(?:tiktok|bytedance)[^"\'\\]+\.mp4[^"\'\\]*)', resp.text)
            if video_urls:
                clean_url = video_urls[0].replace('\\u002F', '/').replace('\\u0026', '&')
                logger.info(f"Found direct video URL: {clean_url[:80]}...")
                return {"direct_url": clean_url}
            
            logger.warning("No video URLs found in page")
            return None
        except Exception as e:
            logger.error(f"Web scraping failed: {e}")
            return None
    
    def _parse_web_data(self, data):
        try:
            # __UNIVERSAL_DATA_FOR_REHYDRATION__ format
            if "__DEFAULT_SCOPE__" in data:
                video_detail = data["__DEFAULT_SCOPE__"].get("webapp.video-detail", {})
                item_info = video_detail.get("itemInfo", {}).get("itemStruct", {})
                if item_info:
                    return item_info
            
            # SIGI_STATE format
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
            video_id, resolved_url = self._extract_video_id(url)
            logger.info(f"Extracted video ID: {video_id}")
            
            # Try API first
            video_info = self._get_video_info_api(video_id)
            
            if video_info:
                result = self._extract_urls_from_api(video_info)
            
            # Fallback to web scraping (uses cookies)
            if not result["success"]:
                logger.info("API failed, trying web scraping with cookies...")
                video_info = self._get_video_info_web(resolved_url)
                
                if video_info:
                    if "direct_url" in video_info:
                        result["no_watermark"] = video_info["direct_url"]
                        result["success"] = True
                        result["title"] = "TikTok Video"
                    else:
                        result = self._extract_urls_from_web(video_info)
            
            # Fallback to TikWM API (third-party, more reliable)
            if not result["success"]:
                logger.info("Web scraping failed, trying TikWM API...")
                tikwm_result = self._get_video_info_tikwm(resolved_url)
                if tikwm_result and tikwm_result.get("success"):
                    result = tikwm_result
            
            if not result["success"]:
                result["error"] = "Failed to get video. Video may be private or unavailable."
            
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
            
            # No watermark URL
            play_addr = video.get("play_addr", {})
            url_list = play_addr.get("url_list", [])
            if url_list:
                result["no_watermark"] = url_list[0]
            
            # Watermark URL
            download_addr = video.get("download_addr", {})
            download_list = download_addr.get("url_list", [])
            if download_list:
                result["watermark"] = download_list[0]
            
            # Audio
            music = video_info.get("music", {})
            play_url = music.get("play_url", {})
            if isinstance(play_url, dict):
                music_urls = play_url.get("url_list", [])
                if music_urls:
                    result["audio"] = music_urls[0]
            elif isinstance(play_url, str):
                result["audio"] = play_url
            
            # Cover
            cover = video.get("cover", {})
            cover_urls = cover.get("url_list", [])
            if cover_urls:
                result["cover"] = cover_urls[0]
            
            # Metadata
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
            
            # playAddr
            play_addr = video.get("playAddr")
            if isinstance(play_addr, str):
                result["no_watermark"] = play_addr
            elif isinstance(play_addr, dict):
                result["no_watermark"] = play_addr.get("src") or play_addr.get("url")
            
            # downloadAddr
            download_addr = video.get("downloadAddr")
            if isinstance(download_addr, str):
                result["watermark"] = download_addr
            elif isinstance(download_addr, dict):
                result["watermark"] = download_addr.get("src") or download_addr.get("url")
            
            # Audio
            music = video_info.get("music", {})
            result["audio"] = music.get("playUrl")
            
            # Cover
            result["cover"] = video.get("cover") or video.get("originCover")
            
            # Metadata
            result["title"] = video_info.get("desc", "TikTok Video")
            result["author"] = video_info.get("author", {}).get("nickname", "Unknown")
            
            result["success"] = bool(result["no_watermark"] or result["watermark"])
            
        except Exception as e:
            logger.error(f"Failed to extract URLs from web: {e}")
            result["error"] = str(e)
        
        return result


def download_tiktok_video(url, output_path, format_id='tiktok_no_watermark'):
    """
    Download TikTok video
    
    Args:
        url: TikTok video URL
        output_path: Path to save the video
        format_id: 'tiktok_no_watermark', 'tiktok_watermark', or 'tiktok_audio'
    """
    logger.info(f"TikTok download started: {url} (format: {format_id})")
    
    downloader = TikTokDownloader()
    result = downloader.get_download_urls(url)
    
    logger.info(f"TikTok result: success={result['success']}, has_cookies={bool(downloader.cookies)}")
    
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
    
    logger.info(f"Downloading from: {download_url[:100]}...")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        }
        
        resp = requests.get(download_url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"TikTok download completed: {output_path}")
        return {
            "success": True,
            "file": output_path,
            "title": result.get("title"),
            "author": result.get("author")
        }
        
    except Exception as e:
        logger.error(f"TikTok download failed: {e}")
        return {"success": False, "error": str(e)}
