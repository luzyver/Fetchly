import pytest

from downloads.states import InvalidTransition, TaskState, transition


def test_download_happy_path():
    state = TaskState.INSPECTION_QUEUED
    for target in (
        TaskState.INSPECTING,
        TaskState.READY,
        TaskState.DOWNLOAD_QUEUED,
        TaskState.DOWNLOADING,
        TaskState.COMPLETED,
    ):
        state = transition(state, target)

    assert state is TaskState.COMPLETED


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (TaskState.COMPLETED, TaskState.DOWNLOADING),
        (TaskState.FAILED, TaskState.READY),
        (TaskState.EXPIRED, TaskState.DOWNLOAD_QUEUED),
        (TaskState.INSPECTION_QUEUED, TaskState.COMPLETED),
    ],
)
def test_invalid_transition_is_rejected(source, target):
    with pytest.raises(InvalidTransition):
        transition(source, target)


@pytest.mark.parametrize(
    "state",
    [TaskState.COMPLETED, TaskState.FAILED, TaskState.BLOCKED, TaskState.EXPIRED],
)
def test_terminal_states_are_terminal(state):
    assert state.is_terminal is True


def test_retry_can_requeue_the_active_stage():
    assert (
        transition(TaskState.INSPECTING, TaskState.INSPECTION_QUEUED) is TaskState.INSPECTION_QUEUED
    )
    assert transition(TaskState.DOWNLOADING, TaskState.DOWNLOAD_QUEUED) is TaskState.DOWNLOAD_QUEUED
