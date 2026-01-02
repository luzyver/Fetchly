import os
import time
import logging
import threading
import atexit
import signal
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, abort

from core.config import CONFIG
from core.database import init_db, is_blacklisted
from routes.main import main_bp
from routes.api import api_bp, set_executor as set_api_executor
from routes.convert import convert_bp, set_executor as set_convert_executor
from routes.admin import admin_bp
from routes.helpers import get_client_ip
from core.cleanup import start_cleanup_thread


def create_app() -> Flask:
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler('logs/app.log', maxBytes=10*1024*1024, backupCount=3)
        ]
    )

    app = Flask(__name__)
    app.secret_key = CONFIG['SECRET_KEY']
    app.config['CACHE_VERSION'] = str(int(time.time()))

    _warn_insecure_config()

    init_db()

    executor = ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS'])
    app.config['EXECUTOR'] = executor
    set_api_executor(executor)
    set_convert_executor(executor)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(convert_bp)
    app.register_blueprint(admin_bp)

    _register_middleware(app)
    _register_error_handlers(app)
    _register_shutdown_hooks(app, executor)

    return app


def _register_middleware(app: Flask) -> None:
    @app.before_request
    def check_blacklist():
        if request.path.startswith('/static'):
            return None
        ip = get_client_ip()
        if is_blacklisted(ip):
            abort(403)

    @app.context_processor
    def inject_globals():
        return {'cache_version': app.config['CACHE_VERSION']}


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return render_template('405.html'), 405

    @app.route('/blocked')
    def blocked_page():
        return render_template('403.html'), 403

    @app.route('/devtools')
    def devtools_page():
        return render_template('devtools.html'), 200


def _register_shutdown_hooks(app: Flask, executor: ThreadPoolExecutor) -> None:
    shutdown_flag = {'done': False}

    def shutdown_executor():
        if shutdown_flag['done']:
            return
        shutdown_flag['done'] = True
        try:
            executor.shutdown(wait=False, cancel_futures=True)
            logging.getLogger(__name__).info("ThreadPoolExecutor shut down.")
        except Exception as exc:
            logging.getLogger(__name__).warning(f"Failed to shutdown executor cleanly: {exc}")

    atexit.register(shutdown_executor)
    app.config['EXECUTOR_SHUTDOWN'] = shutdown_executor


def _warn_insecure_config() -> None:
    if CONFIG['SECRET_KEY'] == 'change-me-in-production':
        logging.getLogger(__name__).warning("SECRET_KEY is using the default value. Change it in production.")
    if CONFIG['ADMIN_PASSWORD'] == 'admin123':
        logging.getLogger(__name__).warning("ADMIN_PASSWORD is using the default value. Change it in production.")


app = create_app()


if __name__ == '__main__':
    stop_event = threading.Event()
    cleanup_thread = start_cleanup_thread(stop_event)

    def _handle_exit(*_args):
        stop_event.set()
        cleanup_thread.join(timeout=5)
        logging.getLogger(__name__).info("Cleanup thread stopped.")
        shutdown_cb = app.config.get('EXECUTOR_SHUTDOWN')
        if shutdown_cb:
            shutdown_cb()

    signal.signal(signal.SIGTERM, _handle_exit)
    signal.signal(signal.SIGINT, _handle_exit)
    
    app.run(debug=False, host='0.0.0.0', port=5050)
