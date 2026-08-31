from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="staff-login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="staff-logout"),
    path("", views.index, name="dashboard-index"),
    path("rules/add", views.add_rule, name="dashboard-rule-add"),
    path("rules/<str:rule_id>/delete", views.delete_rule, name="dashboard-rule-delete"),
]
