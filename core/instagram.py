import os
import re
import time
import logging
import requests
import yt_dlp
import instaloader
from instaloader import Post

logger = logging.getLogger(__name__)

_loader = None
_last_request_time = 0
REQUEST_DELAY = 2

PROXY = os.getenv('INSTAGRAM_PROXY', '')


def _get_proxy():
    if PROXY:
        return {
            'http': PROXY,
            'https': PROXY
        }
    return None


def _get_loader():
    global _loader

    if _loader is not None:
        return _loader

    _loader = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        request_timeout=30
    )

    if PROXY:
        _loader.context._session.proxies = _get_proxy()
        logger.info(f"Using proxy for Instagram: {PROXY}")

    username = os.getenv('INSTAGRAM_USERNAME')
    password = os.getenv('INSTAGRAM_PASSWORD')
    session_file = os.getenv('INSTAGRAM_SESSION_FILE', 'instagram_session')

    if not username:
        logger.warning("INSTAGRAM_USERNAME not set, using anonymous mode")
        return _loader

    try:
        _loader.load_session_from_file(username, session_file)
        logger.info(f"Loaded Instagram session for {username}")
        return _loader
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"Failed to load session: {e}")

    if password:
        try:
            time.sleep(3)
            _loader.login(username, password)
            _loader.save_session_to_file(session_file)
            logger.info(f"Logged in and saved session for {username}")
        except Exception as e:
            logger.error(f"Instagram login failed: {e}")

    return _loader


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


def _extract_shortcode(url):
    patterns = [
        r'instagram\.com/p/([^/?#]+)',
        r'instagram\.com/reel/([^/?#]+)',
        r'instagram\.com/tv/([^/?#]+)',
        r'instagram\.com/reels/([^/?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid Instagram URL")


def _fetch_with_instaloader(url):
    _rate_limit()
    loader = _get_loader()
    shortcode = _extract_shortcode(url)

    post = Post.from_shortcode(loader.context, shortcode)

    if not post.is_video:
        raise Exception("This Instagram post is not a video")

    title = "Instagram Video"
    if post.caption:
        title = post.caption[:50].replace('\n', ' ').strip()
        if len(post.caption) > 50:
            title += "..."

    return {
        'title': title,
        'duration': post.video_duration,
        'video_url': post.video_url
    }


def _fetch_with_ytdlp(url):
    logger.info("Falling back to yt-dlp for Instagram")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    cookie_file = _export_cookies_to_file()
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    if PROXY:
        ydl_opts['proxy'] = PROXY

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise Exception("Could not fetch Instagram video")

    title = info.get('title', 'Instagram Video')
    if len(title) > 50:
        title = title[:50] + "..."

    video_url = None
    if info.get('url'):
        video_url = info['url']
    elif info.get('formats'):
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


def _export_cookies_to_file():
    try:
        loader = _get_loader()
        if not loader.context._session or not loader.context._session.cookies:
            return None
        
        cookie_file = 'instagram_cookies.txt'
        with open(cookie_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in loader.context._session.cookies:
                secure = "TRUE" if cookie.secure else "FALSE"
                expires = str(int(cookie.expires)) if cookie.expires else "0"
                f.write(f".instagram.com\tTRUE\t{cookie.path}\t{secure}\t{expires}\t{cookie.name}\t{cookie.value}\n")
        
        logger.info("Exported Instagram cookies for yt-dlp")
        return cookie_file
    except Exception as e:
        logger.warning(f"Could not export cookies: {e}")
    return None


def fetch_instagram_formats(url):
    try:
        info = _fetch_with_instaloader(url)
    except Exception as e:
        logger.warning(f"Instaloader failed: {e}, trying yt-dlp")
        try:
            info = _fetch_with_ytdlp(url)
        except Exception as e2:
            logger.error(f"yt-dlp also failed: {e2}")
            raise Exception("Instagram is temporarily unavailable. Please try again in 15-30 minutes.")

    formats = [{
        'format_id': 'best',
        'resolution': 'Best Quality',
        'height': 9999,
        'width': 0,
        'ext': 'mp4',
        'filesize': '',
        'bitrate': '',
        'has_audio': True
    }]

    return {
        'formats': formats,
        'title': info['title'],
        'duration': info['duration'],
        'video_url': info['video_url'],
        'thumbnail': ''
    }


def download_instagram(url, output_path):
    try:
        info = fetch_instagram_formats(url)
        video_url = info['video_url']

        proxies = _get_proxy()
        response = requests.get(video_url, stream=True, timeout=60, proxies=proxies, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return {"success": True, "file": output_path}
    except Exception as e:
        logger.error(f"Instagram download failed: {e}")
        return {"success": False, "error": str(e)}
