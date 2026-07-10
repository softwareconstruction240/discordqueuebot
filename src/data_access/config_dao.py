from datetime import datetime
from zoneinfo import ZoneInfo

import aiomysql
from aiomysql import DictCursor
import discord
from discord.utils import get
from discord.ext import tasks

from data_access.db_manager import db_manager
from data_access.server_info_dao import get_id
from ui.helpers.discord_helpers import update_queue_messages
from ui.helpers.constants import Channels, Config


async def _get_queue_times() -> tuple[datetime, datetime]:
    """Get the configured queue open and close times.
    
    Returns:
        Tuple of (open_hour, open_minute, close_hour, close_minute)
    """
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("SELECT value FROM config WHERE name = %s", (Config.QUEUE_SCHEDULE,))
            row = await cursor.fetchone()
            if row:
                value: str = row["value"]
                open_time, close_time = value.split(",")
                open_time = datetime.fromisoformat(open_time) 
                close_time = datetime.fromisoformat(close_time)
                return open_time, close_time 
            return datetime(2000, 1, 1, hour=8, minute=0), datetime(2000, 1, 1, hour=20, minute=0)  # Default to 8:00am-8:00pm


async def set_queue_times(open_hour: int, open_minute: int, close_hour: int, close_minute: int) -> None:
    """Set the queue open and close times.
    
    Args:
        open_hour: Hour to open (0-23)
        open_minute: Minute to open (0-59)
        close_hour: Hour to close (0-23)
        close_minute: Minute to close (0-59)
    """
    if not (0 <= open_hour <= 23 and 0 <= open_minute <= 59 and 0 <= close_hour <= 23 and 0 <= close_minute <= 59):
        raise ValueError("Hours must be 0-23 and minutes must be 0-59")
    open_time = datetime(2000, 1, 1, hour=open_hour, minute=open_minute)
    close_time = datetime(2000, 1, 1, hour=close_hour, minute=close_minute)
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                "UPDATE config SET value = %s WHERE name = %s",
                (f"{open_time.isoformat()},{close_time.isoformat()}", Config.QUEUE_SCHEDULE)
            )

async def set_ta_meeting(day: str, ta_meeting_hour: int, ta_meeting_minute: int):
    if not (0 <= ta_meeting_hour <= 23 and 0 <= ta_meeting_minute <= 59):
        raise ValueError("Hours must be 0-23 and minutes must be 0-59")
    ta_meeting_time = datetime(2000, 1, 1, hour=ta_meeting_hour, minute=ta_meeting_minute)
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("UPDATE config SET value = %s WHERE name = %s", (f"{day},{ta_meeting_time.isoformat()}", Config.TA_MEETING))

async def _get_ta_meeting() -> tuple[str, datetime]:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("SELECT value FROM config WHERE name = %s", (Config.TA_MEETING,))
            row = await cursor.fetchone()
            if row:
                value: str = row["value"]
                day, ta_meeting_time = value.split(",")
                ta_meeting_time = datetime.fromisoformat(ta_meeting_time)
                return day, ta_meeting_time
            
            # if no TA meeting has been configured, set the queue closing time to one hour before opening time, effectively causing no effect on queue hours
            open_time, _ = await _get_queue_times()
            meeting_time = datetime(2000, 1, 1, open_time.hour-1, open_time.minute)
            return "MON", meeting_time

async def set_devotional_hours(day, devotional_hour, devotional_minute):
    if not (0 <= devotional_hour <= 23 and 0 <= devotional_minute <= 59):
        raise ValueError("Hours must be 0-23 and minutes must be 0-59")
    devotional_time = datetime(2000, 1, 1, hour=devotional_hour, minute=devotional_minute)
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("UPDATE config SET value = %s WHERE name = %s", (f"{day},{devotional_time.isoformat()}", Config.DEVOTIONAL))

async def _get_devotional_hours() -> tuple[str, datetime]:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("SELECT value FROM config WHERE name = %s", (Config.DEVOTIONAL,))
            row = await cursor.fetchone()
            if row:
                value: str = row["value"]
                day, devotional_time = value.split(",")
                devotional_time = datetime.fromisoformat(devotional_time)
                return day, devotional_time
            
            # if no devotional has been configured, set to tuesday at 11am
            return "TUE", datetime(2000, 1, 1, hour=11, minute=0)

async def set_saturday_hours(open_hour: int, open_minute: int, close_hour: int, close_minute: int) -> None:
    open_at: datetime = datetime(2000, 1, 1, hour=open_hour, minute = open_minute)
    close_at: datetime = datetime(2000, 1, 1, hour=close_hour, minute=close_minute)

    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute(
                """
                INSERT INTO config (name, value)
                VALUES (%s, %s) AS new
                ON DUPLICATE KEY UPDATE value = new.value
                """,
                (Config.SATURDAY_HOURS, f"{open_at.isoformat()},{close_at.isoformat()}")
            )


