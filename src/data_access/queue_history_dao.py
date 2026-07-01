import aiomysql
from aiomysql.cursors import DictCursor
import csv
from datetime import datetime, UTC
import discord
import io
from data_access.db_manager import db_manager
from records import QueueEntry
from zoneinfo import ZoneInfo


async def add_queue_history_item(queue_entry: QueueEntry, student_username, ta: str) -> int:
    """Adds information about the student's help queue entry to the database and returns its associated key to be used for later indexing.
    
    Returns: 
        int => id of queue history item
    """
    dequeue_time = datetime.now(UTC)
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                """INSERT INTO queue_history (
                    student_discord_name,
                    ta_name,
                    question,
                    enqueue_time,
                    dequeue_time,
                    is_passoff,
                    in_person
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (student_username, 
                    ta, 
                    queue_entry.details, 
                    queue_entry.timestamp, 
                    dequeue_time, 
                    queue_entry.is_passoff, 
                    queue_entry.in_person
                    )
            )
            generated_id = cursor.lastrowid

            return generated_id

async def _get_dequeue_time(id: int) -> datetime:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor

            await cursor.execute(
                """
                SELECT dequeue_time FROM queue_history WHERE id = %s
                """, (id,)
            )
            row = await cursor.fetchone()
            dequeue_time: datetime = row["dequeue_time"]
            return dequeue_time.astimezone(ZoneInfo("America/Denver"))
    

async def set_time_finished(id: int):
    now = datetime.now(UTC)
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                """
                UPDATE queue_history SET time_finished = %s WHERE id = %s
                """, (now, id)
            )

async def get_queue_history_as_csv() -> discord.File:
    # build header from column names
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'queue_history'
                ORDER BY ORDINAL_POSITION;
                """
            )
            header = [row["COLUMN_NAME"] for row in await cursor.fetchall()]
            header.append("time_in_queue")
            header.append("time_helped")

            #build rows
            data = []
            await cursor.execute("SELECT * FROM queue_history")
            for row in await cursor.fetchall():
                items:list = []
                items.append(row["id"])
                items.append(row["student_discord_name"])
                items.append(row["TA_name"])
                items.append(row["question"])

                items.append(_to_denver_time(row["enqueue_time"]))
                items.append(_to_denver_time(row["dequeue_time"]))

                items.append(row["is_passoff"])
                items.append(row["in_person"])
                items.append(_to_denver_time(row["time_finished"]))
                
                # calculate time in queue
                enqueue_time = row["enqueue_time"]
                dequeue_time = row["dequeue_time"]
                items.append(dequeue_time-enqueue_time)
                #calculate time helped
                try: 
                    time_finished: datetime = row["time_finished"]
                    items.append(time_finished - dequeue_time)
                except TypeError:
                    items.append("None")
                data.append(items)

    buffer = io.StringIO()        
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(data)

    file = discord.File(io.BytesIO(buffer.getvalue().encode("utf-8")), filename="queue_history.csv")
    return file


async def get_queue_history() -> list:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("SELECT * FROM queue_history")
            return [row for row in await cursor.fetchall()]
    

def _to_denver_time(time: datetime) -> datetime | None:
    if time is None:
        return None
    return time.astimezone(ZoneInfo("America/Denver"))

