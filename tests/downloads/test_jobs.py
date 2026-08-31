from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from cryptography.fernet import Fernet

from downloads.crypto import decrypt_context, encrypt_context
from downloads.jobs import download_task, inspect_task, reconcile_stale_tasks
from downloads.states import TaskState
from providers.contracts import DownloadResult, InspectionResult, MediaFormat
from providers.url_safety import UnsafeUrl, ValidatedUrl


class FakeTasks:
    def __init__(self, task):
        self.task = task
        self.inspection = None
        self.completed = None
        self.failed = None
        self.requeued = None
        self.stale = []
        self.expired_count = 0

    def claim(self, task_id, expected, target):
        if self.task.state != expected:
            return None
        self.task.state = target
        return self.task

    def store_inspection(self, task_id, result, encrypted_context):
        self.inspection = (result, encrypted_context)
        self.task.state = TaskState.READY

    def complete_download(self, task_id, file_path, byte_count, task_directory):
        self.completed = (file_path, byte_count, task_directory)
        self.task.state = TaskState.COMPLETED
        self.task.resolver_context = ""

    def fail(self, task_id, code, detail):
        self.failed = (code, detail)
        self.task.state = TaskState.FAILED
        self.task.resolver_context = ""

    def block(self, task_id, code):
        self.failed = (code, "")
        self.task.state = TaskState.BLOCKED

    def requeue(self, task_id, active_state, queued_state, code):
        self.requeued = (active_state, queued_state, code)
        self.task.state = queued_state
        self.task.retry_count += 1
        return True

    def find_stale(self, stale_before):
        return self.stale

    def expire_ready(self, now):
        return self.expired_count


class FakeProvider:
    def __init__(self, inspection=None, download=None):
        self.inspection = inspection
        self.download_result = download
        self.inspected = []
        self.downloaded = []

    def inspect(self, url):
        self.inspected.append(url)
        return self.inspection

    def download(self, request):
        self.downloaded.append(request)
        if self.download_result.success:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_bytes(b"media")
            return DownloadResult(True, request.output_path, 5)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"partial")
        return self.download_result


class FakeQuota:
    def __init__(self):
        self.settled = []
        self.released = []

    def settle(self, task, byte_count):
        self.settled.append((task.public_token, byte_count))

    def release(self, task):
        self.released.append(task.public_token)


class FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue_in(self, delay, function, task_id):
        self.calls.append((delay, function, task_id))


def safe_validator(url):
    return ValidatedUrl(url, "example.test", ("93.184.216.34",))


def task(**changes):
    values = {
        "id": "internal-id",
        "public_token": "public-token",
        "source_url": "https://example.test/watch/1",
        "state": TaskState.INSPECTION_QUEUED,
        "formats": (MediaFormat("720", "720p", "mp4", "video", estimated_bytes=100),),
        "selected_format_id": "720",
        "reserved_bytes": 100,
        "resolver_context": "",
        "retry_count": 0,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_inspection_claims_task_and_encrypts_private_context():
    current = task()
    tasks = FakeTasks(current)
    provider = FakeProvider(
        InspectionResult(
            "generic",
            current.source_url,
            "A video",
            current.formats,
            resolver_context={"cookies": "session=secret"},
        )
    )
    keys = [Fernet.generate_key().decode()]

    inspect_task(
        "internal-id",
        tasks=tasks,
        provider_for_url=lambda url: provider,
        validator=safe_validator,
        encryption_keys=keys,
    )

    assert provider.inspected == [current.source_url]
    assert "secret" not in tasks.inspection[1]
    assert decrypt_context(tasks.inspection[1], keys) == {"cookies": "session=secret"}
    assert current.state == TaskState.READY


def test_duplicate_inspection_job_is_a_noop():
    current = task(state=TaskState.READY)
    provider = FakeProvider()

    inspect_task(
        "internal-id",
        tasks=FakeTasks(current),
        provider_for_url=lambda url: provider,
        validator=safe_validator,
        encryption_keys=[Fernet.generate_key().decode()],
    )

    assert provider.inspected == []


def test_inspection_blocks_url_that_is_no_longer_public():
    current = task()
    tasks = FakeTasks(current)

    def reject(url):
        raise UnsafeUrl("private")

    inspect_task(
        "internal-id",
        tasks=tasks,
        provider_for_url=lambda url: FakeProvider(),
        validator=reject,
        encryption_keys=[Fernet.generate_key().decode()],
    )

    assert tasks.failed == ("unsafe_url", "")
    assert current.state == TaskState.BLOCKED


def test_download_settles_quota_and_persists_relative_file(tmp_path):
    keys = [Fernet.generate_key().decode()]
    current = task(
        state=TaskState.DOWNLOAD_QUEUED,
        resolver_context=encrypt_context({"referer": "https://example.test"}, keys),
    )
    tasks = FakeTasks(current)
    quota = FakeQuota()
    provider = FakeProvider(download=DownloadResult(True))

    download_task(
        "internal-id",
        tasks=tasks,
        provider_for_url=lambda url: provider,
        quota=quota,
        queue=FakeQueue(),
        download_root=tmp_path,
        encryption_keys=keys,
    )

    assert quota.settled == [("public-token", 5)]
    assert tasks.completed[0] == "internal-id/media.mp4"
    assert (tmp_path / tasks.completed[0]).read_bytes() == b"media"
    assert current.resolver_context == ""


def test_failed_download_removes_partial_file_and_releases_quota(tmp_path):
    current = task(state=TaskState.DOWNLOAD_QUEUED)
    tasks = FakeTasks(current)
    quota = FakeQuota()
    provider = FakeProvider(download=DownloadResult(False, error_code="unavailable"))

    download_task(
        "internal-id",
        tasks=tasks,
        provider_for_url=lambda url: provider,
        quota=quota,
        queue=FakeQueue(),
        download_root=tmp_path,
        encryption_keys=[Fernet.generate_key().decode()],
    )

    assert not (tmp_path / "internal-id" / "media.mp4").exists()
    assert quota.released == ["public-token"]
    assert tasks.failed[0] == "unavailable"


def test_transient_download_failure_is_requeued_twice(tmp_path):
    current = task(state=TaskState.DOWNLOAD_QUEUED, retry_count=1)
    tasks = FakeTasks(current)
    queue = FakeQueue()

    download_task(
        "internal-id",
        tasks=tasks,
        provider_for_url=lambda url: FakeProvider(
            download=DownloadResult(False, error_code="timeout")
        ),
        quota=FakeQuota(),
        queue=queue,
        download_root=tmp_path,
        encryption_keys=[Fernet.generate_key().decode()],
    )

    assert tasks.requeued[1] == TaskState.DOWNLOAD_QUEUED
    assert queue.calls == [(timedelta(seconds=10), "downloads.jobs.download_task", "internal-id")]


def test_reconcile_requeues_recoverable_jobs_and_fails_exhausted_jobs():
    tasks = FakeTasks(task())
    inspecting = task(id="inspect-id", state=TaskState.INSPECTING, retry_count=0)
    exhausted = task(id="download-id", state=TaskState.DOWNLOADING, retry_count=2)
    tasks.stale = [inspecting, exhausted]
    tasks.expired_count = 3
    quota = FakeQuota()
    queue = FakeQueue()

    result = reconcile_stale_tasks(
        datetime.now(UTC),
        tasks=tasks,
        quota=quota,
        queue=queue,
    )

    assert result.requeued == 1
    assert result.failed == 1
    assert result.expired == 3
    assert queue.calls[0][1:] == ("downloads.jobs.inspect_task", "inspect-id")
    assert quota.released == ["public-token"]
