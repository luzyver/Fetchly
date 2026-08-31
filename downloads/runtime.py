from django.conf import settings
from django.db import connection
from django.utils import timezone
from redis import Redis

from usage.access import AccessDecision, Rule, decide_access
from usage.models import AccessRule
from usage.quota import reserve_quota
from usage.ratelimit import hit_rate_limit
from usage.repository import MongoQuotaStore


def _quota_store() -> MongoQuotaStore:
    connection.ensure_connection()
    return MongoQuotaStore(connection.database["daily_usage"], timezone.localdate)


class MongoCommandQuota:
    def reserve(self, identity, token: str, byte_count: int) -> None:
        reserve_quota(
            _quota_store(),
            identity,
            token,
            byte_count,
            limit_bytes=settings.DAILY_QUOTA_BYTES,
            active_limit=settings.ACTIVE_DOWNLOAD_LIMIT,
        )

    def release(self, identity, token: str, byte_count: int) -> None:
        store = _quota_store()
        store.release(identity.fingerprint_id, token, byte_count)
        store.release(identity.ip_id, token, byte_count)


class MongoJobQuota:
    def settle(self, task, byte_count: int) -> None:
        store = _quota_store()
        for identifier in (task.fingerprint_id, task.ip_id):
            store.settle(
                identifier,
                task.public_token,
                reserved_bytes=task.reserved_bytes,
                actual_bytes=byte_count,
            )

    def release(self, task) -> None:
        store = _quota_store()
        for identifier in (task.fingerprint_id, task.ip_id):
            store.release(identifier, task.public_token, task.reserved_bytes)


def access_allowed(identity) -> bool:
    rules = [
        Rule(rule.kind, rule.subject_type, rule.subject_value) for rule in AccessRule.objects.all()
    ]
    return decide_access(rules, identity, "") is not AccessDecision.BLOCK


def rate_limited(bucket: str, identifier: str) -> bool:
    client = Redis.from_url(settings.REDIS_URL)
    return hit_rate_limit(
        client,
        bucket,
        identifier,
        settings.INSPECTION_RATE_LIMIT,
        settings.INSPECTION_RATE_WINDOW_SECONDS,
    )
