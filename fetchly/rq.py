from django.conf import settings
from redis import Redis
from rq import Queue


def get_queue(name: str = "media") -> Queue:
    return Queue(name, connection=Redis.from_url(settings.REDIS_URL))
