import os
import time
import threading
import logging
from typing import Tuple
from core.config import CONFIG
from core.database import get_db

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = ('.mp4', '.mp3')


def cleanup_old_files(stop_event: threading.Event) -> None:
    """Run periodic cleanup until the provided event is set."""
    is_first_run = True

    while not stop_event.is_set():
        delay = 5 if is_first_run else CONFIG['CLEANUP_INTERVAL']
        # Wait returns True if the event is set during the sleep period
        if stop_event.wait(delay):
            break
        is_first_run = False

        try:
            logger.info("Running cleanup task...")
            files_deleted, db_deleted = _run_cleanup()
            logger.info(f"Cleanup complete: {files_deleted} files, {db_deleted} DB records deleted")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


def start_cleanup_thread(stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(target=cleanup_old_files, args=(stop_event,), daemon=True)
    thread.start()
    return thread


def _run_cleanup() -> Tuple[int, int]:
    return _cleanup_files(), _cleanup_database()


def _cleanup_files() -> int:
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


def _cleanup_database() -> int:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE created_at < datetime('now', '-1 day')")
        deleted = cursor.rowcount
        conn.commit()
    return deleted
