import time
import threading
from collections import deque
from typing import Deque, Dict

_lock = threading.Lock()
_store: Dict[str, Deque[float]] = {}


def is_rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    cutoff = now - window_seconds

    with _lock:
        q = _store.get(key)
        if q is None:
            q = deque()
            _store[key] = q

        while q and q[0] <= cutoff:
            q.popleft()

        if len(q) >= limit:
            return True

        q.append(now)
        return False
