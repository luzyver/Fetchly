import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from core.config import CONFIG

logger = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))
DAILY_LIMIT_BYTES = 1 * 1024 * 1024 * 1024

SCHEMA = '''
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        url TEXT,
        status TEXT,
        file TEXT,
        error TEXT,
        fingerprint TEXT,
        title TEXT,
        filesize INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
'''

USAGE_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS usage (
        fingerprint TEXT PRIMARY KEY,
        bytes_used INTEGER DEFAULT 0,
        last_reset TEXT
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
        conn.execute(USAGE_SCHEMA)
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


def _get_today_wib():
    return datetime.now(WIB).strftime('%Y-%m-%d')


def get_usage(fingerprint):
    today = _get_today_wib()

    with get_db() as conn:
        row = conn.execute(
            'SELECT bytes_used, last_reset FROM usage WHERE fingerprint = ?',
            (fingerprint,)
        ).fetchone()

        if not row:
            return 0

        if row['last_reset'] != today:
            conn.execute(
                'UPDATE usage SET bytes_used = 0, last_reset = ? WHERE fingerprint = ?',
                (today, fingerprint)
            )
            conn.commit()
            return 0

        return row['bytes_used']


def add_usage(fingerprint, bytes_count):
    today = _get_today_wib()

    with get_db() as conn:
        row = conn.execute(
            'SELECT bytes_used, last_reset FROM usage WHERE fingerprint = ?',
            (fingerprint,)
        ).fetchone()

        if not row:
            conn.execute(
                'INSERT INTO usage (fingerprint, bytes_used, last_reset) VALUES (?, ?, ?)',
                (fingerprint, bytes_count, today)
            )
        elif row['last_reset'] != today:
            conn.execute(
                'UPDATE usage SET bytes_used = ?, last_reset = ? WHERE fingerprint = ?',
                (bytes_count, today, fingerprint)
            )
        else:
            conn.execute(
                'UPDATE usage SET bytes_used = bytes_used + ? WHERE fingerprint = ?',
                (bytes_count, fingerprint)
            )
        conn.commit()


def check_limit(fingerprint):
    used = get_usage(fingerprint)
    remaining = max(0, DAILY_LIMIT_BYTES - used)
    return {
        'allowed': used < DAILY_LIMIT_BYTES,
        'used': used,
        'limit': DAILY_LIMIT_BYTES,
        'remaining': remaining
    }


def get_user_history(fingerprint):
    today = _get_today_wib()

    with get_db() as conn:
        rows = conn.execute('''
            SELECT id, title, status, filesize, created_at 
            FROM tasks 
            WHERE fingerprint = ? AND DATE(created_at) = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (fingerprint, today)).fetchall()

        return [dict(row) for row in rows]


def update_task_filesize(task_id, filesize):
    try:
        with get_db() as conn:
            conn.execute(
                'UPDATE tasks SET filesize = ? WHERE id = ?',
                (filesize, task_id)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update filesize for {task_id}: {e}")


def get_task_fingerprint(task_id):
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT fingerprint FROM tasks WHERE id = ?',
                (task_id,)
            ).fetchone()
            return row['fingerprint'] if row else None
    except Exception:
        return None
