import json
import subprocess
import logging
from urllib.parse import urlparse
from core.config import USER_AGENTS
from core.utils import format_size, is_direct_supported, get_cookie_file

logger = logging.getLogger(__name__)

def fetch_generic_formats(url, resolved_url, cookies=None, user_agent=None, referer=None):
    current_referer = referer or url
    parsed_url = urlparse(resolved_url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    
    parsed_ref = urlparse(current_referer)
    origin_domain = f"{parsed_ref.scheme}://{parsed_ref.netloc}" if current_referer else domain
    
    cookie_file = get_cookie_file()
    stdout = None
    last_error = None

    user_agents = [user_agent] if user_agent else [USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]

    for ua in user_agents:
        cmd = _build_fetch_cmd(ua, resolved_url, current_referer, origin_domain, cookies, cookie_file)

        try:
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
    formats = _parse_formats(video_info, is_direct_supported(url))

    return formats, video_info

def _build_fetch_cmd(ua, resolved_url, referer, origin, cookies, cookie_file):
    cmd = ['yt-dlp', '--user-agent', ua, '--add-header', f'Referer: {referer}',
           '--add-header', f'Origin: {origin}', '--no-check-certificate', '-J', resolved_url]

    if '.m3u8' in resolved_url.lower():
        cmd[5:5] = [
            '--add-header', 'Accept: */*',
            '--add-header', 'Accept-Language: en-US,en;q=0.9',
            '--add-header', 'Sec-Fetch-Dest: empty',
            '--add-header', 'Sec-Fetch-Mode: cors',
            '--add-header', 'Sec-Fetch-Site: cross-site',
        ]

    if cookies:
        cmd.extend(['--add-header', f'Cookie: {cookies}'])
    elif cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    return cmd

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
        filesize_bytes = 0

        if filesize:
            size_str = format_size(filesize)
            filesize_bytes = int(filesize)
        elif tbr and duration:
            estimated = (tbr * 1000 / 8) * duration
            size_str = f"~{format_size(estimated)}"
            filesize_bytes = int(estimated)
        else:
            size_str = ""

        formats.append({
            'format_id': fmt.get('format_id', ''),
            'resolution': resolution,
            'height': height,
            'width': fmt.get('width', 0),
            'ext': fmt.get('ext', 'mp4'),
            'filesize': size_str,
            'filesize_bytes': filesize_bytes,
            'bitrate': f"{int(tbr)}kbps" if tbr else "",
            'has_audio': direct_supported or fmt.get('acodec', 'none') != 'none'
        })

    formats.sort(key=lambda x: x['height'], reverse=True)
    
    if not formats:
        formats.append({
            'format_id': 'bestvideo', 'resolution': 'HD (720p)', 'height': 720, 'width': 1280,
            'ext': 'mp4', 'filesize': '', 'filesize_bytes': 0, 'bitrate': '', 'has_audio': True
        })

    return formats

def download_generic(url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Generic download: {url[:60]} (format: {format_id})")

    parsed_url = urlparse(url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    current_referer = referer or domain
    direct_supported = is_direct_supported(url)
    cookie_file = get_cookie_file()

    last_error = None

    for i, ua in enumerate([USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]):
        cmd = _build_download_cmd(ua, url, output_path, current_referer, domain, 
                                   cookies, cookie_file, direct_supported, format_id)

        logger.info(f"Generic attempt {i+1}/2")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()

        if process.returncode == 0:
            logger.info(f"Generic download completed: {output_path}")
            return {"success": True, "file": output_path}

        last_error = stderr.decode().strip()[-300:]
        logger.warning(f"Generic attempt {i+1} failed: {last_error}")

    return {"success": False, "error": last_error}

def _build_download_cmd(ua, url, output_path, referer, domain, cookies, cookie_file, direct_supported, format_id):
    cmd = ['yt-dlp', '--user-agent', ua, '--no-check-certificate', '--no-playlist', '-o', output_path]

    if cookie_file:
        cmd[1:1] = ['--cookies', cookie_file]

    if direct_supported:
        fmt = f'{format_id}+bestaudio/best' if format_id and format_id != 'best' else 'bestvideo+bestaudio/best'
        cmd.extend(['-f', fmt, '--merge-output-format', 'mp4'])
    else:
        cmd.extend(['--add-header', f'Referer: {referer}', '--add-header', f'Origin: {domain}', '--concurrent-fragments', '4'])

        if '.m3u8' in url.lower():
            cmd.extend([
                '--add-header', 'Accept: */*',
                '--add-header', 'Accept-Language: en-US,en;q=0.9',
                '--add-header', 'Sec-Fetch-Dest: empty',
                '--add-header', 'Sec-Fetch-Mode: cors',
                '--add-header', 'Sec-Fetch-Site: cross-site',
            ])

        if format_id and format_id != 'best':
            cmd.extend(['-f', format_id])
        if cookies:
            cmd.extend(['--add-header', f'Cookie: {cookies}'])

    cmd.append(url)
    return cmd
