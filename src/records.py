from dataclasses import dataclass
from datetime import datetime

@dataclass
class QueueEntry:
    user_id: int
    username: str
    student_name: str
    details: str
    is_passoff: bool
    timestamp: datetime
    in_person: bool
    phase: str

def format_phase(phase: str) -> str:
    p = phase.strip().upper() if phase else "?"
    if p in ("0", "1", "2", "3", "4", "5", "6"):
        return f"Phase {p}"
    elif p == "E":
        return "Exam"
    elif p == "G":
        return "Github Repo"
    else:
        return "Misc"