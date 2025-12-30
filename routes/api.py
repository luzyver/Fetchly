import logging
from flask import Blueprint, request, jsonify
from core.utils import is_tiktok_url, is_twitter_url, is_instagram_url, is_direct_supported, get_user_error
from core.tiktok import fetch_tiktok_formats
from core.twitter import fetch_twitter_formats
from core.instagram import fetch_instagram_formats
from core.generic import fetch_generic_formats
from core.resolver import resolve_source_url
from core.database import check_limit, get_user_history

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)
executor = None


def set_executor(exec):
    global executor
    executor = exec


@api_bp.route('/check-limit', methods=['POST'])
def check_usage_limit():
    data = request.json
    fingerprint = data.get('fingerprint', '')

    if not fingerprint:
        return jsonify({'error': 'Fingerprint required'}), 400

    result = check_limit(fingerprint)
    return jsonify(result)


@api_bp.route('/history', methods=['POST'])
def get_history():
    data = request.json
    fingerprint = data.get('fingerprint', '')

    if not fingerprint:
        return jsonify({'error': 'Fingerprint required'}), 400

    history = get_user_history(fingerprint)
    return jsonify({'history': history})


@api_bp.route('/fetch-formats', methods=['POST'])
def fetch_formats():
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        if is_tiktok_url(url):
            return _handle_tiktok(url)

        if is_twitter_url(url):
            return _handle_twitter(url)

        if is_instagram_url(url):
            return _handle_instagram(url)

        return _handle_generic(url)

    except Exception as e:
        logger.error(f"Fetch formats error: {e}")
        return jsonify({'error': get_user_error(str(e))}), 400


def _handle_tiktok(url):
    info = fetch_tiktok_formats(url)
    return jsonify({
        'formats': info['formats'],
        'resolved_url': url,
        'title': info['title'],
        'duration': info['duration'],
        'cookies': None,
        'referer': url
    })


def _handle_twitter(url):
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


def _handle_instagram(url):
    info = fetch_instagram_formats(url)
    return jsonify({
        'formats': info['formats'],
        'resolved_url': url,
        'title': info['title'],
        'duration': info['duration'],
        'cookies': None,
        'referer': url,
        'is_instagram': True,
        'video_url': info['video_url']
    })


def _handle_generic(url):
    resolved_url = url
    cookies = None
    user_agent = None
    referer = None

    if not is_direct_supported(url) and '.m3u8' not in url.lower():
        result = resolve_source_url(url)
        if not result or not result[0]:
            raise Exception("Could not find video stream")
        resolved_url, cookies, user_agent, referer = result
        logger.info(f"Resolved to: {resolved_url}")

    formats, video_info = fetch_generic_formats(url, resolved_url, cookies, user_agent, referer)

    return jsonify({
        'formats': formats,
        'resolved_url': resolved_url,
        'title': video_info.get('title', 'Video'),
        'duration': video_info.get('duration'),
        'cookies': cookies,
        'referer': referer or url
    })
