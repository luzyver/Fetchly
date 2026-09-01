import shutil
from dataclasses import dataclass
from datetime import timedelta
from functools import cache
from pathlib import Path

from django.conf import settings

from providers.contracts import DownloadRequest, MediaFormat
from providers.url_safety import UnsafeUrl, validate_public_url
from providers.ytdlp import ProviderError

from .crypto import decrypt_context, encrypt_context
from .states import TaskState

TRANSIENT_ERRORS = frozenset({"network", "rate_limited", "timeout"})
MAX_RETRIES = 2


@dataclass(frozen=True)
class ReconcileResult:
    requeued: int = 0
    failed: int = 0
    expired: int = 0


def inspect_task(
    task_id: str,
    *,
    tasks=None,
    provider_for_url=None,
    validator=validate_public_url,
    encryption_keys=None,
) -> None:
    tasks = tasks or _task_store()
    provider_for_url = provider_for_url or _provider_for_url
    encryption_keys = encryption_keys or settings.RESOLVER_ENCRYPTION_KEYS
    task = tasks.claim(task_id, TaskState.INSPECTION_QUEUED, TaskState.INSPECTING)
    if task is None:
        return

    try:
        source_url = validator(task.source_url).url
        result = provider_for_url(source_url).inspect(source_url)
        private_context = encrypt_context(result.resolver_context, encryption_keys)
        tasks.store_inspection(task_id, result, private_context)
    except UnsafeUrl:
        tasks.block(task_id, "unsafe_url")
    except ProviderError as error:
        tasks.fail(task_id, error.code, error.detail[-300:])
    except Exception as error:
        tasks.fail(task_id, "provider_failed", str(error)[-300:])


def download_task(
    task_id: str,
    *,
    tasks=None,
    provider_for_url=None,
    quota=None,
    queue=None,
    download_root: Path | None = None,
    encryption_keys=None,
) -> None:
    tasks = tasks or _task_store()
    provider_for_url = provider_for_url or _provider_for_url
    quota = quota or _quota_jobs()
    queue = queue or _media_queue()
    download_root = Path(download_root or settings.DOWNLOAD_ROOT).resolve()
    encryption_keys = encryption_keys or settings.RESOLVER_ENCRYPTION_KEYS
    task = tasks.claim(task_id, TaskState.DOWNLOAD_QUEUED, TaskState.DOWNLOADING)
    if task is None:
        return

    selected = _selected_format(task)
    if selected is None:
        quota.release(task)
        tasks.fail(task_id, "format_not_found", "")
        return

    task_directory = (download_root / str(task.id)).resolve()
    if task_directory.parent != download_root:
        quota.release(task)
        tasks.fail(task_id, "invalid_path", "")
        return
    output_path = task_directory / f"media.{selected.extension}"

    try:
        context = (
            decrypt_context(task.resolver_context, encryption_keys) if task.resolver_context else {}
        )
        result = provider_for_url(task.source_url).download(
            DownloadRequest(
                task.source_url,
                selected,
                output_path,
                settings.DOWNLOAD_MAX_BYTES,
                context,
            )
        )
    except Exception as error:
        _finish_failure(
            task,
            "provider_failed",
            str(error)[-300:],
            tasks,
            quota,
            queue,
            task_directory,
        )
        return

    if not result.success or result.file_path is None:
        _finish_failure(
            task,
            result.error_code or "provider_failed",
            (result.error_detail or "")[-300:],
            tasks,
            quota,
            queue,
            task_directory,
        )
        return

    relative_file = result.file_path.resolve().relative_to(download_root).as_posix()
    quota.settle(task, result.bytes_written)
    tasks.complete_download(
        task_id,
        relative_file,
        result.bytes_written,
        str(task.id),
    )


def reconcile_stale_tasks(now, *, tasks=None, quota=None, queue=None) -> ReconcileResult:
    tasks = tasks or _task_store()
    quota = quota or _quota_jobs()
    queue = queue or _media_queue()
    stale_before = now - timedelta(seconds=settings.STALE_TASK_SECONDS)
    requeued = 0
    failed = 0

    for task in tasks.find_stale(stale_before):
        active_state = TaskState(task.state)
        if active_state is TaskState.INSPECTING:
            queued_state = TaskState.INSPECTION_QUEUED
            job = "downloads.jobs.inspect_task"
        else:
            queued_state = TaskState.DOWNLOAD_QUEUED
            job = "downloads.jobs.download_task"

        if task.retry_count < MAX_RETRIES and tasks.requeue(
            str(task.id), active_state, queued_state, "worker_interrupted"
        ):
            queue.enqueue_in(timedelta(0), job, str(task.id))
            requeued += 1
            continue

        if active_state is TaskState.DOWNLOADING:
            quota.release(task)
        tasks.fail(str(task.id), "worker_interrupted", "Retry limit exhausted")
        failed += 1

    return ReconcileResult(
        requeued=requeued,
        failed=failed,
        expired=tasks.expire_ready(now),
    )


def maintenance_task() -> None:
    from django.utils import timezone

    from .cleanup import cleanup_expired

    now = timezone.now()
    cleanup_expired(now, tasks=_task_store(), download_root=settings.DOWNLOAD_ROOT)
    reconcile_stale_tasks(now)


def _selected_format(task) -> MediaFormat | None:
    for item in task.formats:
        item_id = getattr(item, "format_id", getattr(item, "id", None))
        if item_id == task.selected_format_id:
            if isinstance(item, MediaFormat):
                return item
            return MediaFormat(
                id=item.format_id,
                label=item.label,
                extension=item.extension,
                kind=item.kind,
                height=item.height,
                estimated_bytes=item.estimated_bytes,
                selector=item.selector,
                playlist_item=item.playlist_item,
            )
    return None


def _finish_failure(task, code, detail, tasks, quota, queue, task_directory) -> None:
    _clean_task_directory(task_directory)
    if code in TRANSIENT_ERRORS and task.retry_count < MAX_RETRIES:
        retry_count = task.retry_count
        queued = tasks.requeue(
            str(task.id),
            TaskState.DOWNLOADING,
            TaskState.DOWNLOAD_QUEUED,
            code,
        )
        if queued:
            delay = timedelta(seconds=5 * (2**retry_count))
            queue.enqueue_in(delay, "downloads.jobs.download_task", str(task.id))
            return
    quota.release(task)
    tasks.fail(str(task.id), code, detail)


def _clean_task_directory(task_directory: Path) -> None:
    if task_directory.exists() and task_directory.is_dir():
        shutil.rmtree(task_directory)


@cache
def _task_store():
    from .repository import DjangoTaskStore

    return DjangoTaskStore()


@cache
def _registrations():
    import requests

    from providers.registry import build_default_registry
    from providers.ytdlp import YtDlpClient

    return build_default_registry(YtDlpClient(), requests.Session())


def _provider_for_url(url: str):
    from providers.registry import get_provider

    return get_provider(url, _registrations())


def _media_queue():
    from fetchly.rq import get_queue

    return get_queue()


def _quota_jobs():
    from .runtime import MongoJobQuota

    return MongoJobQuota()
