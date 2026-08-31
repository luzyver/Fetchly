from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CleanupResult:
    deleted: int = 0
    missing: int = 0
    refused: int = 0


def cleanup_expired(now, *, tasks, download_root: Path) -> CleanupResult:
    root = Path(download_root).resolve()
    deleted = missing = refused = 0
    for task in tasks.expired_candidates(now):
        candidate = (root / task.output_file).resolve()
        if candidate == root or not candidate.is_relative_to(root):
            refused += 1
            continue
        if candidate.is_file():
            candidate.unlink()
            deleted += 1
        else:
            missing += 1
        tasks.mark_expired(str(task.id))
        try:
            candidate.parent.rmdir()
        except OSError:
            pass
    return CleanupResult(deleted, missing, refused)
