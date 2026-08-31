from django.apps import AppConfig


class DownloadsConfig(AppConfig):
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"
    name = "downloads"
