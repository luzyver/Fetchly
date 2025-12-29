import os
import threading
from core.cleanup import cleanup_old_files

bind = "0.0.0.0:5050"
workers = 3
timeout = 120

cleanup_started = False
cleanup_lock = threading.Lock()


def on_starting(server):
    global cleanup_started
    with cleanup_lock:
        if not cleanup_started:
            cleanup_started = True
            thread = threading.Thread(target=cleanup_old_files, daemon=True)
            thread.start()
            server.log.info("Cleanup thread started")
