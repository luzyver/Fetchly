from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django_mongodb_backend.fields import EmbeddedModelArrayField, ObjectIdAutoField
from django_mongodb_backend.models import EmbeddedModel

from .states import TaskState


def default_expiry():
    return timezone.now() + timedelta(seconds=settings.DOWNLOAD_TASK_TTL_SECONDS)


class StoredFormat(EmbeddedModel):
    format_id = models.CharField(max_length=128)
    label = models.CharField(max_length=128)
    extension = models.CharField(max_length=16)
    kind = models.CharField(max_length=16)
    height = models.PositiveIntegerField(null=True)
    estimated_bytes = models.PositiveBigIntegerField(null=True)
    selector = models.CharField(max_length=255, default="best")
    playlist_item = models.PositiveIntegerField(null=True)


class DownloadTask(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    public_token = models.CharField(max_length=96, unique=True)
    owner_id = models.CharField(max_length=64)
    fingerprint_id = models.CharField(max_length=64)
    ip_id = models.CharField(max_length=64)
    identity_key_version = models.PositiveSmallIntegerField(default=0)

    source_url = models.URLField(max_length=2048)
    provider = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=512, blank=True)
    thumbnail_url = models.URLField(max_length=2048, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True)
    formats = EmbeddedModelArrayField(StoredFormat, default=list)
    resolver_context = models.TextField(blank=True)

    state = models.CharField(
        max_length=32,
        choices=[(state.value, state.value) for state in TaskState],
        default=TaskState.INSPECTION_QUEUED,
    )
    progress_percent = models.PositiveSmallIntegerField(default=0)
    retry_count = models.PositiveSmallIntegerField(default=0)
    selected_format_id = models.CharField(max_length=128, blank=True)
    reserved_bytes = models.PositiveBigIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True)
    error_detail = models.TextField(blank=True)

    task_directory = models.CharField(max_length=512, blank=True)
    output_file = models.CharField(max_length=512, blank=True)
    output_size = models.PositiveBigIntegerField(default=0)
    expires_at = models.DateTimeField(default=default_expiry)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "download_tasks"
        indexes = [
            models.Index(fields=["owner_id", "-created_at"], name="task_owner_created"),
            models.Index(fields=["state", "updated_at"], name="task_state_updated"),
            models.Index(fields=["expires_at"], name="task_expiry"),
        ]
