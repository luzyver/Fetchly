import os
import time
import logging
import threading
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

    init_db()

    executor = ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS'])
    set_api_executor(executor)
    set_convert_executor(executor)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(convert_bp)
    app.register_blueprint(admin_bp)

    _register_middleware(app)
    _register_error_handlers(app)

    return app


def _register_middleware(app: Flask) -> None:
    @app.before_request
    def check_blacklist():
        if request.path.startswith('/admin') or request.path.startswith('/static'):
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


app = create_app()


if __name__ == '__main__':
    from core.cleanup import cleanup_old_files
    
    thread = threading.Thread(target=cleanup_old_files, daemon=True)
    thread.start()
    
    app.run(debug=False, host='0.0.0.0', port=5050)
