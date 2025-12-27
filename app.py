from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import os
import uuid
import threading
import time
import requests

UA_DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
UA_MOBILE = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

app = Flask(__name__)

# Folder untuk simpan hasil convert
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

import sqlite3
from datetime import datetime

# Initialize Database
DB_PATH = os.path.join(DOWNLOAD_FOLDER, 'tasks.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def update_task_status(task_id, status, file=None, error=None):
    conn = get_db_connection()
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
    conn.close()

def convert_m3u8(task_id, url, output_path, referer=None):
    """Convert M3U8 to MP4 using FFmpeg with Smart Retry"""
    try:
        update_task_status(task_id, 'processing')
        
        # User Agents to try
        user_agents = [UA_DESKTOP, UA_MOBILE]
        
        success = False
        last_error = None
        
        for i, ua in enumerate(user_agents):
            try:
                # Build headers for ffmpeg
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
                
                # Run ffmpeg
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    update_task_status(task_id, 'completed', file=output_path)
                    success = True
                    break
                else:
                    error_msg = stderr.decode()
                    # Only retry on 403/404 related errors in ffmpeg output
                    if "403 Forbidden" in error_msg or "404 Not Found" in error_msg:
                        last_error = f"Attempt {i+1} failed with UA change: {error_msg[-200:]}"
                        continue
                    else:
                        raise Exception(error_msg[-200:]) # Real error, don't retry
                        
            except Exception as e:
                last_error = str(e)
                continue
                
        if not success:
            update_task_status(task_id, 'failed', error=last_error or "All attempts failed")
            
    except Exception as e:
        update_task_status(task_id, 'failed', error=str(e))

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
    
    if not url.endswith('.m3u8') and 'm3u8' not in url:
        return jsonify({'error': 'URL harus berformat M3U8'}), 400
    
    task_id = str(uuid.uuid4())
    filename = f"{task_id}.mp4"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # Save to DB
    conn = get_db_connection()
    conn.execute('INSERT INTO tasks (id, url, status) VALUES (?, ?, ?)',
                 (task_id, url, 'queued'))
    conn.commit()
    conn.close()
    
    thread = threading.Thread(target=convert_m3u8, args=(task_id, url, output_path, referer))
    thread.start()
    
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>')
def status(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    if task is None:
        return jsonify({'error': 'Task tidak ditemukan'}), 404
    
    return jsonify(dict(task))

@app.route('/download/<task_id>')
def download(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    
    if task is None:
        return jsonify({'error': 'Task tidak ditemukan'}), 404
    
    if task['status'] != 'completed':
        return jsonify({'error': 'File belum siap'}), 400
    
    return send_file(
        task['file'],
        as_attachment=True,
        download_name=f"video_{task_id[:8]}.mp4"
    )

# Cleanup old files (run every hour)
def cleanup_old_files():
    while True:
        time.sleep(3600)
        try:
            # Cleanup physical files
            current_time = time.time()
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.getmtime(filepath) < current_time - 3600:
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass
            
            # Cleanup DB entries older than 24 hours
            conn = get_db_connection()
            conn.execute("DELETE FROM tasks WHERE created_at < datetime('now', '-1 day')")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Cleanup error: {e}")

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)
