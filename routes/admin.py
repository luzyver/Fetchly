import os
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from core.database import get_db, get_whitelist, add_to_whitelist, remove_from_whitelist, get_all_usage, DAILY_LIMIT_BYTES

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/tasks')
def admin_tasks():
    try:
        with get_db() as conn:
            tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100').fetchall()

        tasks_list = [_format_task(dict(task)) for task in tasks]
        return render_template('admin_tasks.html', tasks=tasks_list)

    except Exception as e:
        logger.error(f"Admin error: {e}")
        return "Server Error", 500


@admin_bp.route('/admin/delete_task/<task_id>', methods=['DELETE'])
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


@admin_bp.route('/admin/whitelist')
def whitelist_page():
    try:
        whitelist = get_whitelist()
        usage_data = get_all_usage()
        return render_template('admin_whitelist.html', 
                             whitelist=whitelist, 
                             usage_data=usage_data,
                             daily_limit=DAILY_LIMIT_BYTES)
    except Exception as e:
        logger.error(f"Whitelist error: {e}")
        return "Server Error", 500


@admin_bp.route('/admin/whitelist/add', methods=['POST'])
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
def remove_whitelist(user_id):
    try:
        remove_from_whitelist(user_id)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/admin/usage')
def usage_page():
    try:
        usage_data = get_all_usage()
        return render_template('admin_usage.html', 
                             usage_data=usage_data, 
                             daily_limit=DAILY_LIMIT_BYTES)
    except Exception as e:
        logger.error(f"Usage page error: {e}")
        return "Server Error", 500


def _format_task(task):
    if task.get('created_at'):
        try:
            utc_time = datetime.strptime(task['created_at'], '%Y-%m-%d %H:%M:%S')
            local_time = utc_time + timedelta(hours=7)
            task['created_at'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
    return task
