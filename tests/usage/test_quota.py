from dataclasses import dataclass, field
from threading import Lock, Thread

import pytest

from usage.identity import VisitorIdentity
from usage.quota import QuotaExceeded, QuotaReservation, reserve_quota


@dataclass
class FakeQuotaStore:
    failing_identifier: str | None = None
    reservations: dict[str, dict[str, int]] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)

    def reserve(
        self,
        identifier: str,
        task_token: str,
        byte_count: int,
        limit_bytes: int,
        active_limit: int,
    ) -> bool:
        with self.lock:
            if identifier == self.failing_identifier:
                return False
            entries = self.reservations.setdefault(identifier, {})
            if task_token in entries:
                return True
            if len(entries) >= active_limit or sum(entries.values()) + byte_count > limit_bytes:
                return False
            entries[task_token] = byte_count
            return True

    def release(self, identifier: str, task_token: str, byte_count: int) -> None:
        with self.lock:
            self.reservations.setdefault(identifier, {}).pop(task_token, None)


@pytest.fixture
def identity():
    return VisitorIdentity("fp-id", "ip-id", "owner-id", 0)


def test_second_identifier_failure_compensates_first(identity):
    store = FakeQuotaStore(failing_identifier=identity.ip_id)

    with pytest.raises(QuotaExceeded):
        reserve_quota(
            store,
            identity,
            "task-a",
            200,
            limit_bytes=1_000,
            active_limit=1,
        )

    assert store.reservations[identity.fingerprint_id] == {}


def test_parallel_reservations_cannot_exceed_limit(identity):
    store = FakeQuotaStore()
    successes: list[QuotaReservation] = []

    def attempt(task_token: str) -> None:
        try:
            successes.append(
                reserve_quota(
                    store,
                    identity,
                    task_token,
                    700,
                    limit_bytes=1_000,
                    active_limit=2,
                )
            )
        except QuotaExceeded:
            pass

    threads = [Thread(target=attempt, args=(token,)) for token in ("task-a", "task-b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert sum(store.reservations[identity.fingerprint_id].values()) == 700
