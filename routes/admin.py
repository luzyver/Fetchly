import os
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify
from core.database import get_db

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/tasks')
def admin_tasks():
    try:
        with get_db() as conn:
            tasks = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100').fetchall()
        
        tasks_list = []
        for task in tasks:
            task_dict = dict(task)
            if task_dict.get('created_at'):
                try:
                    utc_time = datetime.strptime(task_dict['created_at'], '%Y-%m-%d %H:%M:%S')
                    local_time = utc_time + timedelta(hours=7)
                    task_dict['created_at'] = local_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            tasks_list.append(task_dict)
        
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