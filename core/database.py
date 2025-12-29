import sqlite3
import logging
from contextlib import contextmanager
from core.config import CONFIG

logger = logging.getLogger(__name__)

SCHEMA = '''
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        url TEXT,
        status TEXT,
        file TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
'''


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
        conn.execute(SCHEMA)
        conn.commit()


def update_task_status(task_id, status, file=None, error=None):
    try:
        updates = {'status': status}
        if file:
            updates['file'] = file
        if error:
            updates['error'] = error

        fields = ', '.join(f"{k} = ?" for k in updates.keys())
        params = list(updates.values()) + [task_id]

        with get_db() as conn:
            conn.execute(f"UPDATE tasks SET {fields} WHERE id = ?", params)
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
