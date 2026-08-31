import base64
import hashlib
import hmac
import json
import re
import secrets

from cryptography.fernet import Fernet, MultiFernet

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}\.[A-Za-z0-9_-]{43}$")


def _cipher(keys: list[str]) -> MultiFernet:
    if not keys:
        raise ValueError("At least one resolver encryption key is required")
    return MultiFernet([Fernet(key.encode()) for key in keys])


def encrypt_context(context: dict[str, str], keys: list[str]) -> str:
    payload = json.dumps(context, separators=(",", ":"), sort_keys=True).encode()
    return _cipher(keys).encrypt(payload).decode()


def decrypt_context(payload: str, keys: list[str]) -> dict[str, str]:
    return json.loads(_cipher(keys).decrypt(payload.encode()))


def issue_public_token(secret: str | None = None) -> str:
    if secret is None:
        from django.conf import settings

        secret = settings.SECRET_KEY
    value = secrets.token_urlsafe(32)
    signature = _token_signature(value, secret)
    return f"{value}.{signature}"


def verify_public_token(token: str, secret: str | None = None) -> bool:
    if not TOKEN_PATTERN.fullmatch(token):
        return False
    if secret is None:
        from django.conf import settings

        secret = settings.SECRET_KEY
    value, signature = token.split(".", 1)
    return hmac.compare_digest(signature, _token_signature(value, secret))


def _token_signature(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), value.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
