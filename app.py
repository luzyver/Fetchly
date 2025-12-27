import shutil
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
from contextlib import closing, contextmanager
from urllib.parse import urlparse, urljoin

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CONFIG = {
    'DOWNLOAD_FOLDER': 'downloads',
    'DB_PATH': os.path.join('downloads', 'tasks.db'),
    'MAX_WORKERS': 4,
    'CLEANUP_INTERVAL': 86400,
    'RETENTION_PERIOD': 86400,
}

USER_AGENTS = {
    'DESKTOP': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'MOBILE': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
}

os.makedirs(CONFIG['DOWNLOAD_FOLDER'], exist_ok=True)

executor = ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS'])

@contextmanager
def get_db():
    conn = sqlite3.connect(CONFIG['DB_PATH'])
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute('''
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

def update_task_status(task_id, status, file=None, error=None):
    try:
        with get_db() as conn:
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
            conn.execute(query, params)
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")

def convert_m3u8(task_id, url, output_path, referer=None, cookies=None):
    logger.info(f"Task {task_id}: Starting conversion for {url}")
    try:
        update_task_status(task_id, 'processing')
        
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        current_referer = referer if referer else domain
        
        agents_to_try = [USER_AGENTS['DESKTOP'], USER_AGENTS['MOBILE']]
        success = False
        last_error = None

        for i, ua in enumerate(agents_to_try):
            try:
                cmd = [
                    'yt-dlp',
                    '--user-agent', ua,
                    '--add-header', f'Referer: {current_referer}',
                    '--add-header', f'Origin: {domain}',
                    '--no-check-certificate',
                    '--no-playlist',
                    '--concurrent-fragments', '4',
                    '-o', output_path,
                    url
                ]
                
                if cookies:
                    cmd.extend(['--add-header', f'Cookie: {cookies}'])
                
                logger.info(f"Task {task_id}: Attempt {i+1}/{len(agents_to_try)} (UA: {'Mobile' if 'Mobile' in ua else 'Desktop'})")
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    update_task_status(task_id, 'completed', file=output_path)
                    logger.info(f"Task {task_id}: Conversion successful")
                    success = True
                    break
                else:
                    error_msg = stderr.decode().strip()
                    last_error = error_msg[-300:]
                    logger.warning(f"Task {task_id}: Attempt {i+1} failed. Error: {last_error}")
                    
            except Exception as e:
                logger.error(f"Task {task_id}: Attempt {i+1} exception: {e}")
                last_error = str(e)

        if not success:
            logger.error(f"Task {task_id}: All attempts failed")
            update_task_status(task_id, 'failed', error=f"Failed: {last_error}")
            
    except Exception as e:
        logger.critical(f"Task {task_id}: Critical error: {e}")
        update_task_status(task_id, 'failed', error=str(e))

def cleanup_old_files():
    while True:
        try:
            time.sleep(CONFIG['CLEANUP_INTERVAL'])
            logger.info("Running cleanup task...")
            
            cutoff_time = time.time() - CONFIG['RETENTION_PERIOD']
            
            for filename in os.listdir(CONFIG['DOWNLOAD_FOLDER']):
                if filename.endswith('.mp4'):
                    filepath = os.path.join(CONFIG['DOWNLOAD_FOLDER'], filename)
                    if os.path.getmtime(filepath) < cutoff_time:
                        try:
                            os.remove(filepath)
                            logger.info(f"Deleted old file: {filename}")
                        except OSError as e:
                            logger.warning(f"Error deleting {filename}: {e}")

            with get_db() as conn:
                conn.execute("DELETE FROM tasks WHERE created_at < datetime('now', '-1 day')")
                conn.commit()
                
        except Exception as e:
            logger.error(f"Cleanup loop error: {e}")

executor.submit(cleanup_old_files)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

def get_chromedriver_path():
    if os.path.exists("/usr/bin/chromedriver"):
        return "/usr/bin/chromedriver"
    path = shutil.which("chromedriver")
    if path:
        return path
    return None

def resolve_source_url(url):
    logger.info(f"Resolving source URL: {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
    chrome_options.add_argument(f"user-agent={USER_AGENTS['DESKTOP']}")
    
    driver_path = get_chromedriver_path()
    service = Service(driver_path) if driver_path else None
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(3)
        
        page_source = driver.page_source
        m3u8_matches = re.findall(r'(https?://[^"\\]+\.m3u8)', page_source)
        
        def extract_cookies(drv):
            return "; ".join([f"{c['name']}={c['value']}" for c in drv.get_cookies()])

        if m3u8_matches:
            return m3u8_matches[0], extract_cookies(driver)
            
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_src = None
        
        for iframe in iframes:
            src = iframe.get_attribute("src")
            if src and any(k in src.lower() for k in ['embed', 'video', 'stream', 'player', 'id']):
                target_src = src
                break
        
        if target_src and target_src != url:
            logger.info(f"Checking iframe: {target_src}")
            driver.get(target_src)
            time.sleep(3)
            
            m3u8_matches = re.findall(r'(https?://[^"\\]+\.m3u8)', driver.page_source)
            if m3u8_matches:
                return m3u8_matches[0], extract_cookies(driver)

        try:
             jw_url = driver.execute_script("return (window.jwplayer && window.jwplayer().getPlaylist) ? window.jwplayer().getPlaylist()[0].file : null")
             if jw_url:
                 if not jw_url.startswith('http'):
                     jw_url = urljoin(driver.current_url, jw_url)
                 return jw_url, extract_cookies(driver)
        except Exception:
             pass
             
        raise Exception("No usable M3U8 stream found.")
        
    except Exception as e:
        logger.error(f"Resolution failed for {url}: {e}")
        raise
    finally:
        try:
            driver.quit()
        except:
            pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    resolved_url = url
    cookies = None
    referer = url 
    
    if '.m3u8' not in url.lower():
        try:
            resolved_url, cookies = resolve_source_url(url)
            logger.info(f"Resolved to: {resolved_url}")
        except Exception as e:
            return jsonify({'error': f'Could not fetch video: {str(e)}'}), 400
    
    task_id = str(uuid.uuid4())
    filename = f"{task_id}.mp4"
    output_path = os.path.join(CONFIG['DOWNLOAD_FOLDER'], filename)
    
    try:
        with get_db() as conn:
            conn.execute('INSERT INTO tasks (id, url, status) VALUES (?, ?, ?)',
                         (task_id, resolved_url, 'queued'))
            conn.commit()
            
        executor.submit(convert_m3u8, task_id, resolved_url, output_path, referer, cookies)
        return jsonify({'task_id': task_id})
        
    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({'error': 'Server Error'}), 500

@app.route('/status/<task_id>')
def status(task_id):
    try:
        with get_db() as conn:
            task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify(dict(task))
    except Exception:
        return jsonify({'error': 'Database error'}), 500

@app.route('/download/<task_id>')
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

        return send_file(
            task['file'],
            as_attachment=True,
            download_name=f"video_{task_id[:8]}.mp4"
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return jsonify({'error': 'Download failed'}), 500

@app.route('/admin/tasks')
def admin_tasks():
    try:
        with get_db() as conn:
            tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100').fetchall()
        return render_template('admin_tasks.html', tasks=tasks)
    except Exception as e:
        logger.error(f"Admin error: {e}")
        return "Server Error", 500

@app.route('/admin/delete_task/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        with get_db() as conn:
            task = conn.execute('SELECT file FROM tasks WHERE id = ?', (task_id,)).fetchone()
            
            if task and task['file'] and os.path.exists(task['file']):
                try:
                    os.remove(task['file'])
                except OSError:
                    pass

            conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()
            
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)
