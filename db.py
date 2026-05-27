import sqlite3
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from typing import Optional
from discord.ext import tasks

conn: sqlite3.Connection = sqlite3.connect("queue.db")
cursor: sqlite3.Cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_stats (
    user_id INTEGER PRIMARY KEY,
    user_name STRING,
    student_name STRING,
    total_help INTEGER DEFAULT 0,
    daily_help INTEGER DEFAULT 0,
    last_reset TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_incidents (
    id INTEGER PRIMARY KEY,
    last_incident TEXT,
    last_issue TEXT
)
""")

# Ensure older databases gain the new student_name column.
cursor.execute("PRAGMA table_info(user_stats)")
columns = [row[1] for row in cursor.fetchall()]
if "student_name" not in columns:
    cursor.execute("ALTER TABLE user_stats ADD COLUMN student_name STRING")

cursor.execute("PRAGMA table_info(bot_incidents)")
bot_columns = [row[1] for row in cursor.fetchall()]
if "last_issue" not in bot_columns:
    cursor.execute("ALTER TABLE bot_incidents ADD COLUMN last_issue TEXT")

conn.commit()

@tasks.loop(
    time=time(
        hour=23,
        minute=59,
        tzinfo=ZoneInfo("America/Denver")
    )
)
async def daily_reset():
    cursor.execute("""
        UPDATE user_stats
        SET daily_help = 0
    """)
    conn.commit()

    print("Daily help counts reset.")


def increment_help(user_id: int, user_name: str, student_name: Optional[str] = None):
    cursor.execute("""
        INSERT INTO user_stats (user_id, user_name, student_name, total_help, daily_help, last_reset)
        VALUES (?, ?, ?, 1, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            user_name = ?,
            total_help = total_help + 1,
            daily_help = daily_help + 1
    """, (user_id, user_name, student_name or "", str(date.today()), user_name))

    if student_name:
        _update_student_name_if_longer(user_id, student_name)

    conn.commit()


def _update_student_name_if_longer(user_id: int, student_name: str):

    cursor.execute("SELECT student_name FROM user_stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    existing_name = row[0] if row else ""
    if len(student_name) > len(existing_name or ""):
        cursor.execute(
            "UPDATE user_stats SET student_name = ? WHERE user_id = ?",
            (student_name, user_id)
        )

def record_bot_issue(timestamp: datetime, issue: str):
    cursor.execute(
        "INSERT INTO bot_incidents (id, last_incident, last_issue) VALUES (1, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET last_incident = ?, last_issue = ?",
        (timestamp.isoformat(), issue, timestamp.isoformat(), issue)
    )
    conn.commit()


def get_last_incident_info() -> tuple[Optional[int], Optional[str]]:
    cursor.execute("SELECT last_incident, last_issue FROM bot_incidents WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row[0]:
        return None, None

    last_incident = datetime.fromisoformat(row[0])
    delta = datetime.now() - last_incident
    return delta.days, row[1] or None


def get_student_info() -> tuple[list]:
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

    result: tuple[list] = (["Name", "Total Help Queue visits", "Times Helped Today"], [])

    for row in cursor.execute("SELECT COALESCE(NULLIF(student_name, ''), user_name), total_help, daily_help FROM user_stats"):
        result[1].append(row)

    return result

def get_times_helped_today(user_id: int) -> int:
    cursor.execute("SELECT daily_help FROM user_stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0