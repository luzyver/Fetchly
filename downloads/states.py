from enum import StrEnum


class InvalidTransition(ValueError):
    pass


class TaskState(StrEnum):
    INSPECTION_QUEUED = "inspection_queued"
    INSPECTING = "inspecting"
    READY = "ready"
    DOWNLOAD_QUEUED = "download_queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.FAILED,
            self.BLOCKED,
            self.EXPIRED,
        }


ALLOWED_TRANSITIONS = {
    TaskState.INSPECTION_QUEUED: {
        TaskState.INSPECTING,
        TaskState.FAILED,
        TaskState.BLOCKED,
        TaskState.EXPIRED,
    },
    TaskState.INSPECTING: {
        TaskState.INSPECTION_QUEUED,
        TaskState.READY,
        TaskState.FAILED,
        TaskState.BLOCKED,
        TaskState.EXPIRED,
    },
    TaskState.READY: {TaskState.DOWNLOAD_QUEUED, TaskState.EXPIRED},
    TaskState.DOWNLOAD_QUEUED: {
        TaskState.DOWNLOADING,
        TaskState.FAILED,
        TaskState.EXPIRED,
    },
    TaskState.DOWNLOADING: {
        TaskState.DOWNLOAD_QUEUED,
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.EXPIRED,
    },
}


def transition(source: TaskState, target: TaskState) -> TaskState:
    if target not in ALLOWED_TRANSITIONS.get(source, set()):
        raise InvalidTransition(f"Cannot transition from {source} to {target}")
    return target
