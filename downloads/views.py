import hmac
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from providers.url_safety import validate_public_url
from usage.identity import identity_from_request
from usage.quota import QuotaExceeded

from .crypto import verify_public_token
from .repository import DjangoTaskStore
from .runtime import MongoCommandQuota, access_allowed, rate_limited
from .services import TaskRejected, create_inspection, request_download
from .states import TaskState


def _store():
    return DjangoTaskStore()


def _request_identity(request):
    return identity_from_request(request, request.COOKIES.get("fetchly_fp", ""))


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _history_for_request(request):
    try:
        identity = _request_identity(request)
    except (TypeError, ValueError):
        return []
    return _store().recent(identity.owner_id, limit=20)


def _owned_task(request, token: str):
    if not verify_public_token(token):
        raise Http404
    try:
        identity = _request_identity(request)
    except (TypeError, ValueError) as error:
        raise Http404 from error
    task = _store().find(token)
    if task is None or not hmac.compare_digest(task.owner_id, identity.owner_id):
        raise Http404
    return identity, task


@require_GET
def index(request):
    return render(
        request,
        "downloads/index.html",
        {
            "history": _history_for_request(request),
            "has_identity": bool(request.COOKIES.get("fetchly_fp")),
        },
    )


@require_POST
def set_identity(request):
    fingerprint = request.POST.get("fingerprint", "")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        return JsonResponse({"error": "invalid_fingerprint"}, status=400)
    response = JsonResponse({"ready": True})
    response.set_cookie(
        "fetchly_fp",
        f"v1:{fingerprint}",
        max_age=365 * 24 * 60 * 60,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="Lax",
    )
    return response


@require_POST
def inspect(request):
    try:
        identity = _request_identity(request)
        token = create_inspection(
            identity,
            request.POST.get("url", ""),
            tasks=_store(),
            queue=_queue(),
            validator=validate_public_url,
            access_allowed=access_allowed,
            rate_limited=rate_limited,
        )
    except (TypeError, ValueError):
        return JsonResponse({"error": "identity_required"}, status=400)
    except TaskRejected as error:
        status = {"blocked": 403, "rate_limited": 429}.get(error.code, 400)
        if _is_htmx(request):
            return render(
                request,
                "downloads/_error.html",
                {"error_code": error.code},
                status=status,
            )
        return JsonResponse({"error": error.code}, status=status)
    if _is_htmx(request):
        return render(
            request,
            "downloads/_inspection.html",
            {"task": _store().find(token)},
            status=202,
        )
    return JsonResponse(
        {
            "token": token,
            "inspection_url": reverse("task-inspection", args=[token]),
        },
        status=202,
    )


@require_GET
def task_inspection(request, token: str):
    _, task = _owned_task(request, token)
    if _is_htmx(request):
        return render(request, "downloads/_inspection.html", {"task": task})
    return JsonResponse(_public_task(task, include_formats=True))


@require_POST
def task_download(request, token: str):
    identity, _ = _owned_task(request, token)
    try:
        request_download(
            identity,
            token,
            request.POST.get("format_id", ""),
            tasks=_store(),
            queue=_queue(),
            quota=MongoCommandQuota(),
            now=timezone.now,
            max_bytes=settings.DOWNLOAD_MAX_BYTES,
        )
    except QuotaExceeded:
        return JsonResponse({"error": "quota_exceeded"}, status=429)
    except TaskRejected as error:
        status = 404 if error.code == "not_found" else 409
        return JsonResponse({"error": error.code}, status=status)
    if _is_htmx(request):
        return render(
            request,
            "downloads/_status.html",
            {"task": _store().find(token)},
            status=202,
        )
    return JsonResponse(
        {"status_url": reverse("task-status", args=[token])},
        status=202,
    )


@require_GET
def task_status(request, token: str):
    _, task = _owned_task(request, token)
    if _is_htmx(request):
        return render(request, "downloads/_status.html", {"task": task})
    payload = _public_task(task)
    if TaskState(task.state) is TaskState.COMPLETED and task.expires_at > timezone.now():
        payload["file_url"] = reverse("task-file", args=[token])
    return JsonResponse(payload)


@require_GET
def task_file(request, token: str):
    _, task = _owned_task(request, token)
    if TaskState(task.state) is not TaskState.COMPLETED or task.expires_at <= timezone.now():
        raise Http404
    root = Path(settings.DOWNLOAD_ROOT).resolve()
    candidate = (root / task.output_file).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise Http404 from error
    if candidate == root or not candidate.is_file():
        raise Http404

    extension = candidate.suffix.lower()
    filename = f"{slugify(task.title) or 'fetchly-media'}{extension}"
    response = FileResponse(candidate.open("rb"), as_attachment=True, filename=filename)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _public_task(task, *, include_formats: bool = False) -> dict:
    payload = {
        "state": str(task.state),
        "title": task.title,
        "provider": getattr(task, "provider", ""),
        "progress_percent": task.progress_percent,
        "error_code": task.error_code or None,
        "output_size": task.output_size or None,
        "expires_at": task.expires_at.isoformat(),
    }
    if include_formats:
        payload["formats"] = [
            {
                "id": getattr(item, "format_id", getattr(item, "id", "")),
                "label": item.label,
                "extension": item.extension,
                "kind": item.kind,
                "height": item.height,
                "estimated_bytes": item.estimated_bytes,
            }
            for item in task.formats
        ]
    return payload


def _queue():
    from fetchly.rq import get_queue

    return get_queue()
