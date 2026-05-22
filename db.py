import sqlite3
from datetime import date, time
from zoneinfo import ZoneInfo
from discord.ext import tasks

conn: sqlite3.Connection = sqlite3.connect("queue.db")
cursor: sqlite3.Cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_stats (
    user_id INTEGER PRIMARY KEY,
    user_name STRING,
    total_help INTEGER DEFAULT 0,
    daily_help INTEGER DEFAULT 0,
    last_reset TEXT
)
""")

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


def increment_help(user_id: int, user_name: str):
    cursor.execute("""
        INSERT INTO user_stats (user_id, user_name, total_help, daily_help, last_reset)
        VALUES (?, ?, 1, 1, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            user_name = ?,
            total_help = total_help + 1,
            daily_help = daily_help + 1
    """, (user_id, user_name, str(date.today()), user_name))

    conn.commit()

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

    result: tuple[list] = (["Username", "Total Help Queue visits", "Times Helped Today"], [])

    for row in cursor.execute("SELECT user_name, total_help, daily_help FROM user_stats"):
        result[1].append(row)

    return result

def get_times_helped_today(user_id: int) -> int:
    cursor.execute("SELECT daily_help FROM user_stats WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0