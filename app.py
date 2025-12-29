import time
import logging
from flask import Flask, render_template
from concurrent.futures import ThreadPoolExecutor

from core.config import CONFIG
from core.database import init_db
from core.cleanup import cleanup_old_files
from routes.main import main_bp
from routes.api import api_bp, set_executor as set_api_executor
from routes.convert import convert_bp, set_executor as set_convert_executor
from routes.admin import admin_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)
app.config['CACHE_VERSION'] = str(int(time.time()))


@app.context_processor
def inject_globals():
    return {'cache_version': app.config['CACHE_VERSION']}


init_db()

executor = ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS'])
set_api_executor(executor)
set_convert_executor(executor)

app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(convert_bp)
app.register_blueprint(admin_bp)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('405.html'), 405


executor.submit(cleanup_old_files)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)
