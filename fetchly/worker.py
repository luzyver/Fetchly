import os
import threading
import time

import django
from rq import Repeat, Worker


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fetchly.settings")
    django.setup()

    from django.conf import settings
    from redis import Redis

    from fetchly.rq import get_queue

    queue = get_queue()
    if queue.fetch_job("fetchly-maintenance") is None:
        # ponytail: RQ requires a finite count; one million intervals is effectively permanent.
        queue.enqueue(
            "downloads.jobs.maintenance_task",
            job_id="fetchly-maintenance",
            repeat=Repeat(times=1_000_000, interval=settings.MAINTENANCE_INTERVAL_SECONDS),
        )

    def heartbeat():
        client = Redis.from_url(settings.REDIS_URL)
        while True:
            client.set(settings.WORKER_HEARTBEAT_KEY, "ok", ex=30)
            time.sleep(10)

    threading.Thread(target=heartbeat, daemon=True).start()
    Worker([queue]).work(with_scheduler=True)


if __name__ == "__main__":
    main()
