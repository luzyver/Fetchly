import os
import re
import time
import logging
import requests
import instaloader
from instaloader import Post

logger = logging.getLogger(__name__)

_loader = None
_last_request_time = 0
REQUEST_DELAY = 2


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
            raise Exception("Instagram login failed. Check credentials.")

    return _loader


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()

    return _loader


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


def fetch_instagram_formats(url):
    _rate_limit()
    loader = _get_loader()
    shortcode = _extract_shortcode(url)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            post = Post.from_shortcode(loader.context, shortcode)
            break
        except instaloader.exceptions.QueryReturnedBadRequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise Exception("Instagram rate limit. Please try again in a few minutes.")
        except Exception as e:
            logger.error(f"Failed to fetch post {shortcode}: {e}")
            if "401" in str(e) or "rate" in str(e).lower():
                raise Exception("Instagram rate limit. Please try again in a few minutes.")
            raise Exception("Could not fetch Instagram post. It may be private or deleted.")

    if not post.is_video:
        raise Exception("This Instagram post is not a video")

    title = "Instagram Video"
    if post.caption:
        title = post.caption[:50].replace('\n', ' ').strip()
        if len(post.caption) > 50:
            title += "..."

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
        'title': title,
        'duration': post.video_duration,
        'video_url': post.video_url,
        'thumbnail': post.url
    }


def download_instagram(url, output_path):
    info = fetch_instagram_formats(url)
    video_url = info['video_url']

    try:
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return {"success": True, "file": output_path}
    except Exception as e:
        logger.error(f"Instagram download failed: {e}")
        return {"success": False, "error": str(e)}
