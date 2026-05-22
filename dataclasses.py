from dataclasses import dataclass
from datetime import datetime

@dataclass
class QueueEntry:
    user_id: int
    username: str
    details: str
    is_passoff: bool
    timestamp: datetime
    in_person: bool