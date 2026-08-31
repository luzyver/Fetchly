import os
import uuid

from django.conf import settings
from django.http import JsonResponse
from pymongo import MongoClient
from redis import Redis


def mongo_ready() -> bool:
    client = MongoClient(settings.DATABASES["default"]["HOST"], serverSelectionTimeoutMS=1000)
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False
    finally:
        client.close()


def redis_ready() -> bool:
    try:
        return bool(Redis.from_url(settings.REDIS_URL).ping())
    except Exception:
        return False


def downloads_ready() -> bool:
    probe = settings.DOWNLOAD_ROOT / f".health-{uuid.uuid4().hex}"
    try:
        settings.DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"")
        return True
    except OSError:
        return False
    finally:
        try:
            os.unlink(probe)
        except FileNotFoundError:
            pass


def health_live(request):
    return JsonResponse({"ok": True})


def health_ready(request):
    status = {
        "mongodb": mongo_ready(),
        "redis": redis_ready(),
        "downloads": downloads_ready(),
    }
    status["ok"] = all(status.values())
    return JsonResponse(
        {
            "ok": status["ok"],
            "mongodb": status["mongodb"],
            "redis": status["redis"],
            "downloads": status["downloads"],
        },
        status=200 if status["ok"] else 503,
    )
