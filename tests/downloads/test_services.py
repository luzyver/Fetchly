from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from downloads.services import TaskRejected, create_inspection, request_download
from downloads.states import TaskState
from providers.contracts import MediaFormat
from providers.url_safety import UnsafeUrl, ValidatedUrl
from usage.identity import VisitorIdentity
from usage.quota import QuotaExceeded

IDENTITY = VisitorIdentity("fingerprint", "ip", "owner", 0)


class FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, function, *args):
        self.calls.append((function, args))


class FakeTasks:
    def __init__(self, task=None, *, lose_claim=False):
        self.task = task
        self.lose_claim = lose_claim
        self.created = None
        self.queued = None

    def create(self, values):
        self.created = values
        return "internal-object-id"

    def find(self, token):
        return self.task

    def queue_download(self, internal_id, format_id, reserved_bytes):
        if self.lose_claim or self.task.state != TaskState.READY:
            return False
        self.queued = (internal_id, format_id, reserved_bytes)
        self.task.state = TaskState.DOWNLOAD_QUEUED
        return True


class FakeQuota:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.reserved = []
        self.released = []

    def reserve(self, identity, token, byte_count):
        if not self.allowed:
            raise QuotaExceeded("full")
        self.reserved.append((identity, token, byte_count))

    def release(self, identity, token, byte_count):
        self.released.append((identity, token, byte_count))


def validator(url):
    if "private" in url:
        raise UnsafeUrl("private")
    return ValidatedUrl(url, "example.test", ("93.184.216.34",))


def ready_task(**changes):
    values = {
        "id": "internal-object-id",
        "public_token": "public-token",
        "owner_id": IDENTITY.owner_id,
        "state": TaskState.READY,
        "expires_at": datetime.now(UTC) + timedelta(minutes=15),
        "formats": (MediaFormat("720", "720p", "mp4", "video", estimated_bytes=100),),
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_inspection_enqueues_only_internal_id():
    tasks = FakeTasks()
    queue = FakeQueue()

    token = create_inspection(
        IDENTITY,
        "https://example.test/watch/1",
        tasks=tasks,
        queue=queue,
        validator=validator,
        access_allowed=lambda identity: True,
        rate_limited=lambda bucket, identifier: False,
    )

    assert token == tasks.created["public_token"]
    assert tasks.created["source_url"] == "https://example.test/watch/1"
    assert queue.calls == [("downloads.jobs.inspect_task", ("internal-object-id",))]


@pytest.mark.parametrize(
    ("identity", "url", "allowed", "limited", "code"),
    [
        (
            VisitorIdentity("", "ip", "owner", 0),
            "https://example.test/1",
            True,
            False,
            "identity_required",
        ),
        (IDENTITY, "https://private.test/1", True, False, "unsafe_url"),
        (IDENTITY, "https://example.test/1", False, False, "blocked"),
        (IDENTITY, "https://example.test/1", True, True, "rate_limited"),
    ],
)
def test_inspection_is_rejected_before_queue(identity, url, allowed, limited, code):
    queue = FakeQueue()

    with pytest.raises(TaskRejected, match=code):
        create_inspection(
            identity,
            url,
            tasks=FakeTasks(),
            queue=queue,
            validator=validator,
            access_allowed=lambda identity: allowed,
            rate_limited=lambda bucket, identifier: limited,
        )

    assert queue.calls == []


def test_download_reserves_snapshot_size_and_enqueues_internal_id():
    tasks = FakeTasks(ready_task())
    queue = FakeQueue()
    quota = FakeQuota()

    request_download(
        IDENTITY,
        "public-token",
        "720",
        tasks=tasks,
        queue=queue,
        quota=quota,
        now=lambda: datetime.now(UTC),
    )

    assert quota.reserved[0][2] == 100
    assert tasks.queued == ("internal-object-id", "720", 100)
    assert queue.calls == [("downloads.jobs.download_task", ("internal-object-id",))]


def test_unknown_size_reserves_server_cap_instead_of_rejecting_format():
    current = ready_task(formats=(MediaFormat("audio", "Audio saja", "mp3", "audio"),))
    quota = FakeQuota()

    request_download(
        IDENTITY,
        "public-token",
        "audio",
        tasks=FakeTasks(current),
        queue=FakeQueue(),
        quota=quota,
        now=lambda: datetime.now(UTC),
        max_bytes=500,
    )

    assert quota.reserved[0][2] == 500


@pytest.mark.parametrize(
    ("task", "format_id", "code"),
    [
        (None, "720", "not_found"),
        (ready_task(owner_id="someone-else"), "720", "not_found"),
        (ready_task(expires_at=datetime.now(UTC) - timedelta(seconds=1)), "720", "expired"),
        (ready_task(), "unknown", "format_not_found"),
        (ready_task(state=TaskState.DOWNLOADING), "720", "not_ready"),
    ],
)
def test_download_rejects_invalid_or_unauthorized_task(task, format_id, code):
    queue = FakeQueue()

    with pytest.raises(TaskRejected, match=code):
        request_download(
            IDENTITY,
            "public-token",
            format_id,
            tasks=FakeTasks(task),
            queue=queue,
            quota=FakeQuota(),
            now=lambda: datetime.now(UTC),
        )

    assert queue.calls == []


def test_download_does_not_enqueue_when_quota_is_exhausted():
    queue = FakeQueue()

    with pytest.raises(QuotaExceeded):
        request_download(
            IDENTITY,
            "public-token",
            "720",
            tasks=FakeTasks(ready_task()),
            queue=queue,
            quota=FakeQuota(allowed=False),
            now=lambda: datetime.now(UTC),
        )

    assert queue.calls == []


def test_download_releases_quota_if_atomic_queue_claim_loses_race():
    task = ready_task()
    tasks = FakeTasks(task, lose_claim=True)
    quota = FakeQuota()

    with pytest.raises(TaskRejected, match="not_ready"):
        request_download(
            IDENTITY,
            "public-token",
            "720",
            tasks=tasks,
            queue=FakeQueue(),
            quota=quota,
            now=lambda: datetime.now(UTC),
        )

    assert quota.released == [(IDENTITY, "public-token", 100)]
