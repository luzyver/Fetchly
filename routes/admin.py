import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, session
from core.config import CONFIG
from core.database import get_db, get_whitelist, add_to_whitelist, remove_from_whitelist, get_all_usage, DAILY_LIMIT_BYTES

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@login_required
def admin_index():
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.admin_dashboard'))
    
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == CONFIG['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            return redirect(url_for('admin.admin_dashboard'))
        error = 'Invalid password'
    
    return render_template('admin_login.html', error=error)

@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    try:
        with get_db() as conn:
            tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50').fetchall()
            total_tasks = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
            completed_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'").fetchone()[0]
            failed_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'").fetchone()[0]
            processing_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'processing'").fetchone()[0]

        tasks_list = [_format_task(dict(task)) for task in tasks]
        whitelist = get_whitelist()
        usage_data = get_all_usage()
        
        stats = {
            'total': total_tasks,
            'completed': completed_tasks,
            'failed': failed_tasks,
            'processing': processing_tasks,
            'whitelist_count': len(whitelist),
            'active_users': len(usage_data)
        }

        return render_template('admin_dashboard.html', 
                             tasks=tasks_list,
                             whitelist=whitelist,
                             usage_data=usage_data,
                             daily_limit=DAILY_LIMIT_BYTES,
                             stats=stats)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return "Server Error", 500

@admin_bp.route('/admin/delete_task/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    try:
        with get_db() as conn:
            task = conn.execute('SELECT file FROM tasks WHERE id = ?', (task_id,)).fetchone()
            if task and task['file'] and os.path.exists(task['file']):
                try:
                    os.remove(task['file'])
                except OSError:
                    pass
            conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/whitelist/add', methods=['POST'])
@login_required
def add_whitelist():
    try:
        data = request.json
        user_id = data.get('user_id', '').strip()
        note = data.get('note', '').strip()
        if not user_id:
            return jsonify({'error': 'User ID required'}), 400
        add_to_whitelist(user_id, note)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/admin/whitelist/remove/<user_id>', methods=['DELETE'])
@login_required
def remove_whitelist(user_id):
    try:
        remove_from_whitelist(user_id)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _format_task(task):
    if task.get('created_at'):
        try:
            utc_time = datetime.strptime(task['created_at'], '%Y-%m-%d %H:%M:%S')
            local_time = utc_time + timedelta(hours=7)
            task['created_at'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
    return task
