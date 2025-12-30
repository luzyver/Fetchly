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
        ip_address TEXT,
        title TEXT,
        filesize INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
'''

USAGE_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS usage (
        identifier TEXT PRIMARY KEY,
        id_type TEXT,
        bytes_used INTEGER DEFAULT 0,
        last_reset TEXT
    )
'''

WHITELIST_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS whitelist (
        user_id TEXT PRIMARY KEY,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
'''

ABUSE_SCHEMA = '''
    CREATE TABLE IF NOT EXISTS abuse_attempts (
        identifier TEXT PRIMARY KEY,
        attempts INTEGER DEFAULT 0,
        last_attempt TEXT
    )
'''

MAX_ABUSE_ATTEMPTS = 3


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
        conn.execute(WHITELIST_SCHEMA)
        conn.execute(ABUSE_SCHEMA)
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


def _get_usage_single(conn, identifier):
    today = _get_today_wib()
    row = conn.execute(
        'SELECT bytes_used, last_reset FROM usage WHERE identifier = ?',
        (identifier,)
    ).fetchone()

    if not row:
        return 0

    if row['last_reset'] != today:
        conn.execute(
            'UPDATE usage SET bytes_used = 0, last_reset = ? WHERE identifier = ?',
            (today, identifier)
        )
        return 0

    return row['bytes_used']


def get_usage(fingerprint, ip):
    with get_db() as conn:
        fp_used = _get_usage_single(conn, fingerprint) if fingerprint else 0
        ip_used = _get_usage_single(conn, ip) if ip else 0
        conn.commit()
        return max(fp_used, ip_used)


def add_usage(fingerprint, ip, bytes_count):
    today = _get_today_wib()

    with get_db() as conn:
        for identifier, id_type in [(fingerprint, 'fingerprint'), (ip, 'ip')]:
            if not identifier:
                continue
                
            row = conn.execute(
                'SELECT bytes_used, last_reset FROM usage WHERE identifier = ?',
                (identifier,)
            ).fetchone()

            if not row:
                conn.execute(
                    'INSERT INTO usage (identifier, id_type, bytes_used, last_reset) VALUES (?, ?, ?, ?)',
                    (identifier, id_type, bytes_count, today)
                )
            elif row['last_reset'] != today:
                conn.execute(
                    'UPDATE usage SET bytes_used = ?, last_reset = ? WHERE identifier = ?',
                    (bytes_count, today, identifier)
                )
            else:
                conn.execute(
                    'UPDATE usage SET bytes_used = bytes_used + ? WHERE identifier = ?',
                    (bytes_count, identifier)
                )
        conn.commit()


def check_limit(fingerprint, ip):
    if is_whitelisted(fingerprint) or is_whitelisted(ip):
        return {
            'allowed': True,
            'used': 0,
            'limit': DAILY_LIMIT_BYTES,
            'remaining': DAILY_LIMIT_BYTES,
            'whitelisted': True
        }

    used = get_usage(fingerprint, ip)
    remaining = max(0, DAILY_LIMIT_BYTES - used)
    return {
        'allowed': used < DAILY_LIMIT_BYTES,
        'used': used,
        'limit': DAILY_LIMIT_BYTES,
        'remaining': remaining
    }


def record_abuse_attempt(fingerprint, ip):
    """Record an abuse attempt. Returns True if user should be penalized (3+ attempts)."""
    today = _get_today_wib()
    should_penalize = False

    with get_db() as conn:
        for identifier in [fingerprint, ip]:
            if not identifier:
                continue

            row = conn.execute(
                'SELECT attempts, last_attempt FROM abuse_attempts WHERE identifier = ?',
                (identifier,)
            ).fetchone()

            if not row:
                conn.execute(
                    'INSERT INTO abuse_attempts (identifier, attempts, last_attempt) VALUES (?, 1, ?)',
                    (identifier, today)
                )
            elif row['last_attempt'] != today:
                # Reset for new day
                conn.execute(
                    'UPDATE abuse_attempts SET attempts = 1, last_attempt = ? WHERE identifier = ?',
                    (today, identifier)
                )
            else:
                new_attempts = row['attempts'] + 1
                conn.execute(
                    'UPDATE abuse_attempts SET attempts = ? WHERE identifier = ?',
                    (new_attempts, identifier)
                )
                if new_attempts >= MAX_ABUSE_ATTEMPTS:
                    should_penalize = True

        conn.commit()

    return should_penalize


def set_full_usage(fingerprint, ip):
    """Set user's usage to full daily limit as penalty."""
    today = _get_today_wib()

    with get_db() as conn:
        for identifier, id_type in [(fingerprint, 'fingerprint'), (ip, 'ip')]:
            if not identifier:
                continue

            row = conn.execute(
                'SELECT 1 FROM usage WHERE identifier = ?',
                (identifier,)
            ).fetchone()

            if not row:
                conn.execute(
                    'INSERT INTO usage (identifier, id_type, bytes_used, last_reset) VALUES (?, ?, ?, ?)',
                    (identifier, id_type, DAILY_LIMIT_BYTES, today)
                )
            else:
                conn.execute(
                    'UPDATE usage SET bytes_used = ?, last_reset = ? WHERE identifier = ?',
                    (DAILY_LIMIT_BYTES, today, identifier)
                )

        conn.commit()
    
    logger.warning(f"Penalty applied: full usage set for fp={fingerprint}, ip={ip}")


def get_user_history(fingerprint, ip):
    today = _get_today_wib()

    with get_db() as conn:
        rows = conn.execute('''
            SELECT id, title, status, filesize, created_at 
            FROM tasks 
            WHERE fingerprint = ? AND ip_address = ? AND DATE(created_at) = ?
            ORDER BY created_at DESC
            LIMIT 100
        ''', (fingerprint, ip, today)).fetchall()

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


def get_task_info(task_id):
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT fingerprint, ip_address FROM tasks WHERE id = ?',
                (task_id,)
            ).fetchone()
            if row:
                return row['fingerprint'], row['ip_address']
            return None, None
    except Exception:
        return None, None


def is_whitelisted(identifier):
    if not identifier:
        return False
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT 1 FROM whitelist WHERE user_id = ?',
                (identifier,)
            ).fetchone()
            return row is not None
    except Exception:
        return False


def get_whitelist():
    try:
        with get_db() as conn:
            rows = conn.execute(
                'SELECT user_id, note, created_at FROM whitelist ORDER BY created_at DESC'
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def add_to_whitelist(user_id, note=''):
    try:
        with get_db() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO whitelist (user_id, note) VALUES (?, ?)',
                (user_id, note)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to add to whitelist: {e}")


def remove_from_whitelist(user_id):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM whitelist WHERE user_id = ?', (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to remove from whitelist: {e}")


def _to_wib(utc_str):
    if not utc_str:
        return None
    try:
        utc_time = datetime.strptime(utc_str, '%Y-%m-%d %H:%M:%S')
        wib_time = utc_time + timedelta(hours=7)
        return wib_time.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return utc_str


def get_all_usage():
    today = _get_today_wib()
    
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT 
                    u.identifier,
                    u.id_type,
                    u.bytes_used,
                    u.last_reset,
                    (SELECT COUNT(*) FROM tasks t WHERE (t.fingerprint = u.identifier OR t.ip_address = u.identifier) AND DATE(t.created_at) = ?) as today_downloads,
                    (SELECT COUNT(*) FROM tasks t WHERE t.fingerprint = u.identifier OR t.ip_address = u.identifier) as total_downloads,
                    (SELECT MAX(created_at) FROM tasks t WHERE t.fingerprint = u.identifier OR t.ip_address = u.identifier) as last_activity,
                    (SELECT 1 FROM whitelist w WHERE w.user_id = u.identifier) as is_whitelisted
                FROM usage u
                ORDER BY u.bytes_used DESC
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
