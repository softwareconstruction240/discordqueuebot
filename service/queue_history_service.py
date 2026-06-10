import datetime
from db import get_queue_history


def calculate_expected_wait_time(num_tas: int, queue_size: int) -> int:
    """Returns the expected wait time based on the number of active TAs and students currently in the queue based on """
    # defensive checks
    if num_tas <= 0:
        print("no TAs")
        return 0

    if queue_size == 0: 
        queue_size = 1 

    queue_history: list = get_queue_history()

    # work on a reversed copy so most recent items are first
    recent = list(queue_history)[::-1]
    samples = min(5, len(recent))
    if samples == 0:
        print("no queue history items")
        return 0

    total_wait = datetime.timedelta()
    for i in range(samples):
        history_item = recent[i]
        enqueue_time = datetime.datetime.fromisoformat(history_item[4])
        dequeue_time = datetime.datetime.fromisoformat(history_item[5])
        total_wait += dequeue_time - enqueue_time

    average_wait: datetime.timedelta = total_wait / samples
    print(average_wait)
    return int((queue_size / num_tas) * (average_wait.total_seconds()))
