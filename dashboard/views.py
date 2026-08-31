from functools import wraps

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from downloads.models import DownloadTask
from downloads.states import TaskState
from usage.models import AccessRule

from .forms import AccessRuleForm


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('staff-login')}?next={request.path}")
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


@staff_required
def index(request):
    return render(request, "dashboard/index.html", _dashboard_context(request))


def _dashboard_context(request):
    tasks = DownloadTask.objects.all()
    search = request.GET.get("q", "").strip()
    state = request.GET.get("state", "").strip()
    if search:
        tasks = tasks.filter(Q(title__icontains=search) | Q(provider__icontains=search))
    if state in {item.value for item in TaskState}:
        tasks = tasks.filter(state=state)
    today = timezone.localdate()
    return {
        "counts": {
            "queued": DownloadTask.objects.filter(
                state__in=[TaskState.INSPECTION_QUEUED, TaskState.DOWNLOAD_QUEUED]
            ).count(),
            "active": DownloadTask.objects.filter(
                state__in=[TaskState.INSPECTING, TaskState.DOWNLOADING]
            ).count(),
            "completed": DownloadTask.objects.filter(
                state=TaskState.COMPLETED,
                updated_at__date=today,
            ).count(),
            "failed": DownloadTask.objects.filter(
                state__in=[TaskState.FAILED, TaskState.BLOCKED]
            ).count(),
        },
        "tasks": list(tasks.order_by("-updated_at")[:50]),
        "rules": list(AccessRule.objects.order_by("-updated_at")[:50]),
        "rule_form": AccessRuleForm(),
        "search": search,
        "selected_state": state,
        "states": list(TaskState),
    }


@require_POST
@staff_required
def add_rule(request):
    form = AccessRuleForm(request.POST)
    if form.is_valid():
        AccessRule.objects.create(
            **form.cleaned_data,
            created_by_id=str(request.user.pk),
            created_by_name=request.user.get_username(),
        )
        return redirect("dashboard-index")
    context = _dashboard_context(request)
    context["rule_form"] = form
    return render(request, "dashboard/index.html", context, status=400)


@require_POST
@staff_required
def delete_rule(request, rule_id: str):
    AccessRule.objects.filter(pk=rule_id).delete()
    return redirect("dashboard-index")
