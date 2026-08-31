from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django_mongodb_backend.fields import ObjectIdAutoField


def test_contrib_models_use_object_id_primary_keys():
    for model in (LogEntry, Group, Permission, User, ContentType):
        assert isinstance(model._meta.pk, ObjectIdAutoField), model.__name__
