import os
import time
import logging
from core.config import CONFIG
from core.database import get_db

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = ('.mp4', '.mp3')


def cleanup_old_files():
    is_first_run = True

    while True:
        _wait(is_first_run)
        is_first_run = False

        try:
            logger.info("Running cleanup task...")
            files_deleted = _cleanup_files()
            db_deleted = _cleanup_database()
            logger.info(f"Cleanup complete: {files_deleted} files, {db_deleted} DB records deleted")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


def _wait(is_first_run):
    delay = 5 if is_first_run else CONFIG['CLEANUP_INTERVAL']
    time.sleep(delay)


def _cleanup_files():
    cutoff_time = time.time() - CONFIG['RETENTION_PERIOD']
    deleted = 0

    for filename in os.listdir(CONFIG['DOWNLOAD_FOLDER']):
        if not filename.endswith(ALLOWED_EXTENSIONS):
            continue

        filepath = os.path.join(CONFIG['DOWNLOAD_FOLDER'], filename)
        try:
            if os.path.getmtime(filepath) < cutoff_time:
                os.remove(filepath)
                logger.info(f"Deleted: {filename}")
                deleted += 1
        except OSError as e:
            logger.warning(f"Error deleting {filename}: {e}")

    return deleted


def _cleanup_database():
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE created_at < datetime('now', '-1 day')")
        deleted = cursor.rowcount
        conn.commit()
    return deleted
