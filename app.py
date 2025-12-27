from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import os
import uuid
import time
import requests
import sqlite3
import logging
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
DOWNLOAD_FOLDER = 'downloads'
DB_PATH = os.path.join(DOWNLOAD_FOLDER, 'tasks.db')
MAX_WORKERS = 4  # Limit concurrent conversions
UA_DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
UA_MOBILE = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Thread Pool for background tasks
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                url TEXT,
                status TEXT,
                file TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def update_task_status(task_id, status, file=None, error=None):
    try:
        with closing(get_db_connection()) as conn:
            c = conn.cursor()
            update_fields = ["status = ?"]
            params = [status]
            
            if file:
                update_fields.append("file = ?")
                params.append(file)
            if error:
                update_fields.append("error = ?")
                params.append(error)
                
            params.append(task_id)
            
            query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
            c.execute(query, params)
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update task status {task_id}: {e}")

def convert_m3u8(task_id, url, output_path, referer=None):
    """Convert M3U8 to MP4 using FFmpeg with Smart Retry"""
    logger.info(f"Starting conversion for task {task_id}")
    try:
        update_task_status(task_id, 'processing')
        
        user_agents = [UA_DESKTOP, UA_MOBILE]
        success = False
        last_error = None
        
        for i, ua in enumerate(user_agents):
            try:
                headers_list = [f'User-Agent: {ua}']
                if referer:
                    headers_list.append(f'Referer: {referer}')
                    
                headers_str = '\r\n'.join(headers_list) + '\r\n'
                
                cmd = [
                    'ffmpeg',
                    '-headers', headers_str,
                    '-i', url,
                    '-c', 'copy',
                    '-bsf:a', 'aac_adtstoasc',
                    '-y',
                    output_path
                ]
                
                logger.info(f"Task {task_id}: Running ffmpeg (Attempt {i+1})")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    update_task_status(task_id, 'completed', file=output_path)
                    success = True
                    logger.info(f"Task {task_id}: Conversion successful")
                    break
                else:
                    error_msg = stderr.decode()
                    logger.warning(f"Task {task_id}: Attempt {i+1} failed. Error: {error_msg[-200:]}")
                    
                    if "403 Forbidden" in error_msg or "404 Not Found" in error_msg:
                        last_error = f"Attempt {i+1} failed (Access Denied): {error_msg[-100:]}"
                        continue
                    else:
                        raise Exception(error_msg[-200:]) 
                        
            except Exception as e:
                last_error = str(e)
                continue
                
        if not success:
            logger.error(f"Task {task_id}: All attempts failed")
            update_task_status(task_id, 'failed', error=last_error or "All attempts failed")
            
    except Exception as e:
        logger.error(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))

def cleanup_old_files():
    """Background task to clean up old files and DB entries"""
    while True:
        try:
            time.sleep(3600)  # Check every hour
            logger.info("Running cleanup task")
            
            # 1. Delete physical files older than 1 hour
            cutoff_time = time.time() - 3600
            for filename in os.listdir(DOWNLOAD_FOLDER):
                if filename.endswith('.mp4'):
                    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                    if os.path.getmtime(filepath) < cutoff_time:
                        try:
                            os.remove(filepath)
                            logger.info(f"Deleted old file: {filename}")
                        except OSError as e:
                            logger.warning(f"Error deleting {filename}: {e}")

            # 2. Delete DB entries older than 24 hours
            with closing(get_db_connection()) as conn:
                conn.execute("DELETE FROM tasks WHERE created_at < datetime('now', '-1 day')")
                conn.commit()
                
        except Exception as e:
            logger.error(f"Cleanup loop error: {e}")

# Start cleanup in background
executor.submit(cleanup_old_files)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url', '').strip()
    referer = data.get('referer', '').strip()
    
    if not url:
        return jsonify({'error': 'URL tidak boleh kosong'}), 400
    
    # Basic M3U8 validation
    if not (url.lower().endswith('.m3u8') or '.m3u8' in url.lower()):
         return jsonify({'error': 'URL harus berformat M3U8'}), 400
    
    task_id = str(uuid.uuid4())
    filename = f"{task_id}.mp4"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    try:
        with closing(get_db_connection()) as conn:
            conn.execute('INSERT INTO tasks (id, url, status) VALUES (?, ?, ?)',
                         (task_id, url, 'queued'))
            conn.commit()
            
        # Submit to thread pool
        executor.submit(convert_m3u8, task_id, url, output_path, referer)
        
        return jsonify({'task_id': task_id})
    except Exception as e:
        logger.error(f"Failed to submit task: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/status/<task_id>')
def status(task_id):
    try:
        with closing(get_db_connection()) as conn:
            task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        
        if task is None:
            return jsonify({'error': 'Task tidak ditemukan'}), 404
        
        return jsonify(dict(task))
    except Exception:
        return jsonify({'error': 'Database error'}), 500

@app.route('/download/<task_id>')
def download(task_id):
    try:
        with closing(get_db_connection()) as conn:
            task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        
        if task is None:
            return jsonify({'error': 'Task tidak ditemukan'}), 404
        
        if task['status'] != 'completed':
            return jsonify({'error': 'File belum siap'}), 400
        
        if not os.path.exists(task['file']):
             return jsonify({'error': 'File telah kadaluarsa atau dihapus'}), 404

        return send_file(
            task['file'],
            as_attachment=True,
            download_name=f"video_{task_id[:8]}.mp4"
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': 'Gagal mengunduh file'}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)