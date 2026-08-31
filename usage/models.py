from django.db import models
from django_mongodb_backend.fields import EmbeddedModelArrayField, ObjectIdAutoField
from django_mongodb_backend.models import EmbeddedModel


class UsageReservation(EmbeddedModel):
    task_token = models.CharField(max_length=128)
    bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField()


class DailyUsage(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    identifier = models.CharField(max_length=64)
    identifier_type = models.CharField(max_length=16)
    day = models.DateField()
    charged_bytes = models.PositiveBigIntegerField(default=0)
    reserved_bytes = models.PositiveBigIntegerField(default=0)
    active_tasks = models.PositiveIntegerField(default=0)
    reservations = EmbeddedModelArrayField(UsageReservation, default=list)

    class Meta:
        db_table = "daily_usage"
        constraints = [
            models.UniqueConstraint(
                fields=["identifier", "day"],
                name="unique_usage_identifier_day",
            )
        ]


class AccessRule(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    kind = models.CharField(
        max_length=16, choices=(("whitelist", "Whitelist"), ("blacklist", "Blacklist"))
    )
    subject_type = models.CharField(max_length=16)
    subject_value = models.CharField(max_length=128)
    note = models.CharField(max_length=255, blank=True)
    created_by_id = models.CharField(max_length=64, blank=True)
    created_by_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "access_rules"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "subject_type", "subject_value"],
                name="unique_access_rule",
            )
        ]
