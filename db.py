import sqlite3
from datetime import date, datetime, time
from typing import List, Optional
from zoneinfo import ZoneInfo
from discord.ext import tasks

conn: sqlite3.Connection = sqlite3.connect("queue.db", detect_types=sqlite3.PARSE_DECLTYPES)
conn.row_factory = sqlite3.Row


def _initialize_database() -> None:
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                user_name STRING,
                student_name STRING,
                total_help INTEGER DEFAULT 0,
                daily_help INTEGER DEFAULT 0,
                last_reset TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_incidents (
                id INTEGER PRIMARY KEY,
                last_incident TEXT,
                last_issue TEXT
            )
            """
        )


_initialize_database()

@tasks.loop(
    time=time(
        hour=23,
        minute=59,
        tzinfo=ZoneInfo("America/Denver")
    )
)
async def daily_reset() -> None:
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_stats SET daily_help = 0"
    )
    conn.commit()

    print("Daily help counts reset.")


def increment_help(user_id: int, user_name: str, student_name: Optional[str] = None) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO user_stats (user_id, user_name, student_name, total_help, daily_help, last_reset)
        VALUES (?, ?, ?, 1, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            user_name = ?,
            total_help = total_help + 1,
            daily_help = daily_help + 1
        """,
        (user_id, user_name, student_name or "", str(date.today()), user_name),
    )

    if student_name:
        _update_student_name_if_longer(user_id, student_name)

    conn.commit()


def _update_student_name_if_longer(user_id: int, student_name: str) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT student_name FROM user_stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    existing_name = row[0] if row else ""
    if len(student_name) > len(existing_name or ""):
        cursor.execute(
            "UPDATE user_stats SET student_name = ? WHERE user_id = ?",
            (student_name, user_id),
        )
        conn.commit()

def record_bot_issue(timestamp: datetime, issue: str) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bot_incidents (id, last_incident, last_issue) VALUES (1, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET last_incident = ?, last_issue = ?",
        (timestamp.isoformat(), issue, timestamp.isoformat(), issue),
    )
    conn.commit()


def get_last_incident_info() -> tuple[Optional[int], Optional[str]]:
    cursor = conn.cursor()
    cursor.execute("SELECT last_incident, last_issue FROM bot_incidents WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row[0]:
        return None, None

    try:
        last_incident = datetime.fromisoformat(row[0])
    except ValueError:
        return None, row[1] or None

    delta = datetime.now() - last_incident
    return delta.days, row[1] or None


def get_student_info() -> tuple[List[str], List[tuple[str, int, int]]]:
    """Get information about students that have joined the help queue.

    Returns:
        A tuple containing 2 lists. 
        The first list contains strings indicating what information corresponds to which index of the student's information. 
        The second list contains a list for each student in the database. 

    _**Example:**_ There are two users in the database, and the first list contains the strings "username" and "times helped today"
    The resulting tuple would look like the following:\n
     `( ["username", "times helped today"],`\n `[ ["Freddy", 1],`\n `["Howie", 3] ] )`\n
    In practice more information is given by this function.
    """

    result: tuple[List[str], List[tuple[str, int, int]]] = (
        ["Name", "Total Help Queue visits", "Times Helped Today"],
        [],
    )

    cursor = conn.cursor()
    for row in cursor.execute("SELECT COALESCE(NULLIF(student_name, ''), user_name), total_help, daily_help FROM user_stats"):
        result[1].append((row[0], row[1], row[2]))

    return result

def get_times_helped_today(user_id: int) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT daily_help FROM user_stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return int(row[0]) if row else 0