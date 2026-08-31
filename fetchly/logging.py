import json
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

SENSITIVE_KEYS = frozenset(
    {"authorization", "cookie", "cookies", "referer", "resolver_context", "token"}
)


def redact(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        parsed = urlsplit(value)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "task_id",
            "provider",
            "state",
            "elapsed_ms",
            "error_code",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(redact(payload), ensure_ascii=False)
