from dataclasses import dataclass
from typing import Protocol

from usage.identity import VisitorIdentity


class QuotaExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class QuotaReservation:
    task_token: str
    byte_count: int


class QuotaStore(Protocol):
    def reserve(
        self,
        identifier: str,
        task_token: str,
        byte_count: int,
        limit_bytes: int,
        active_limit: int,
    ) -> bool: ...

    def release(self, identifier: str, task_token: str, byte_count: int) -> None: ...


def reserve_quota(
    store: QuotaStore,
    identity: VisitorIdentity,
    task_token: str,
    byte_count: int,
    *,
    limit_bytes: int,
    active_limit: int,
) -> QuotaReservation:
    reserved_fingerprint = store.reserve(
        identity.fingerprint_id,
        task_token,
        byte_count,
        limit_bytes,
        active_limit,
    )
    if not reserved_fingerprint:
        raise QuotaExceeded("Daily quota or active task limit reached")

    reserved_ip = store.reserve(
        identity.ip_id,
        task_token,
        byte_count,
        limit_bytes,
        active_limit,
    )
    if not reserved_ip:
        store.release(identity.fingerprint_id, task_token, byte_count)
        raise QuotaExceeded("Daily quota or active task limit reached")

    return QuotaReservation(task_token, byte_count)
