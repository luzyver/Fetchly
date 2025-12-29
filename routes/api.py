import logging
from flask import Blueprint, request, jsonify
from core.tiktok import TikTokDownloader
from core.twitter import is_twitter_url, fetch_twitter_formats
from core.generic import is_direct_supported, fetch_generic_formats
from core.resolver import resolve_source_url

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)
executor = None


def set_executor(exec):
    global executor
    executor = exec


def _format_size(size_bytes):
    if not size_bytes:
        return ''
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _get_user_error(last_error):
    if not last_error:
        return "Unable to fetch video formats."

    error_lower = last_error.lower()
    if "login required" in error_lower or "cookies" in error_lower:
        return "This video requires authentication."
    if "private" in error_lower:
        return "This video is private."
    if "not available" in error_lower or "unavailable" in error_lower:
        return "This video is not available."
    if "rate" in error_lower or "limit" in error_lower:
        return "Rate limit reached. Try again later."
    if "timeout" in error_lower:
        return "Request timed out. Try again."

    return "Unable to fetch video formats."


@api_bp.route('/fetch-formats', methods=['POST'])
def fetch_formats():
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        if TikTokDownloader.is_tiktok_url(url):
            return _fetch_tiktok_formats(url)

        if is_twitter_url(url):
            return _fetch_twitter_formats(url)

        return _fetch_generic_formats(url)

    except Exception as e:
        logger.error(f"Fetch formats error: {e}")
        return jsonify({'error': _get_user_error(str(e))}), 400


def _fetch_tiktok_formats(url):
    downloader = TikTokDownloader()
    info = downloader.get_download_urls(url)
    hd_size = _format_size(info.get('size_hd') or info.get('size'))

    return jsonify({
        'formats': [
            {'format_id': 'tiktok_no_watermark', 'resolution': 'No Watermark (HD)', 'height': 9999, 'width': 0, 'ext': 'mp4', 'filesize': hd_size, 'bitrate': '', 'has_audio': True},
            {'format_id': 'tiktok_watermark', 'resolution': 'With Watermark', 'height': 9998, 'width': 0, 'ext': 'mp4', 'filesize': hd_size, 'bitrate': '', 'has_audio': True},
            {'format_id': 'tiktok_audio', 'resolution': 'Audio Only', 'height': 0, 'width': 0, 'ext': 'mp3', 'filesize': '', 'bitrate': '', 'has_audio': True}
        ],
        'resolved_url': url,
        'title': info.get('title') or 'TikTok Video',
        'duration': info.get('duration'),
        'cookies': None,
        'referer': url
    })


def _fetch_twitter_formats(url):
    info = fetch_twitter_formats(url)

    return jsonify({
        'formats': info['formats'],
        'resolved_url': url,
        'title': info['title'],
        'duration': info['duration'],
        'cookies': None,
        'referer': url,
        'is_twitter': True,
        'video_count': info['video_count']
    })


def _fetch_generic_formats(url):
    resolved_url = url
    cookies = None

    if not is_direct_supported(url) and '.m3u8' not in url.lower():
        resolved_url, cookies = resolve_source_url(url)
        logger.info(f"Resolved to: {resolved_url}")

    formats, video_info = fetch_generic_formats(url, resolved_url, cookies)

    return jsonify({
        'formats': formats,
        'resolved_url': resolved_url,
        'title': video_info.get('title', 'Video'),
        'duration': video_info.get('duration'),
        'cookies': cookies,
        'referer': url
    })
