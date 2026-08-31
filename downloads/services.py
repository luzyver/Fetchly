import hmac
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from providers.url_safety import UnsafeUrl, ValidatedUrl
from usage.identity import VisitorIdentity

from .crypto import issue_public_token
from .states import TaskState


class TaskRejected(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class TaskStore(Protocol):
    def create(self, values: dict) -> str: ...

    def find(self, token: str): ...

    def queue_download(self, internal_id: str, format_id: str, reserved_bytes: int) -> bool: ...


class TaskQueue(Protocol):
    def enqueue(self, function: str, *args: str): ...


class QuotaCommands(Protocol):
    def reserve(self, identity: VisitorIdentity, token: str, byte_count: int) -> None: ...

    def release(self, identity: VisitorIdentity, token: str, byte_count: int) -> None: ...


def create_inspection(
    identity: VisitorIdentity,
    url: str,
    *,
    tasks: TaskStore,
    queue: TaskQueue,
    validator: Callable[[str], ValidatedUrl],
    access_allowed: Callable[[VisitorIdentity], bool],
    rate_limited: Callable[[str, str], bool],
    token_factory: Callable[[], str] = issue_public_token,
) -> str:
    if not identity.fingerprint_id or not identity.ip_id or not identity.owner_id:
        raise TaskRejected("identity_required")
    try:
        source_url = validator(url).url
    except UnsafeUrl as error:
        raise TaskRejected("unsafe_url") from error
    if not access_allowed(identity):
        raise TaskRejected("blocked")
    if rate_limited("inspection", identity.owner_id):
        raise TaskRejected("rate_limited")

    token = token_factory()
    internal_id = tasks.create(
        {
            "public_token": token,
            "owner_id": identity.owner_id,
            "fingerprint_id": identity.fingerprint_id,
            "ip_id": identity.ip_id,
            "identity_key_version": identity.key_version,
            "source_url": source_url,
            "state": TaskState.INSPECTION_QUEUED,
        }
    )
    queue.enqueue("downloads.jobs.inspect_task", internal_id)
    return token


def request_download(
    identity: VisitorIdentity,
    token: str,
    format_id: str,
    *,
    tasks: TaskStore,
    queue: TaskQueue,
    quota: QuotaCommands,
    now: Callable[[], datetime],
    max_bytes: int | None = None,
) -> None:
    task = tasks.find(token)
    if task is None or not hmac.compare_digest(task.owner_id, identity.owner_id):
        raise TaskRejected("not_found")
    if task.expires_at <= now():
        raise TaskRejected("expired")
    if TaskState(task.state) is not TaskState.READY:
        raise TaskRejected("not_ready")

    selected = next(
        (
            item
            for item in task.formats
            if getattr(item, "format_id", getattr(item, "id", None)) == format_id
        ),
        None,
    )
    if selected is None:
        raise TaskRejected("format_not_found")
    if max_bytes is None:
        from django.conf import settings

        max_bytes = settings.DOWNLOAD_MAX_BYTES
    if selected.estimated_bytes and selected.estimated_bytes > max_bytes:
        raise TaskRejected("too_large")
    reserved_bytes = selected.estimated_bytes or max_bytes

    quota.reserve(identity, token, reserved_bytes)
    if not tasks.queue_download(str(task.id), format_id, reserved_bytes):
        quota.release(identity, token, reserved_bytes)
        raise TaskRejected("not_ready")
    queue.enqueue("downloads.jobs.download_task", str(task.id))
