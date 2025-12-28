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
    'CLEANUP_INTERVAL': 3600,
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

def convert_m3u8(task_id, url, output_path, referer=None, cookies=None, format_id=None):
    logger.info(f"Task {task_id}: Starting conversion for {url} (format: {format_id or 'best'})")
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
                ]
                
                if format_id and format_id != 'best':
                    cmd.extend(['-f', format_id])
                
                cmd.append(url)
                
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
    first_run = True
    while True:
        try:
            if not first_run:
                time.sleep(CONFIG['CLEANUP_INTERVAL'])
            else:
                first_run = False
                time.sleep(5)
            
            logger.info("Running cleanup task...")
            
            cutoff_time = time.time() - CONFIG['RETENTION_PERIOD']
            deleted_count = 0
            
            for filename in os.listdir(CONFIG['DOWNLOAD_FOLDER']):
                if filename.endswith('.mp4'):
                    filepath = os.path.join(CONFIG['DOWNLOAD_FOLDER'], filename)
                    try:
                        if os.path.getmtime(filepath) < cutoff_time:
                            os.remove(filepath)
                            logger.info(f"Deleted old file: {filename}")
                            deleted_count += 1
                    except OSError as e:
                        logger.warning(f"Error deleting {filename}: {e}")

            with get_db() as conn:
                cursor = conn.execute("DELETE FROM tasks WHERE created_at < datetime('now', '-1 day')")
                db_deleted = cursor.rowcount
                conn.commit()
            
            logger.info(f"Cleanup complete: {deleted_count} files, {db_deleted} DB records deleted")
                
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

@app.route('/fetch-formats', methods=['POST'])
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
    
    if '.m3u8' not in url.lower():
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
        
        import json

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
                
                if cookies:
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
            return jsonify({'error': f'Failed to fetch formats: {last_error}'}), 400
        
        video_info = json.loads(stdout.decode())
        
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
            
            formats.append({
                'format_id': format_id,
                'resolution': resolution,
                'height': height,
                'width': width,
                'ext': ext,
                'filesize': size_str,
                'bitrate': f"{int(tbr)}kbps" if tbr else "",
                'has_audio': acodec != 'none'
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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('405.html'), 405

@app.route('/convert', methods=['POST'])
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
            
        executor.submit(convert_m3u8, task_id, resolved_url, output_path, referer, cookies, format_id)
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
        
        tasks_list = []
        for task in tasks:
            task_dict = dict(task)
            if task_dict.get('created_at'):
                try:
                    utc_time = datetime.strptime(task_dict['created_at'], '%Y-%m-%d %H:%M:%S')
                    local_time = utc_time + timedelta(hours=7)
                    task_dict['created_at'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            tasks_list.append(task_dict)
        
        return render_template('admin_tasks.html', tasks=tasks_list)
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