import os
import uuid
import json
import subprocess
import logging
from flask import Blueprint, request, jsonify, send_file
from urllib.parse import urlparse
from core.config import CONFIG, USER_AGENTS, DIRECT_SUPPORTED_DOMAINS
from core.database import get_db
from core.resolver import resolve_source_url

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

executor = None

def set_executor(exec):
    global executor
    executor = exec

@api_bp.route('/fetch-formats', methods=['POST'])
def fetch_formats():
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    resolved_url = url
    cookies = None
    referer = url
    is_direct_supported = False
    
    parsed = urlparse(url)
    for domain in DIRECT_SUPPORTED_DOMAINS:
        if domain in parsed.netloc:
            is_direct_supported = True
            break
    
    if not is_direct_supported and '.m3u8' not in url.lower():
        try:
            resolved_url, cookies = resolve_source_url(url)
            logger.info(f"Resolved to: {resolved_url}")
        except Exception as e:
            return jsonify({'error': f'Could not fetch video: {str(e)}'}), 400
    
    try:
        parsed_url = urlparse(resolved_url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        
        agents_to_try = [USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]
        last_error = None
        stdout = None
        
        cookie_file = CONFIG.get('COOKIE_FILE')
        has_cookie_file = cookie_file and os.path.exists(cookie_file) and os.path.getsize(cookie_file) > 100

        for i, ua in enumerate(agents_to_try):
            try:
                logger.info(f"Fetch Formats: Attempt {i+1}/{len(agents_to_try)} (UA: {'Mobile' if 'Mobile' in ua else 'Desktop'})")
                
                cmd = [
                    'yt-dlp',
                    '--user-agent', ua,
                    '--add-header', f'Referer: {referer}',
                    '--add-header', f'Origin: {domain}',
                    '--no-check-certificate',
                    '-J',
                    resolved_url
                ]
                
                if has_cookie_file:
                    cmd.insert(1, '--cookies')
                    cmd.insert(2, cookie_file)
                elif cookies:
                    cmd.extend(['--add-header', f'Cookie: {cookies}'])
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = process.communicate(timeout=30)
                
                if process.returncode == 0:
                    stdout = out
                    break
                else:
                    error_msg = err.decode().strip()
                    last_error = error_msg[-200:]
                    logger.warning(f"Fetch Formats: Attempt {i+1} failed. Error: {last_error}")
            
            except subprocess.TimeoutExpired:
                last_error = "Timeout"
                logger.warning(f"Fetch Formats: Attempt {i+1} timed out")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Fetch Formats: Attempt {i+1} error: {e}")

        if not stdout:
            user_error = "Unable to fetch video formats. The video may be private, unavailable, or the platform is currently unsupported."
            
            if last_error:
                if "login required" in last_error.lower() or "cookies" in last_error.lower():
                    user_error = "This video requires authentication. Please ensure cookies are configured."
                elif "private" in last_error.lower():
                    user_error = "This video is private and cannot be accessed."
                elif "not available" in last_error.lower() or "unavailable" in last_error.lower():
                    user_error = "This video is not available in your region or has been removed."
                elif "rate" in last_error.lower() or "limit" in last_error.lower():
                    user_error = "Rate limit reached. Please try again later."
                elif "timeout" in last_error.lower():
                    user_error = "Request timed out. Please try again."
            
            return jsonify({'error': user_error}), 400
        
        video_info = json.loads(stdout.decode())
        duration = video_info.get('duration')
        
        formats = []
        seen_resolutions = set()
        
        for fmt in video_info.get('formats', []):
            height = fmt.get('height')
            width = fmt.get('width')
            format_id = fmt.get('format_id', '')
            ext = fmt.get('ext', 'mp4')
            filesize = fmt.get('filesize') or fmt.get('filesize_approx')
            tbr = fmt.get('tbr')
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            
            if vcodec == 'none' or not height:
                continue
            
            resolution = f"{height}p"
            
            if resolution in seen_resolutions:
                continue
            seen_resolutions.add(resolution)
            
            size_str = ""
            if filesize:
                if filesize > 1024 * 1024 * 1024:
                    size_str = f"{filesize / (1024*1024*1024):.1f} GB"
                elif filesize > 1024 * 1024:
                    size_str = f"{filesize / (1024*1024):.1f} MB"
                else:
                    size_str = f"{filesize / 1024:.1f} KB"
            elif tbr and duration:
                estimated_bytes = (tbr * 1000 / 8) * duration
                if estimated_bytes > 1024 * 1024 * 1024:
                    size_str = f"~{estimated_bytes / (1024*1024*1024):.1f} GB"
                elif estimated_bytes > 1024 * 1024:
                    size_str = f"~{estimated_bytes / (1024*1024):.0f} MB"
                else:
                    size_str = f"~{estimated_bytes / 1024:.0f} KB"
            
            formats.append({
                'format_id': format_id,
                'resolution': resolution,
                'height': height,
                'width': width,
                'ext': ext,
                'filesize': size_str,
                'bitrate': f"{int(tbr)}kbps" if tbr else "",
                'has_audio': is_direct_supported or acodec != 'none'
            })
        
        formats.sort(key=lambda x: x['height'], reverse=True)
        
        formats.insert(0, {
            'format_id': 'best',
            'resolution': 'Best Quality',
            'height': 9999,
            'width': 0,
            'ext': 'mp4',
            'filesize': '',
            'bitrate': '',
            'has_audio': True
        })
        
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