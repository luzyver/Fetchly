from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("identity", views.set_identity, name="set-identity"),
    path("tasks/inspect", views.inspect, name="task-inspect"),
    path("tasks/<str:token>/inspection", views.task_inspection, name="task-inspection"),
    path("tasks/<str:token>/download", views.task_download, name="task-download"),
    path("tasks/<str:token>/status", views.task_status, name="task-status"),
    path("tasks/<str:token>/file", views.task_file, name="task-file"),
]
