from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from dashboard import views


def user(*, authenticated, active=False, staff=False):
    return SimpleNamespace(
        is_authenticated=authenticated,
        is_active=active,
        is_staff=staff,
        pk="staff-id",
        get_username=lambda: "operator",
    )


def test_anonymous_dashboard_redirects_to_staff_login():
    request = RequestFactory().get("/admin/")
    request.user = user(authenticated=False)

    response = views.index(request)

    assert response.status_code == 302
    assert "/admin/login/" in response.url


def test_nonstaff_user_receives_403():
    request = RequestFactory().get("/admin/")
    request.user = user(authenticated=True, active=True, staff=False)

    with pytest.raises(PermissionDenied):
        views.index(request)


def test_staff_dashboard_never_renders_sensitive_task_fields(monkeypatch):
    request = RequestFactory().get("/admin/")
    request.user = user(authenticated=True, active=True, staff=True)
    monkeypatch.setattr(
        views,
        "_dashboard_context",
        lambda request: {
            "counts": {"queued": 1, "active": 2, "completed": 3, "failed": 4},
            "tasks": [
                SimpleNamespace(
                    title="Video contoh",
                    provider="youtube",
                    state="completed",
                    output_size=5,
                    updated_at="baru saja",
                    owner_id="abcdef1234567890",
                )
            ],
            "rules": [],
            "rule_form": None,
        },
    )

    html = views.index(request).content.decode()

    assert "Video contoh" in html
    assert "abcdef" in html
    for secret in ("source_url", "resolver_context", "output_file", "fingerprint_id"):
        assert secret not in html
