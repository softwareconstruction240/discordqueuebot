from discord.ext import tasks
from datetime import time
from zoneinfo import ZoneInfo

from data_access.db_manager import db_manager
import aiomysql
from aiomysql.cursors import DictCursor
from typing import List, Optional



async def increment_help(user_id: int, user_name: str, student_name: Optional[str] = None) -> None:
    """
    Records a help session for a user, incrementing both their total and daily help counts.
    Creates a new user record if one does not exist.

    Args:
        user_id (int): The Discord user ID.
        user_name (str): The user's Discord username.
        student_name (Optional[str]): The student's actual name, if provided.
    """
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor

            await cursor.execute(
                """
                INSERT INTO user_stats (user_id, user_name, student_name, total_help, daily_help)
                VALUES (?, ?, ?, 1, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    user_name = ?,
                    total_help = total_help + 1,
                    daily_help = daily_help + 1
                """,
                (user_id, user_name, student_name or "", user_name),
            )

            if student_name:
                await _update_student_name(user_id, student_name)


async def _update_student_name(user_id: int, student_name: str) -> None:
    """
    Updates the student's name in the database if the new name provided is longer 
    than the currently stored name.

    Args:
        user_id (int): The Discord user ID of the student.
        student_name (str): The new name to evaluate and potentially store.
    """
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor

            await cursor.execute("SELECT student_name FROM user_stats WHERE user_id=?", (user_id,))
            row = await cursor.fetchone()

            existing_name = row["student_name"] if row else ""
            if len(student_name) > len(existing_name or ""):
                await cursor.execute(
                    "UPDATE user_stats SET student_name = ? WHERE user_id = ?",
                    (student_name, user_id),
                )


async def get_student_info() -> tuple[List[str], List[tuple[str, int, int]]]:
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
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: aiomysql.Cursor
            for row in await cursor.execute("SELECT COALESCE(NULLIF(student_name, ''), user_name) AS display_name, total_help, daily_help FROM user_stats"):
                result[1].append((row["display_name"], row["total_help"], row["daily_help"]))

    return result


async def get_times_helped_today(user_id: int) -> int:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("SELECT daily_help FROM user_stats WHERE user_id=?", (user_id,))
            row = await cursor.fetchone()
            return int(row["daily_help"]) if row else 0




#Reset daily help queue counts
@tasks.loop(
    time=time(
        hour=23,
        minute=59,
        tzinfo=ZoneInfo("America/Denver")
    )
)
async def daily_reset() -> None:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                "UPDATE user_stats SET daily_help = 0"
            )

    print("Daily help counts reset.")