async def remove_saturday_hours() -> None:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("DELETE FROM config WHERE name = %s", (Config.SATURDAY_HOURS,))


async def _get_saturday_hours() -> tuple[datetime, datetime] | None:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("SELECT value FROM config WHERE name = %s", (Config.SATURDAY_HOURS,))
            row = await cursor.fetchone()
            if row:
                value: str = row["value"]
                open, close = value.split(",")
                open = datetime.fromisoformat(open)
                close = datetime.fromisoformat(close)
                return open, close
            
            return None


async def get_config_data():
    """
    Fetch all config table rows and return a readable string.
    """
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("SELECT name, value FROM config ORDER BY name")
            rows = await cursor.fetchall()

    # Build readable output
    lines = []
    for name, raw_value in rows:
        raw_value: str
        parts = raw_value.split(",")

        formatted_parts = []
        for part in parts:
            formatted_parts.append(_try_format_datetime(part))

        formatted_value = ", ".join(formatted_parts)
        lines.append(f"{name} = {formatted_value}")

    return "\n".join(lines)

def _try_format_datetime(value: str):
    """
    Try to parse a datetime string and return HH:MM.
    If parsing fails, return the original string.
    """

    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%H:%M")
    except ValueError:
        return value  # Not a datetime


def _should_open(current_time: datetime, open_time: datetime, meeting_time: datetime, meeting_day: str, devo_time: datetime, devo_day: str) -> bool:
    begin_queue_hours: bool = current_time.hour == open_time.hour and current_time.minute == open_time.minute
    finish_ta_meeting: bool = current_time.hour == meeting_time.hour+1 and current_time.minute == meeting_time.minute and current_time.weekday() == day_to_int(meeting_day)
    finish_devo: bool = current_time.hour == devo_time.hour+1 and current_time.minute == devo_time.minute and current_time.weekday() == day_to_int(devo_day)
    return begin_queue_hours or finish_ta_meeting or finish_devo

def _should_close(current_time: datetime, close_time: datetime, meeting_time: datetime, meeting_day: str, devo_time: datetime, devo_day: str) -> bool:
    finish_queue_hours: bool = current_time.hour == close_time.hour and current_time.minute == close_time.minute
    begin_ta_meeting: bool = current_time.hour == meeting_time.hour and current_time.minute == meeting_time.minute and current_time.weekday() == day_to_int(meeting_day)
    begin_devo: bool = current_time.hour == devo_time.hour and current_time.minute == devo_time .minute and current_time.weekday() == day_to_int(devo_day)
    return finish_queue_hours or begin_ta_meeting or begin_devo

def day_to_int(day: str) -> int:
    days = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
    return days.index(day)

# Queue auto-open/close scheduled tasks
@tasks.loop(minutes=0.9)
async def auto_queue_scheduler(bot_client: discord.Client) -> None:
    """Check if queue should be auto-opened or auto-closed every minute on weekdays only."""
    open_time, close_time = await _get_queue_times()
    meeting_day, meeting_time = await _get_ta_meeting()
    devo_day, devo_time = await _get_devotional_hours()
    denver_tz = ZoneInfo("America/Denver")
    current_time = datetime.now(denver_tz) 
    
    # Only run on weekdays (Monday-Friday; 5=Saturday, 6=Sunday)
    if current_time.weekday() == 6:
        return
    elif current_time.weekday() == 5:
        try:
            open_time, close_time = await _get_saturday_hours()
        except TypeError:
            return
    
    message: str | None = None
    # Check if we should open (at the configured open time)
    if _should_open(current_time, open_time, meeting_time, meeting_day, devo_time, devo_day) and not bot_client.queue.is_open:
        bot_client.queue.is_open = True
        message = f"Queue auto-opened at {current_time.strftime('%H:%M')}"

    # Check if we should close (at the configured close time)
    elif _should_close(current_time, close_time, meeting_time, meeting_day, devo_time, devo_day) and bot_client.queue.is_open:
        bot_client.queue.is_open = False
        message = f"Queue auto-closed at {current_time.strftime('%H:%M')}"
    
    # Get TA text channel
    ta_channel = None
    if message:
        for guild in bot_client.guilds:
            channel_id = await get_id(Channels.TA_TEXT_CHANNEL_NAME, guild.id)
            ta_channel = get(guild.text_channels, id=channel_id)
            if ta_channel:
                await ta_channel.send(message, delete_after=30)
            else:
                print(message)
            await update_queue_messages(bot_client, guild)
