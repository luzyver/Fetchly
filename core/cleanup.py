import os
import time
import logging
from core.config import CONFIG
from core.database import get_db

logger = logging.getLogger(__name__)

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
