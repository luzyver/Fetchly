from datetime import UTC, datetime
from types import SimpleNamespace

from downloads.cleanup import cleanup_expired


class FakeTasks:
    def __init__(self, candidates):
        self.candidates = candidates
        self.expired = []

    def expired_candidates(self, now):
        return self.candidates

    def mark_expired(self, task_id):
        self.expired.append(task_id)


def test_cleanup_deletes_only_paths_below_download_root(tmp_path):
    media = tmp_path / "safe-id" / "media.mp4"
    media.parent.mkdir()
    media.write_bytes(b"media")
    tasks = FakeTasks(
        [
            SimpleNamespace(id="safe", output_file="safe-id/media.mp4"),
            SimpleNamespace(id="escape", output_file="../secret.txt"),
            SimpleNamespace(id="missing", output_file="gone/media.mp4"),
        ]
    )

    result = cleanup_expired(datetime.now(UTC), tasks=tasks, download_root=tmp_path)

    assert result.deleted == 1
    assert result.refused == 1
    assert result.missing == 1
    assert tasks.expired == ["safe", "missing"]
    assert not media.exists()


def test_cleanup_is_idempotent_when_file_is_already_missing(tmp_path):
    tasks = FakeTasks([SimpleNamespace(id="done", output_file="gone/media.mp4")])

    first = cleanup_expired(datetime.now(UTC), tasks=tasks, download_root=tmp_path)
    second = cleanup_expired(datetime.now(UTC), tasks=tasks, download_root=tmp_path)

    assert first.missing == second.missing == 1
