from django.urls import include, path

from fetchly import views

urlpatterns = [
    path("admin/", include("dashboard.urls")),
    path("", include("downloads.urls")),
    path("health/live", views.health_live, name="health-live"),
    path("health/ready", views.health_ready, name="health-ready"),
]
