from django.urls import reverse


def test_liveness(client):
    response = client.get(reverse("health-live"))
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_readiness_reports_dependencies(client, monkeypatch):
    monkeypatch.setattr("fetchly.views.mongo_ready", lambda: True)
    monkeypatch.setattr("fetchly.views.redis_ready", lambda: True)
    monkeypatch.setattr("fetchly.views.downloads_ready", lambda: True)
    response = client.get(reverse("health-ready"))
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "mongodb": True,
        "redis": True,
        "downloads": True,
    }
