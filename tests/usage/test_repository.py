from datetime import date

import mongomock

from usage.repository import MongoQuotaStore


def test_reserve_is_idempotent_per_task_and_enforces_limit():
    collection = mongomock.MongoClient().fetchly.daily_usage
    store = MongoQuotaStore(collection, day_provider=lambda: date(2026, 8, 31))

    assert store.reserve("fp-id", "task-a", 700, 1_000, 2) is True
    assert store.reserve("fp-id", "task-a", 700, 1_000, 2) is True
    assert store.reserve("fp-id", "task-b", 400, 1_000, 2) is False

    document = collection.find_one({"_id": "2026-08-31:fp-id"})
    assert document["reserved_bytes"] == 700
    assert document["active_tasks"] == 1


def test_release_removes_only_matching_reservation():
    collection = mongomock.MongoClient().fetchly.daily_usage
    store = MongoQuotaStore(collection, day_provider=lambda: date(2026, 8, 31))
    store.reserve("fp-id", "task-a", 300, 1_000, 2)
    store.reserve("fp-id", "task-b", 400, 1_000, 2)

    store.release("fp-id", "task-a", 300)

    document = collection.find_one({"_id": "2026-08-31:fp-id"})
    assert document["reserved_bytes"] == 400
    assert document["active_tasks"] == 1
    assert [item["task_token"] for item in document["reservations"]] == ["task-b"]


def test_settle_converts_reservation_to_actual_usage():
    collection = mongomock.MongoClient().fetchly.daily_usage
    store = MongoQuotaStore(collection, day_provider=lambda: date(2026, 8, 31))
    store.reserve("fp-id", "task-a", 700, 1_000, 1)

    assert store.settle("fp-id", "task-a", reserved_bytes=700, actual_bytes=640) is True

    document = collection.find_one({"_id": "2026-08-31:fp-id"})
    assert document["reserved_bytes"] == 0
    assert document["charged_bytes"] == 640
    assert document["active_tasks"] == 0
    assert document["reservations"] == []
