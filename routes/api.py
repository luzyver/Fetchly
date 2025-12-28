import os
import json
import subprocess
import logging
from flask import Blueprint, request, jsonify
from urllib.parse import urlparse
from core.config import CONFIG, USER_AGENTS, DIRECT_SUPPORTED_DOMAINS
from core.resolver import resolve_source_url
from core.tiktok import TikTokDownloader

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)
executor = None


def set_executor(exec):
    global executor
    executor = exec


def format_size(size_bytes):
    if not size_bytes:
        return ''
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


@api_bp.route('/fetch-formats', methods=['POST'])
def fetch_formats():
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    is_tiktok = TikTokDownloader.is_tiktok_url(url)
    is_direct_supported = any(domain in urlparse(url).netloc for domain in DIRECT_SUPPORTED_DOMAINS)

    if is_tiktok:
        return _fetch_tiktok_formats(url)

    return _fetch_generic_formats(url, is_direct_supported)


def _fetch_tiktok_formats(url):
    downloader = TikTokDownloader()
    info = downloader.get_download_urls(url)
    hd_size = format_size(info.get('size_hd') or info.get('size'))

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


def _fetch_generic_formats(url, is_direct_supported):
    resolved_url = url
    cookies = None
    referer = url

    if not is_direct_supported and '.m3u8' not in url.lower():
        try:
            resolved_url, cookies = resolve_source_url(url)
            logger.info(f"Resolved to: {resolved_url}")
        except Exception as e:
            return jsonify({'error': f'Could not fetch video: {str(e)}'}), 400

    try:
        parsed_url = urlparse(resolved_url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        cookie_file = CONFIG.get('COOKIE_FILE')
        has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

        stdout = None
        last_error = None

        for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
            try:
                cmd = ['yt-dlp', '--user-agent', ua, '--add-header', f'Referer: {referer}',
                       '--add-header', f'Origin: {domain}', '--no-check-certificate', '-J', resolved_url]

                if has_cookie_file:
                    cmd[1:1] = ['--cookies', cookie_file]
                elif cookies:
                    cmd.extend(['--add-header', f'Cookie: {cookies}'])

                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = process.communicate(timeout=30)

                if process.returncode == 0:
                    stdout = out
                    break
                last_error = err.decode().strip()[-200:]

            except subprocess.TimeoutExpired:
                last_error = "Timeout"
            except Exception as e:
                last_error = str(e)

        if not stdout:
            return jsonify({'error': _get_user_error(last_error)}), 400

        video_info = json.loads(stdout.decode())
        formats = _parse_formats(video_info, is_direct_supported)

        return jsonify({
            'formats': formats,
            'resolved_url': resolved_url,
            'title': video_info.get('title', 'Video'),
            'duration': video_info.get('duration'),
            'cookies': cookies,
            'referer': referer
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Request timeout. Try again.'}), 408
    except json.JSONDecodeError:
        return jsonify({'error': 'Failed to parse video info'}), 400
    except Exception as e:
        logger.error(f"Fetch formats error: {e}")
        return jsonify({'error': str(e)}), 500


def _parse_formats(video_info, is_direct_supported):
    duration = video_info.get('duration')
    formats = []
    seen = set()

    for fmt in video_info.get('formats', []):
        height = fmt.get('height')
        if fmt.get('vcodec', 'none') == 'none' or not height:
            continue

        resolution = f"{height}p"
        if resolution in seen:
            continue
        seen.add(resolution)

        filesize = fmt.get('filesize') or fmt.get('filesize_approx')
        tbr = fmt.get('tbr')

        if filesize:
            size_str = format_size(filesize)
        elif tbr and duration:
            estimated = (tbr * 1000 / 8) * duration
            size_str = f"~{format_size(estimated)}"
        else:
            size_str = ""

        formats.append({
            'format_id': fmt.get('format_id', ''),
            'resolution': resolution,
            'height': height,
            'width': fmt.get('width', 0),
            'ext': fmt.get('ext', 'mp4'),
            'filesize': size_str,
            'bitrate': f"{int(tbr)}kbps" if tbr else "",
            'has_audio': is_direct_supported or fmt.get('acodec', 'none') != 'none'
        })

    formats.sort(key=lambda x: x['height'], reverse=True)
    formats.insert(0, {
        'format_id': 'best', 'resolution': 'Best Quality', 'height': 9999, 'width': 0,
        'ext': 'mp4', 'filesize': '', 'bitrate': '', 'has_audio': True
    })

    return formats


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
