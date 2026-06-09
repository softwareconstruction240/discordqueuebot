import io
import sqlite3
import discord
import csv
from datetime import date, datetime, time
from typing import List, Optional
from zoneinfo import ZoneInfo
from discord.ext import tasks
from records import QueueEntry
from ui.helpers.discord_helpers import update_queue_messages

conn: sqlite3.Connection = sqlite3.connect("./resources/queue.db", detect_types=sqlite3.PARSE_DECLTYPES)
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
                incident_timestamp TEXT,
                incident TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queue_settings (
                id INTEGER PRIMARY KEY,
                open_hour INTEGER DEFAULT 8,
                open_minute INTEGER DEFAULT 0,
                close_hour INTEGER DEFAULT 20,
                close_minute INTEGER DEFAULT 0
            )
            """
        )        
        
        # dequeue_time refers to the time the TA begins helping the student, as the student is no longer waiting in the queue
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queue_history (
                id INTEGER PRIMARY KEY,
                student_name TEXT NOT NULL,
                TA_name TEXT NOT NULL,
                question TEXT,
                enqueue_time TEXT NOT NULL,
                dequeue_time TEXT NOT NULL,
                is_passoff INTEGER CHECK (is_passoff IN (0,1)),
                in_person INTEGER CHECK (in_person IN (0,1)),
                time_finished TEXT
                )
            """
        )


        # Ensure queue_settings has a default row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM queue_settings")
        if cursor.fetchone()[0] == 0:
            conn.execute("INSERT INTO queue_settings (id, open_hour, open_minute, close_hour, close_minute) VALUES (1, 8, 0, 20, 0)")


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
    """
    Records a help session for a user, incrementing both their total and daily help counts.
    Creates a new user record if one does not exist.

    Args:
        user_id (int): The Discord user ID.
        user_name (str): The user's Discord username.
        student_name (Optional[str]): The student's actual name, if provided.
    """
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
        _update_student_name(user_id, student_name)

    conn.commit()


def _update_student_name(user_id: int, student_name: str) -> None:
    """
    Updates the student's name in the database if the new name provided is longer 
    than the currently stored name.

    Args:
        user_id (int): The Discord user ID of the student.
        student_name (str): The new name to evaluate and potentially store.
    """
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
        "INSERT INTO bot_incidents (incident_timestamp, incident) VALUES (?, ?)",
        (timestamp.isoformat(), issue)
    )
    conn.commit()


def get_last_incident_info() -> tuple[Optional[int], Optional[str]]:
    cursor = conn.cursor()
    cursor.execute("SELECT incident_timestamp, incident FROM bot_incidents ORDER BY incident_timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if not row or not row[0]:
        return None, None

    try:
        last_incident_time = datetime.fromisoformat(row[0])
    except ValueError:
        return None, row[1] or None

    delta = datetime.now() - last_incident_time
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


def get_queue_times() -> tuple[int, int, int, int]:
    """Get the configured queue open and close times.
    
    Returns:
        Tuple of (open_hour, open_minute, close_hour, close_minute)
    """
    cursor = conn.cursor()
    cursor.execute("SELECT open_hour, open_minute, close_hour, close_minute FROM queue_settings WHERE id = 1")
    row = cursor.fetchone()
    if row:
        return int(row[0]), int(row[1]), int(row[2]), int(row[3])
    return 8, 0, 20, 0  # Default to 8:00am-8:00pm


def set_queue_times(open_hour: int, open_minute: int, close_hour: int, close_minute: int) -> None:
    """Set the queue open and close times.
    
    Args:
        open_hour: Hour to open (0-23)
        open_minute: Minute to open (0-59)
        close_hour: Hour to close (0-23)
        close_minute: Minute to close (0-59)
    """
    if not (0 <= open_hour <= 23 and 0 <= open_minute <= 59 and 0 <= close_hour <= 23 and 0 <= close_minute <= 59):
        raise ValueError("Hours must be 0-23 and minutes must be 0-59")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE queue_settings SET open_hour = ?, open_minute = ?, close_hour = ?, close_minute = ? WHERE id = 1",
        (open_hour, open_minute, close_hour, close_minute)
    )
    conn.commit()

def add_queue_history_item(queue_entry: QueueEntry, ta: str) -> int:
    """Adds information about the student's help queue entry to the database and returns its associated key to be used for later indexing.
    
    Returns: 
        int => id of queue history item
    """
    dequeue_time = datetime.now()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO queue_history (
            student_name,
            ta_name,
            question,
            enqueue_time,
            dequeue_time,
            passoff,
            in_person
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (queue_entry.student_name, 
              ta, 
              queue_entry.details, 
              queue_entry.timestamp.isoformat(), 
              dequeue_time.isoformat(), 
              queue_entry.is_passoff, 
              queue_entry.in_person
              )
    )
    generated_id = cursor.lastrowid
    conn.commit()

    return generated_id

def _get_dequeue_time(id: int) -> datetime:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT dequeue_time FROM queue_history WHERE id = ?
        """, (id)
    )
    row = cursor.fetchone()
    return datetime.fromisoformat(row[0])
    

def set_time_helped(id: int):
    print(id)
    now = datetime.now()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE queue_history SET time_finished = ? WHERE id = ?""", (now.isoformat(), id)
    )
    conn.commit()

def get_queue_history_as_csv() -> discord.File:
    # build header from column names
    cursor = conn.cursor()
    cursor.execute("""PRAGMA table_info(queue_history)""")
    header = [row[1] for row in cursor.fetchall()]
    header.append("time_in_queue")
    header.append("time_helped")

    #build rows
    data = []
    cursor.execute("SELECT * FROM queue_history")
    for row in cursor.fetchall():
        items: list = [item for item in row]
        # calculate time in queue
        enqueue_time = datetime.fromisoformat(row[4])
        dequeue_time = datetime.fromisoformat(row[5])
        items.append(dequeue_time-enqueue_time)
        #calculate time helped
        finished_time: datetime = datetime.fromisoformat(row[8])
        items.append(finished_time - dequeue_time)
        data.append(items)

    buffer = io.StringIO()        
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(data)

    file = discord.File(io.BytesIO(buffer.getvalue().encode("utf-8")), filename="queue_history.csv")
    return file
    


# Queue auto-open/close scheduled tasks
@tasks.loop(minutes=1)
async def auto_queue_scheduler(bot_client: discord.Client) -> None:
    """Check if queue should be auto-opened or auto-closed every minute."""
    open_hour, open_minute, close_hour, close_minute = get_queue_times()
    denver_tz = ZoneInfo("America/Denver")
    current_time = datetime.now(denver_tz)
    
    # Check if we should open (at the configured open time)
    if current_time.hour == open_hour and current_time.minute == open_minute and not bot_client.queue.is_open:
        bot_client.queue.is_open = True
        print(f"Queue auto-opened at {current_time.strftime('%H:%M')}")
        await update_queue_messages(bot_client)

    
    # Check if we should close (at the configured close time)
    elif current_time.hour == close_hour and current_time.minute == close_minute and bot_client.queue.is_open:
        bot_client.queue.is_open = False
        print(f"Queue auto-closed at {current_time.strftime('%H:%M')}")
        await update_queue_messages(bot_client)
