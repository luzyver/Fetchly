import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple, Any
from core.config import CONFIG

logger = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))
DAILY_LIMIT_BYTES = 1 * 1024 * 1024 * 1024

_SCHEMAS = [
    '''CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY, url TEXT, status TEXT, file TEXT, error TEXT,
        fingerprint TEXT, ip_address TEXT, title TEXT, filesize INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS usage (
        identifier TEXT PRIMARY KEY, id_type TEXT, bytes_used INTEGER DEFAULT 0, last_reset TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS whitelist (
        user_id TEXT PRIMARY KEY, note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
    '''CREATE TABLE IF NOT EXISTS blacklist (
        ip_address TEXT PRIMARY KEY, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''',
]
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_fingerprint ON tasks(fingerprint)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_ip_address ON tasks(ip_address)",
    "CREATE INDEX IF NOT EXISTS idx_usage_identifier ON usage(identifier)",
    "CREATE INDEX IF NOT EXISTS idx_whitelist_user_id ON whitelist(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON blacklist(ip_address)",
]


@contextmanager
def get_db():
    conn = sqlite3.connect(CONFIG['DB_PATH'], timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception as e:
        logger.warning(f"Failed to set PRAGMAs: {e}")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        for schema in _SCHEMAS:
            conn.execute(schema)
        for idx in _INDEXES:
            conn.execute(idx)
        conn.commit()


def _get_today_wib() -> str:
    return datetime.now(WIB).strftime('%Y-%m-%d')


def _to_wib(utc_str: Optional[str]) -> Optional[str]:
    if not utc_str:
        return None
    try:
        utc_time = datetime.strptime(utc_str, '%Y-%m-%d %H:%M:%S')
        wib_time = utc_time + timedelta(hours=7)
        return wib_time.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return utc_str


def update_task_status(task_id: str, status: str, file: str = None, error: str = None) -> None:
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


def update_task_filesize(task_id: str, filesize: int) -> None:
    try:
        with get_db() as conn:
            conn.execute('UPDATE tasks SET filesize = ? WHERE id = ?', (filesize, task_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update filesize for {task_id}: {e}")


def get_task_info(task_id: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        with get_db() as conn:
            row = conn.execute('SELECT fingerprint, ip_address FROM tasks WHERE id = ?', (task_id,)).fetchone()
            return (row['fingerprint'], row['ip_address']) if row else (None, None)
    except Exception:
        return None, None


def _get_usage_single(conn, identifier: str, today: str) -> int:
    row = conn.execute('SELECT bytes_used, last_reset FROM usage WHERE identifier = ?', (identifier,)).fetchone()

    if not row:
        return 0
    if row['last_reset'] != today:
        conn.execute('UPDATE usage SET bytes_used = 0, last_reset = ? WHERE identifier = ?', (today, identifier))
        return 0
    return row['bytes_used']


def get_usage(fingerprint: str, ip: str) -> int:
    today = _get_today_wib()
    with get_db() as conn:
        fp_used = _get_usage_single(conn, fingerprint, today) if fingerprint else 0
        ip_used = _get_usage_single(conn, ip, today) if ip else 0
        conn.commit()
        return max(fp_used, ip_used)


def add_usage(fingerprint: str, ip: str, bytes_count: int) -> None:
    today = _get_today_wib()

    with get_db() as conn:
        for identifier, id_type in [(fingerprint, 'fingerprint'), (ip, 'ip')]:
            if not identifier:
                continue
                
            row = conn.execute('SELECT bytes_used, last_reset FROM usage WHERE identifier = ?', (identifier,)).fetchone()

            if not row:
                conn.execute('INSERT INTO usage (identifier, id_type, bytes_used, last_reset) VALUES (?, ?, ?, ?)',
                           (identifier, id_type, bytes_count, today))
            elif row['last_reset'] != today:
                conn.execute('UPDATE usage SET bytes_used = ?, last_reset = ? WHERE identifier = ?',
                           (bytes_count, today, identifier))
            else:
                conn.execute('UPDATE usage SET bytes_used = bytes_used + ? WHERE identifier = ?',
                           (bytes_count, identifier))
        conn.commit()


def _is_whitelisted_conn(conn, identifier: Optional[str]) -> bool:
    if not identifier:
        return False
    row = conn.execute('SELECT 1 FROM whitelist WHERE user_id = ?', (identifier,)).fetchone()
    return row is not None


def _get_usage_with_conn(conn, fingerprint: str, ip: str) -> int:
    today = _get_today_wib()
    fp_used = _get_usage_single(conn, fingerprint, today) if fingerprint else 0
    ip_used = _get_usage_single(conn, ip, today) if ip else 0
    return max(fp_used, ip_used)


def check_limit(fingerprint: str, ip: str) -> Dict[str, Any]:
    with get_db() as conn:
        whitelisted = _is_whitelisted_conn(conn, fingerprint) or _is_whitelisted_conn(conn, ip)
        if whitelisted:
            return {'allowed': True, 'used': 0, 'limit': DAILY_LIMIT_BYTES, 'remaining': DAILY_LIMIT_BYTES, 'whitelisted': True}

        used = _get_usage_with_conn(conn, fingerprint, ip)
        conn.commit()
        remaining = max(0, DAILY_LIMIT_BYTES - used)
        return {'allowed': used < DAILY_LIMIT_BYTES, 'used': used, 'limit': DAILY_LIMIT_BYTES, 'remaining': remaining}


def set_full_usage(fingerprint: str, ip: str) -> None:
    today = _get_today_wib()

    with get_db() as conn:
        for identifier, id_type in [(fingerprint, 'fingerprint'), (ip, 'ip')]:
            if not identifier:
                continue

            row = conn.execute('SELECT 1 FROM usage WHERE identifier = ?', (identifier,)).fetchone()

            if not row:
                conn.execute('INSERT INTO usage (identifier, id_type, bytes_used, last_reset) VALUES (?, ?, ?, ?)',
                           (identifier, id_type, DAILY_LIMIT_BYTES, today))
            else:
                conn.execute('UPDATE usage SET bytes_used = ?, last_reset = ? WHERE identifier = ?',
                           (DAILY_LIMIT_BYTES, today, identifier))
        conn.commit()
    
    logger.warning(f"Penalty applied: full usage set for fp={fingerprint}, ip={ip}")


def get_user_history(fingerprint: str, ip: str) -> List[Dict]:
    with get_db() as conn:
        rows = conn.execute('''
            SELECT id, title, status, filesize, created_at FROM tasks 
            WHERE fingerprint = ? AND ip_address = ? ORDER BY created_at DESC
        ''', (fingerprint, ip)).fetchall()
        return [dict(row) for row in rows]


def get_all_usage() -> List[Dict]:
    today = _get_today_wib()
    
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT u.identifier, u.id_type, u.bytes_used, u.last_reset,
                    (SELECT COUNT(*) FROM tasks t WHERE (t.fingerprint = u.identifier OR t.ip_address = u.identifier) AND DATE(t.created_at) = ?) as today_downloads,
                    (SELECT COUNT(*) FROM tasks t WHERE t.fingerprint = u.identifier OR t.ip_address = u.identifier) as total_downloads,
                    (SELECT MAX(created_at) FROM tasks t WHERE t.fingerprint = u.identifier OR t.ip_address = u.identifier) as last_activity,
                    (SELECT 1 FROM whitelist w WHERE w.user_id = u.identifier) as is_whitelisted
                FROM usage u ORDER BY u.bytes_used DESC
            ''', (today,)).fetchall()
            
            result = []
            for row in rows:
                data = dict(row)
                data['last_activity'] = _to_wib(data['last_activity'])
                result.append(data)
            return result
    except Exception as e:
        logger.error(f"Failed to get all usage: {e}")
        return []


def is_whitelisted(identifier: Optional[str]) -> bool:
    if not identifier:
        return False
    try:
        with get_db() as conn:
            row = conn.execute('SELECT 1 FROM whitelist WHERE user_id = ?', (identifier,)).fetchone()
            return row is not None
    except Exception:
        return False


def get_whitelist() -> List[Dict]:
    try:
        with get_db() as conn:
            rows = conn.execute('SELECT user_id, note, created_at FROM whitelist ORDER BY created_at DESC').fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def add_to_whitelist(user_id: str, note: str = '') -> None:
    try:
        with get_db() as conn:
            conn.execute('INSERT OR REPLACE INTO whitelist (user_id, note) VALUES (?, ?)', (user_id, note))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to add to whitelist: {e}")


def remove_from_whitelist(user_id: str) -> None:
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM whitelist WHERE user_id = ?', (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to remove from whitelist: {e}")


def is_blacklisted(ip: Optional[str]) -> bool:
    if not ip:
        return False
    try:
        with get_db() as conn:
            row = conn.execute('SELECT 1 FROM blacklist WHERE ip_address = ?', (ip,)).fetchone()
            return row is not None
    except Exception:
        return False


def get_blacklist() -> List[Dict]:
    try:
        with get_db() as conn:
            rows = conn.execute('SELECT ip_address, reason, created_at FROM blacklist ORDER BY created_at DESC').fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def add_to_blacklist(ip: str, reason: str = '') -> None:
    try:
        with get_db() as conn:
            conn.execute('INSERT OR REPLACE INTO blacklist (ip_address, reason) VALUES (?, ?)', (ip, reason))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to add to blacklist: {e}")


def remove_from_blacklist(ip: str) -> None:
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM blacklist WHERE ip_address = ?', (ip,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to remove from blacklist: {e}")
