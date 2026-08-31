from django.db import models
from django.utils import timezone

from .models import DownloadTask, StoredFormat
from .states import TaskState


class DjangoTaskStore:
    def create(self, values: dict) -> str:
        task = DownloadTask.objects.create(**values)
        return str(task.pk)

    def find(self, token: str) -> DownloadTask | None:
        return DownloadTask.objects.filter(public_token=token).first()

    def recent(self, owner_id: str, *, limit: int = 20):
        return list(DownloadTask.objects.filter(owner_id=owner_id).order_by("-created_at")[:limit])

    def queue_download(self, internal_id: str, format_id: str, reserved_bytes: int) -> bool:
        updated = DownloadTask.objects.filter(
            pk=internal_id,
            state=TaskState.READY,
        ).update(
            state=TaskState.DOWNLOAD_QUEUED,
            selected_format_id=format_id,
            reserved_bytes=reserved_bytes,
        )
        return updated == 1

    def claim(self, task_id: str, expected: TaskState, target: TaskState):
        updated = DownloadTask.objects.filter(pk=task_id, state=expected).update(
            state=target,
            updated_at=timezone.now(),
        )
        if updated != 1:
            return None
        return DownloadTask.objects.get(pk=task_id)

    def store_inspection(self, task_id: str, result, encrypted_context: str) -> None:
        formats = [
            StoredFormat(
                format_id=item.id,
                label=item.label,
                extension=item.extension,
                kind=item.kind,
                height=item.height,
                estimated_bytes=item.estimated_bytes,
                selector=item.selector,
                playlist_item=item.playlist_item,
            )
            for item in result.formats
        ]
        DownloadTask.objects.filter(pk=task_id, state=TaskState.INSPECTING).update(
            provider=result.provider,
            source_url=result.canonical_url,
            title=result.title,
            thumbnail_url=result.thumbnail_url or "",
            duration_seconds=result.duration_seconds,
            formats=formats,
            resolver_context=encrypted_context,
            state=TaskState.READY,
            updated_at=timezone.now(),
        )

    def complete_download(
        self,
        task_id: str,
        file_path: str,
        byte_count: int,
        task_directory: str,
    ) -> None:
        DownloadTask.objects.filter(pk=task_id, state=TaskState.DOWNLOADING).update(
            state=TaskState.COMPLETED,
            output_file=file_path,
            output_size=byte_count,
            task_directory=task_directory,
            progress_percent=100,
            resolver_context="",
            error_detail="",
            updated_at=timezone.now(),
        )

    def fail(self, task_id: str, code: str, detail: str) -> None:
        DownloadTask.objects.filter(pk=task_id).update(
            state=TaskState.FAILED,
            error_code=code,
            error_detail=detail[-300:],
            resolver_context="",
            updated_at=timezone.now(),
        )

    def block(self, task_id: str, code: str) -> None:
        DownloadTask.objects.filter(pk=task_id).update(
            state=TaskState.BLOCKED,
            error_code=code,
            resolver_context="",
            updated_at=timezone.now(),
        )

    def requeue(
        self,
        task_id: str,
        active_state: TaskState,
        queued_state: TaskState,
        code: str,
    ) -> bool:
        updated = DownloadTask.objects.filter(pk=task_id, state=active_state).update(
            state=queued_state,
            retry_count=models.F("retry_count") + 1,
            error_code=code,
            updated_at=timezone.now(),
        )
        return updated == 1

    def find_stale(self, stale_before):
        return list(
            DownloadTask.objects.filter(
                state__in=[TaskState.INSPECTING, TaskState.DOWNLOADING],
                updated_at__lt=stale_before,
            )
        )

    def expire_ready(self, now) -> int:
        return DownloadTask.objects.filter(
            state=TaskState.READY,
            expires_at__lte=now,
        ).update(
            state=TaskState.EXPIRED,
            resolver_context="",
            updated_at=timezone.now(),
        )

    def expired_candidates(self, now):
        return list(
            DownloadTask.objects.filter(
                expires_at__lte=now,
                state__in=[TaskState.COMPLETED, TaskState.FAILED, TaskState.BLOCKED],
            ).exclude(output_file="")
        )

    def mark_expired(self, task_id: str) -> None:
        DownloadTask.objects.filter(pk=task_id).update(
            state=TaskState.EXPIRED,
            output_file="",
            output_size=0,
            resolver_context="",
            updated_at=timezone.now(),
        )
