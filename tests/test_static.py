from asgiref.sync import async_to_sync
from django.core.management import call_command
from django.test import AsyncClient


def test_collected_static_files_are_served_by_asgi(settings, tmp_path):
    settings.STATIC_ROOT = tmp_path / "staticfiles"
    call_command("collectstatic", interactive=False, verbosity=0)

    response = async_to_sync(AsyncClient().get)("/static/css/app.css")

    assert response.status_code == 200
