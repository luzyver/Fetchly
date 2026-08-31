from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from downloads.cleanup import cleanup_expired
from downloads.jobs import reconcile_stale_tasks
from downloads.repository import DjangoTaskStore


class Command(BaseCommand):
    help = "Clean expired files and reconcile interrupted download tasks"

    def handle(self, *args, **options):
        now = timezone.now()
        cleaned = cleanup_expired(
            now,
            tasks=DjangoTaskStore(),
            download_root=settings.DOWNLOAD_ROOT,
        )
        reconciled = reconcile_stale_tasks(now)
        self.stdout.write(
            self.style.SUCCESS(
                f"deleted={cleaned.deleted} missing={cleaned.missing} "
                f"requeued={reconciled.requeued} failed={reconciled.failed}"
            )
        )
