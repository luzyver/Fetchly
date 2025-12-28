import sqlite3
from contextlib import contextmanager
from core.config import CONFIG
import logging

logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    conn = sqlite3.connect(CONFIG['DB_PATH'])
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                url TEXT,
                status TEXT,
                file TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def update_task_status(task_id, status, file=None, error=None):
    try:
        with get_db() as conn:
            update_fields = ["status = ?"]
            params = [status]
            
            if file:
                update_fields.append("file = ?")
                params.append(file)
            if error:
                update_fields.append("error = ?")
                params.append(error)
                
            params.append(task_id)
            query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
