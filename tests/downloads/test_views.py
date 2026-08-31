from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.http import Http404
from django.test import RequestFactory, override_settings

from downloads import views
from downloads.crypto import issue_public_token
from downloads.states import TaskState
from usage.identity import VisitorIdentity

IDENTITY = VisitorIdentity("fingerprint", "ip", "owner", 0)


class FakeStore:
    def __init__(self, task):
        self.task = task
        self.lookups = []

    def find(self, token):
        self.lookups.append(token)
        return self.task


def completed_task(token, output_file):
    return SimpleNamespace(
        public_token=token,
        owner_id=IDENTITY.owner_id,
        state=TaskState.COMPLETED,
        output_file=output_file,
        title="Video lucu",
        output_size=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


@pytest.fixture
def request_factory():
    return RequestFactory()


def configure(monkeypatch, store):
    monkeypatch.setattr(views, "_store", lambda: store)
    monkeypatch.setattr(views, "_request_identity", lambda request: IDENTITY)


def test_invalid_signature_is_rejected_before_database_lookup(request_factory, monkeypatch):
    store = FakeStore(None)
    configure(monkeypatch, store)

    with pytest.raises(Http404):
        views.task_status(request_factory.get("/"), "not-a-valid-token")

    assert store.lookups == []


def test_wrong_owner_is_indistinguishable_from_missing_task(request_factory, monkeypatch):
    token = issue_public_token()
    current = completed_task(token, "internal-id/media.mp4")
    current.owner_id = "another-owner"
    configure(monkeypatch, FakeStore(current))

    with pytest.raises(Http404):
        views.task_status(request_factory.get("/"), token)


@override_settings(DOWNLOAD_ROOT="C:/tmp/fetchly-downloads")
def test_file_path_traversal_is_rejected(request_factory, monkeypatch):
    token = issue_public_token()
    configure(monkeypatch, FakeStore(completed_task(token, "../secret.txt")))

    with pytest.raises(Http404):
        views.task_file(request_factory.get("/"), token)


def test_completed_owner_can_stream_unexpired_file(tmp_path, request_factory, monkeypatch):
    token = issue_public_token()
    media = tmp_path / "internal-id" / "media.mp4"
    media.parent.mkdir()
    media.write_bytes(b"media")
    configure(monkeypatch, FakeStore(completed_task(token, "internal-id/media.mp4")))

    with override_settings(DOWNLOAD_ROOT=tmp_path):
        response = views.task_file(request_factory.get("/"), token)

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"media"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "attachment" in response.headers["Content-Disposition"]


def test_expired_file_is_not_served(request_factory, monkeypatch):
    token = issue_public_token()
    current = completed_task(token, "internal-id/media.mp4")
    current.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    configure(monkeypatch, FakeStore(current))

    with pytest.raises(Http404):
        views.task_file(request_factory.get("/"), token)
