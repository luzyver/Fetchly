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

def convert_m3u8(task_id, url, output_path, referer=None, cookies=None):
    """Convert M3U8 to MP4 using yt-dlp with Smart Retry (Desktop then Mobile UA)"""
    logger.info(f"Starting conversion for task {task_id}")
    try:
        update_task_status(task_id, 'processing')
        
        # User Agents to try
        user_agents = [
            # Desktop (Default)
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Mobile (Fallback)
            'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        ]
        
        # Parse domain for default referer
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        current_referer = referer if referer else domain
        
        success = False
        last_error = None

        for i, ua in enumerate(user_agents):
            try:
                # Build yt-dlp command
                cmd = [
                    'yt-dlp',
                    '--user-agent', ua,
                    '--add-header', f'Referer: {current_referer}',
                    '--add-header', f'Origin: {domain}',
                    '--no-check-certificate',
                    '--no-playlist',     # Just download the single video
                    '-o', output_path,   # Output file
                    url
                ]
                
                # Pass Cookies if available
                if cookies:
                    cmd.extend(['--add-header', f'Cookie: {cookies}'])
                
                logger.info(f"Task {task_id}: Running yt-dlp (Attempt {i+1}) with Referer: {current_referer} and UA: {'Mobile' if 'Mobile' in ua else 'Desktop'}")
                
                 # Run yt-dlp
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    update_task_status(task_id, 'completed', file=output_path)
                    logger.info(f"Task {task_id}: Conversion successful")
                    success = True
                    break
                else:
                    error_msg = stderr.decode()
                    logger.warning(f"Task {task_id}: Attempt {i+1} failed. Error: {error_msg[-200:]}")
                    last_error = error_msg[-200:]
                    continue
                    
            except Exception as e:
                logger.error(f"Task {task_id}: Attempt {i+1} error: {e}")
                last_error = str(e)
                continue
        
        if not success:
            logger.error(f"Task {task_id}: All attempts failed")
            update_task_status(task_id, 'failed', error=f"Download failed after {len(user_agents)} attempts: {last_error}")
            
    except Exception as e:
        logger.error(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))

def cleanup_old_files():
    """Background task to clean up old files and DB entries"""
    while True:
        try:
            time.sleep(86400)  # Check every 24 hours
            logger.info("Running cleanup task")
            
            # 1. Delete physical files older than 24 hours
            cutoff_time = time.time() - 86400
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

# ... imports ...
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

# ... existing code ...

def resolve_source_url(url):
    """Resolve m3u8 URL from a source page using Headless Chrome (Generic)"""
    logger.info(f"Resolving source URL: {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Explicitly set path for ARM64/System installed driver
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for initial load
        
        # 1. Search for potential embed iframes if no M3U8 found in top source
        page_source = driver.page_source
        m3u8_matches = re.findall(r'(https?://[^"\']+\.m3u8)', page_source)
        
        if m3u8_matches:
            found_url = m3u8_matches[0]
            cookies = driver.get_cookies()
            cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            logger.info(f"Resolved m3u8: {found_url}")
            return found_url, cookies_str
            
        # If not found, look for likely video iframes (generic)
        target_src = url
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            src = iframe.get_attribute("src")
            # Heuristic: iframes with 'embed', 'video', 'stream', or 'player' in URL
            if src and any(k in src.lower() for k in ['embed', 'video', 'stream', 'player', 'id']):
                target_src = src
                logger.info(f"Found candidate iframe: {target_src}")
                break
        
        if target_src != url:
            driver.get(target_src)
            time.sleep(5)
            
            # Re-check for M3U8 in the iframe
            page_source = driver.page_source
            m3u8_matches = re.findall(r'(https?://[^"\']+\.m3u8)', page_source)
            if m3u8_matches:
                found_url = m3u8_matches[0]
                cookies = driver.get_cookies()
                cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                logger.info(f"Resolved m3u8 in iframe: {found_url}")
                return found_url, cookies_str

        # 3. JWPlayer fallback (generic)
        try:
             jw_url = driver.execute_script("return jwplayer().getPlaylist()[0].file")
             if jw_url:
                 # Handle relative URLs
                 if not jw_url.startswith('http'):
                     from urllib.parse import urljoin
                     jw_url = urljoin(target_src, jw_url)
                 
                 # Capture cookies
                 cookies = driver.get_cookies()
                 cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                 
                 logger.info(f"Resolved via JWPlayer: {jw_url}")
                 return jw_url, cookies_str
        except:
             pass
             
        raise Exception("No m3u8 found on the page")
        
    except Exception as e:
        logger.error(f"Resolution failed: {e}")
        raise
    finally:
        driver.quit()

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url', '').strip()
    # Referer is now strictly the source URL, we assume generic behavior
    
    if not url:
        return jsonify({'error': 'URL tidak boleh kosong'}), 400
    
    # Auto-resolve if not m3u8
    resolved_url = url
    cookies = None
    
    # Use the input URL as the referer for the conversion process
    referer = url
    
    if not (url.lower().endswith('.m3u8') or '.m3u8' in url.lower()):
        try:
            resolved_url, cookies = resolve_source_url(url)
        except Exception as e:
            return jsonify({'error': f'Gagal mengambil video dari URL: {str(e)}'}), 400
    
    task_id = str(uuid.uuid4())
    filename = f"{task_id}.mp4"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    try:
        with closing(get_db_connection()) as conn:
            conn.execute('INSERT INTO tasks (id, url, status) VALUES (?, ?, ?)',
                         (task_id, resolved_url, 'queued'))
            conn.commit()
            
        # Submit to thread pool
        # We use the original 'url' as the referer since that's the page the user visited
        executor.submit(convert_m3u8, task_id, resolved_url, output_path, referer, cookies)
        
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

@app.route('/admin/tasks')
def admin_tasks():
    try:
        with closing(get_db_connection()) as conn:
            tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC').fetchall()
        return render_template('admin_tasks.html', tasks=tasks)
    except Exception as e:
        logger.error(f"Admin view error: {e}")
        return "Database error", 500

@app.route('/admin/delete_task/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        with closing(get_db_connection()) as conn:
            # Get file path first
            task = conn.execute('SELECT file FROM tasks WHERE id = ?', (task_id,)).fetchone()
            
            if task and task['file'] and os.path.exists(task['file']):
                try:
                    os.remove(task['file'])
                    logger.info(f"Deleted file for task {task_id}")
                except OSError as e:
                    logger.warning(f"Failed to delete file for task {task_id}: {e}")

            # Delete DB entry
            conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()
            
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Delete task error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)