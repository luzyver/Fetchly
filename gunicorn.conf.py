import os
import logging
import threading
from logging.handlers import RotatingFileHandler

bind = "0.0.0.0:5050"
workers = 3
timeout = 120
preload_app = False

_cleanup_started = False


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
    
    cleanup_logger = logging.getLogger('core.cleanup')
    cleanup_logger.setLevel(logging.INFO)
    cleanup_logger.addHandler(handler)


def when_ready(server):
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True
    
    _setup_logging()
    
    from core.cleanup import cleanup_old_files
    thread = threading.Thread(target=cleanup_old_files, daemon=True)
    thread.start()
    server.log.info("Cleanup thread started in master process")
