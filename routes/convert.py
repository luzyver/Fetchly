import os
import uuid
import logging
from flask import Blueprint, request, jsonify, send_file
from core.config import CONFIG
from core.database import get_db, check_limit, record_abuse_attempt, set_full_usage
from core.resolver import resolve_source_url
from core.converter import process_download
from core.utils import is_tiktok_url, is_twitter_url, is_direct_supported

logger = logging.getLogger(__name__)
convert_bp = Blueprint('convert', __name__)
executor = None


def set_executor(exec):
    global executor
    executor = exec


def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or 'unknown'


@convert_bp.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    resolved_url = data.get('resolved_url')
    cookies = data.get('cookies')
    referer = data.get('referer', url)
    fingerprint = data.get('fingerprint', '')
    title = data.get('title', 'Video')
    ip = get_client_ip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    limit_info = check_limit(fingerprint, ip)
    if not limit_info['allowed']:
        return jsonify({'error': 'Daily limit reached (1GB). Try again tomorrow.'}), 429

    # Skip filesize validation for whitelisted users
    estimated_filesize = data.get('filesize', 0)
    max_file_size = 1 * 1024 * 1024 * 1024  # 1GB max per file

    if not limit_info.get('whitelisted') and estimated_filesize > 0:
        if estimated_filesize > limit_info['remaining'] or estimated_filesize > max_file_size:
            # Record abuse attempt
            should_penalize = record_abuse_attempt(fingerprint, ip)
            if should_penalize:
                set_full_usage(fingerprint, ip)
                return jsonify({
                    'error': 'Too many attempts with oversized files. Daily limit has been fully consumed as penalty.'
                }), 429

            remaining_mb = round(limit_info['remaining'] / (1024 * 1024))
            filesize_mb = round(estimated_filesize / (1024 * 1024))
            
            if estimated_filesize > max_file_size:
                return jsonify({
                    'error': f'File too large ({filesize_mb}MB). Maximum file size is 1GB.'
                }), 429
            else:
                return jsonify({
                    'error': f'File too large ({filesize_mb}MB). You only have {remaining_mb}MB remaining today.'
                }), 429

    if not resolved_url:
        resolved_url = url
        needs_resolve = (
            '.m3u8' not in url.lower() and
            not is_tiktok_url(url) and
            not is_twitter_url(url) and
            not is_direct_supported(url)
        )

        if needs_resolve:
            try:
                result = resolve_source_url(url)
                if result and result[0]:
                    resolved_url, cookies, _, captured_referer = result
                    if captured_referer:
                        referer = captured_referer
                    logger.info(f"Resolved to: {resolved_url}")
            except Exception as e:
                return jsonify({'error': f'Could not fetch video: {str(e)}'}), 400

    task_id = str(uuid.uuid4())
    ext = 'mp3' if format_id == 'tiktok_audio' else 'mp4'
    output_path = os.path.join(CONFIG['DOWNLOAD_FOLDER'], f"{task_id}.{ext}")

    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO tasks (id, url, status, fingerprint, ip_address, title) VALUES (?, ?, ?, ?, ?, ?)',
                (task_id, resolved_url, 'queued', fingerprint, ip, title[:100])
            )
            conn.commit()

        executor.submit(process_download, task_id, resolved_url, output_path, referer, cookies, format_id)
        return jsonify({'task_id': task_id})

    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({'error': 'Server Error'}), 500


@convert_bp.route('/status/<task_id>')
def status(task_id):
    try:
        with get_db() as conn:
            task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()

        if not task:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify(dict(task))
    except Exception:
        return jsonify({'error': 'Database error'}), 500


@convert_bp.route('/download/<task_id>')
def download(task_id):
    try:
        with get_db() as conn:
            task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()

        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if task['status'] != 'completed':
            return jsonify({'error': 'File not ready'}), 400

        if not task['file'] or not os.path.exists(task['file']):
            return jsonify({'error': 'File expired or removed'}), 404

        ext = 'mp3' if task['file'].endswith('.mp3') else 'mp4'
        return send_file(task['file'], as_attachment=True, download_name=f"{task_id}.{ext}")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return jsonify({'error': 'Download failed'}), 500
