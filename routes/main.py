import os
from flask import Blueprint, render_template, jsonify
from core.config import CONFIG
from core.database import get_db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/health')
def health():
    status = {'db': False, 'downloads_writable': False}

    try:
        with get_db() as conn:
            conn.execute('SELECT 1')
        status['db'] = True
    except Exception:
        status['db'] = False

    status['downloads_writable'] = os.access(CONFIG['DOWNLOAD_FOLDER'], os.W_OK)

    ok = status['db'] and status['downloads_writable']
    return jsonify({'ok': ok, **status}), 200 if ok else 503
