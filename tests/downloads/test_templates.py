from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import Client

from downloads.states import TaskState
from providers.contracts import MediaFormat


def task(state, **changes):
    values = {
        "public_token": "public-token",
        "state": state,
        "title": "Video contoh",
        "provider": "youtube",
        "thumbnail_url": "",
        "duration_seconds": 123,
        "formats": (MediaFormat("720", "720p", "mp4", "video", estimated_bytes=1024),),
        "progress_percent": 0,
        "error_code": "",
        "output_size": 0,
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_home_is_semantic_and_uses_only_local_htmx(monkeypatch):
    from downloads import views

    monkeypatch.setattr(views, "_history_for_request", lambda request: [])
    response = Client().get("/")
    html = response.content.decode()

    assert response.status_code == 200
    assert '<html lang="id"' in html
    assert "Ambil videonya." in html
    assert "Simpan momennya." in html
    assert '<label for="media-url">Tautan video</label>' in html
    assert "novalidate" in html
    assert "htmx-4.0.0.min.js" in html
    assert "cdn." not in html


def test_queued_inspection_fragment_polls_until_ready():
    html = render_to_string(
        "downloads/_inspection.html",
        {"task": task(TaskState.INSPECTION_QUEUED)},
    )

    assert 'role="status"' in html
    assert 'hx-trigger="every 2s"' in html
    assert "Sedang memeriksa tautan" in html


def test_ready_fragment_uses_real_radio_inputs_and_stops_polling():
    html = render_to_string(
        "downloads/_inspection.html",
        {"task": task(TaskState.READY)},
    )

    assert 'type="radio"' in html
    assert 'value="720"' in html
    assert "Siapkan unduhan" in html
    assert 'hx-trigger="every 2s"' not in html


def test_completed_status_has_authorized_download_link_and_stops_polling():
    html = render_to_string(
        "downloads/_status.html",
        {"task": task(TaskState.COMPLETED)},
    )

    assert "Siap diunduh" in html
    assert "/tasks/public-token/file" in html
    assert 'hx-trigger="every 2s"' not in html
