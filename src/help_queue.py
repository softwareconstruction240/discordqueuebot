import asyncio
from typing import Optional
from data_access.db import get_times_helped_today
from records import QueueEntry

class HelpQueue:
    def __init__(self):
        self.entries: list[QueueEntry] = []
        self.lock = asyncio.Lock()
        self.is_open = False

    async def add(self, entry: QueueEntry):
        async with self.lock:
            self.entries.append(entry)

    async def remove(self, user_id: int):
        async with self.lock:
            self.entries = [
                e for e in self.entries if e.user_id != user_id
            ]

    async def get_position(self, user_id: int) -> Optional[int]:
        async with self.lock:
            for i, e in enumerate(self.entries):
                if e.user_id == user_id:
                    return i + 1
        return None
    
    async def is_in_queue(self, user_id: int):
        async with self.lock:
            for entry in self.entries:
                if entry.user_id == user_id:
                    return True
        return False

    async def next(self, passoff_only=False, online_only=False) -> Optional[QueueEntry]:
        async with self.lock:
            if passoff_only:
                for i, e in enumerate(self.entries):
                    if e.is_passoff:
                        if online_only and e.in_person:
                            return None
                        else:
                            return self.entries.pop(i)

            elif online_only:
                for i, e in enumerate(self.entries):
                    if not e.in_person:
                        return self.entries.pop(i)
                return None
            else:
                return self.entries.pop(0) if self.entries else None

    async def view(self) -> str:
        async with self.lock:
            if not self.entries:
                return "Queue is empty."

            out = ["Students in queue:\n"]
            for i, e in enumerate(self.entries, start=1):
                p_tag = "PASSOFF" if e.is_passoff else "HELP"
                o_tag = "ONLINE" if not e.in_person else "IN-PERSON"
                times_helped = await get_times_helped_today(e.user_id)
                display_name = e.username
                if e.student_name:
                    display_name = f"{e.username} ({e.student_name})"
                out.append(
                    f"{i}. {display_name} - {p_tag} - {o_tag} - {e.details} "
                    f"(helped {times_helped} time{'s' if times_helped != 1 else ''} today)"
                )

            return "\n".join(out)
        
    async def get_front(self) -> Optional[QueueEntry]:
        async with self.lock:
            return self.entries[0] if self.entries else None
    
    async def clear(self):
        async with self.lock:
            self.entries.clear()