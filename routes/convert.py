import os
import uuid
import logging
from flask import Blueprint, request, jsonify, send_file
from core.config import CONFIG
from core.database import get_db
from core.resolver import resolve_source_url
from core.converter import convert_m3u8
from core.tiktok import TikTokDownloader
from core.twitter import is_twitter_url
from core.generic import is_direct_supported

logger = logging.getLogger(__name__)
convert_bp = Blueprint('convert', __name__)
executor = None


def set_executor(exec):
    global executor
    executor = exec


@convert_bp.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    resolved_url = data.get('resolved_url')
    cookies = data.get('cookies')
    referer = data.get('referer', url)

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    if not resolved_url:
        resolved_url = url
        is_tiktok = TikTokDownloader.is_tiktok_url(url)
        is_twitter = is_twitter_url(url)
        is_direct = is_direct_supported(url)

        if '.m3u8' not in url.lower() and not is_tiktok and not is_twitter and not is_direct:
            try:
                resolved_url, cookies = resolve_source_url(url)
                logger.info(f"Resolved to: {resolved_url}")
            except Exception as e:
                return jsonify({'error': f'Could not fetch video: {str(e)}'}), 400

    task_id = str(uuid.uuid4())
    ext = 'mp3' if format_id == 'tiktok_audio' else 'mp4'
    output_path = os.path.join(CONFIG['DOWNLOAD_FOLDER'], f"{task_id}.{ext}")

    try:
        with get_db() as conn:
            conn.execute('INSERT INTO tasks (id, url, status) VALUES (?, ?, ?)',
                         (task_id, resolved_url, 'queued'))
            conn.commit()

        executor.submit(convert_m3u8, task_id, resolved_url, output_path, referer, cookies, format_id)
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
