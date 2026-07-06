import datetime
from data_access.queue_history_dao import get_queue_history

class NoTasOnlineError(Exception):
    pass

async def calculate_expected_wait_time(
    num_tas: int,
    queue_size: int,
    available_tas: int | None = None,
    position: int = 1,
) -> int:
    """Returns the expected wait time in seconds for the current queue.

    Args:
        num_tas: Total number of TAs currently in voice.
        queue_size: Total number of students currently in the queue.
        available_tas: Optional number of TAs currently available (not already helping).
        position: The position in the queue to estimate for, 1-based.

    Default fallback behavior is centralized here so callers only need to pass
    the relevant state and display the resulting number of seconds.

    Returns:
        wait time in seconds

    Raises:
        NoTasOnlineError if there are no TAs online
    """
    if num_tas <= 0:
        raise NoTasOnlineError

    if available_tas is not None and available_tas >= position:
        return 20 * position

    queue_history: list = await get_queue_history()
    recent = list(queue_history)[::-1]
    samples = min(20, len(recent))
    if samples == 0:
        return 180 * position

    total_wait = datetime.timedelta()
    for history_item in recent[:samples]:
        enqueue_time = datetime.datetime.fromisoformat(history_item["enqueue_time"])
        dequeue_time = datetime.datetime.fromisoformat(history_item["dequeue_time"])
        total_wait += dequeue_time - enqueue_time

    average_wait: datetime.timedelta = total_wait / samples
    base_wait = max(int((queue_size / num_tas) * average_wait.total_seconds()), 180)
    return base_wait * position


