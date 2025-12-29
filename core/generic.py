import os
import json
import subprocess
import logging
from urllib.parse import urlparse
from core.config import CONFIG, USER_AGENTS, DIRECT_SUPPORTED_DOMAINS

logger = logging.getLogger(__name__)


def is_direct_supported(url):
    parsed = urlparse(url)
    return any(domain in parsed.netloc for domain in DIRECT_SUPPORTED_DOMAINS)


def fetch_generic_formats(url, resolved_url, cookies=None):
    referer = url
    parsed_url = urlparse(resolved_url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"

    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    stdout = None
    last_error = None

    for ua in [USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]:
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
        raise Exception(last_error or "Failed to fetch formats")

    video_info = json.loads(stdout.decode())
    return _parse_formats(video_info, is_direct_supported(url)), video_info


def _parse_formats(video_info, direct_supported):
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
            size_str = _format_size(filesize)
        elif tbr and duration:
            estimated = (tbr * 1000 / 8) * duration
            size_str = f"~{_format_size(estimated)}"
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
            'has_audio': direct_supported or fmt.get('acodec', 'none') != 'none'
        })

    formats.sort(key=lambda x: x['height'], reverse=True)
    formats.insert(0, {
        'format_id': 'best', 'resolution': 'Best Quality', 'height': 9999, 'width': 0,
        'ext': 'mp4', 'filesize': '', 'bitrate': '', 'has_audio': True
    })

    return formats


def _format_size(size_bytes):
    if not size_bytes:
        return ''
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024*1024):.1f} MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def download_generic_video(url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Generic download: {url[:60]} (format: {format_id})")

    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    current_referer = referer or domain
    direct_supported = is_direct_supported(url)

    cookie_file = CONFIG.get('COOKIE_FILE')
    has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

    last_error = None

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        try:
            cmd = ['yt-dlp', '--user-agent', ua, '--no-check-certificate', '--no-playlist', '-o', output_path]

            if has_cookie_file:
                cmd[1:1] = ['--cookies', cookie_file]

            if direct_supported:
                fmt = f'{format_id}+bestaudio/best' if format_id and format_id != 'best' else 'bestvideo+bestaudio/best'
                cmd.extend(['-f', fmt, '--merge-output-format', 'mp4'])
            else:
                cmd.extend(['--add-header', f'Referer: {current_referer}', '--add-header', f'Origin: {domain}', '--concurrent-fragments', '4'])
                if format_id and format_id != 'best':
                    cmd.extend(['-f', format_id])
                if cookies:
                    cmd.extend(['--add-header', f'Cookie: {cookies}'])

            cmd.append(url)

            logger.info(f"Generic attempt {i+1}/2")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = process.communicate()

            if process.returncode == 0:
                logger.info(f"Generic download completed: {output_path}")
                return {"success": True, "file": output_path}

            last_error = stderr.decode().strip()[-300:]
            logger.warning(f"Generic attempt {i+1} failed: {last_error}")

        except Exception as e:
            last_error = str(e)
            logger.error(f"Generic attempt {i+1} exception: {e}")

    return {"success": False, "error": last_error}
