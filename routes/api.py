import logging
from typing import Any
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, jsonify
from core.utils import (
    is_tiktok_url, is_twitter_url, is_instagram_url, is_direct_supported,
    get_user_error, validate_public_url
)
from core.tiktok import fetch_tiktok_formats
from core.twitter import fetch_twitter_formats
from core.instagram import fetch_instagram_formats
from core.generic import fetch_generic_formats
from core.resolver import resolve_source_url
from core.database import check_limit, get_user_history
from core.captcha import verify_captcha, is_captcha_enabled
from core.config import CONFIG
from routes.helpers import get_client_ip

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

executor: ThreadPoolExecutor = None


def set_executor(exec: ThreadPoolExecutor) -> None:
    global executor
    executor = exec


@api_bp.route('/check-limit', methods=['POST'])
def check_usage_limit():
    data = request.json
    fingerprint = data.get('fingerprint', '')
    ip = get_client_ip()

    result = check_limit(fingerprint, ip)
    result['captcha_enabled'] = is_captcha_enabled()
    result['turnstile_site_key'] = CONFIG['TURNSTILE_SITE_KEY'] if is_captcha_enabled() else ''
    return jsonify(result)


@api_bp.route('/history', methods=['POST'])
def get_history():
    data = request.json
    fingerprint = data.get('fingerprint', '')
    ip = get_client_ip()

    history = get_user_history(fingerprint, ip)
    return jsonify({'history': history})


@api_bp.route('/fetch-formats', methods=['POST'])
def fetch_formats():
    data = request.json
    url = data.get('url', '').strip()
    captcha_response = data.get('captcha', '')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    validation_error = validate_public_url(url)
    if validation_error:
        return jsonify({'error': validation_error}), 400

    if is_captcha_enabled() and not verify_captcha(captcha_response):
        return jsonify({'error': 'Please complete the captcha', 'captcha_required': True}), 400

    try:
        return _handle_fetch(url)
    except Exception as e:
        logger.exception(f"Fetch formats error for {url}: {e}")
        return jsonify({'error': get_user_error(str(e))}), 400


def _handle_fetch(url: str) -> Any:
    handlers = [
        (is_tiktok_url, _handle_tiktok),
        (is_twitter_url, _handle_twitter),
        (is_instagram_url, _handle_instagram),
    ]

    for check_fn, handler_fn in handlers:
        if check_fn(url):
            return handler_fn(url)

    return _handle_generic(url)


def _handle_tiktok(url: str):
    info = fetch_tiktok_formats(url)
    return jsonify({
        'formats': info['formats'],
        'resolved_url': url,
        'title': info['title'],
        'duration': info['duration'],
        'cookies': None,
        'referer': url
    })


def _handle_twitter(url: str):
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


def _handle_instagram(url: str):
    info = fetch_instagram_formats(url)
    return jsonify({
        'formats': info['formats'],
        'resolved_url': url,
        'title': info['title'],
        'duration': info['duration'],
        'cookies': None,
        'referer': url,
        'is_instagram': True
    })


def _handle_generic(url: str):
    resolved_url = url
    cookies = None
    user_agent = None
    referer = None

    VIDEO_EXTENSIONS = ('.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.m3u8')
    is_direct_video = any(url.lower().split('?')[0].endswith(ext) for ext in VIDEO_EXTENSIONS)

    if not is_direct_video and not is_direct_supported(url):
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
