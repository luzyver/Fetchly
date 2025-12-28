import subprocess
import logging
from urllib.parse import urlparse
from core.config import USER_AGENTS
from core.database import update_task_status

logger = logging.getLogger(__name__)

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
