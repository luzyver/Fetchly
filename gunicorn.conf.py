import os
import logging
import threading
from logging.handlers import RotatingFileHandler
from core.cleanup import cleanup_old_files

bind = "0.0.0.0:5050"
workers = 3
timeout = 120

cleanup_started = False
cleanup_lock = threading.Lock()


def _setup_logging():
    os.makedirs('logs', exist_ok=True)
    
    handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10*1024*1024,
        backupCount=5
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Setup root logger for cleanup module
    cleanup_logger = logging.getLogger('core.cleanup')
    cleanup_logger.setLevel(logging.INFO)
    cleanup_logger.addHandler(handler)


def on_starting(server):
    global cleanup_started
    with cleanup_lock:
        if not cleanup_started:
            cleanup_started = True
            _setup_logging()
            thread = threading.Thread(target=cleanup_old_files, daemon=True)
            thread.start()
            server.log.info("Cleanup thread started")
