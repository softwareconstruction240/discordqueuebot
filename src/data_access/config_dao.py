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


async def _get_queue_times() -> tuple[int, int, int, int]:
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

async def set_ta_meeting(ta_meeting_hour: int, ta_meeting_minute: int):
    if not (0 <= ta_meeting_hour <= 23 and 0 <= ta_meeting_minute <= 59):
        raise ValueError("Hours must be 0-23 and minutes must be 0-59")
    ta_meeting_time = datetime(2000, 1, 1, hour=ta_meeting_hour, minute=ta_meeting_minute)
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            cursor.execute("UPDATE config SET value = %s WHERE name = %s", (ta_meeting_time.isoformat(), Config.TA_MEETING))

async def _get_ta_meeting() -> datetime:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor
            await cursor.execute("SELECT value FROM config WHERE name = %s", (Config.TA_MEETING,))
            row = await cursor.fetchone()
            if row:
                value: str = row[0]
                ta_meeting_time = datetime.fromisoformat(value)
                return ta_meeting_time
            
            # if no TA meeting has been configured, set the queue closing time to one hour before opening time so that when it opens after the meeting it will not conflict.
            open_time, _ = await _get_queue_times()
            return open_time

async def set_devotional_hours():
    pass 

async def _get_devotional_hours():
    pass

def _should_open(current_time: datetime, open_time: datetime, meeting_time: datetime):
    begin_queue_hours: bool = current_time.hour == open_time.hour and current_time.minute == open_time.minute
    finish_ta_meeting: bool = current_time.hour == meeting_time.hour+1 and current_time.minute == meeting_time.minute
    return begin_queue_hours or finish_ta_meeting

def _should_close(current_time: datetime, close_time: datetime, meeting_time: datetime):
    finish_queue_hours: bool = current_time.hour == close_time.hour and current_time.minute == close_time.minute
    begin_ta_meeting: bool = current_time.hour == meeting_time.hour and current_time.minute == meeting_time.minute
    return finish_queue_hours or begin_ta_meeting



# Queue auto-open/close scheduled tasks
@tasks.loop(minutes=1)
async def auto_queue_scheduler(bot_client: discord.Client) -> None:
    """Check if queue should be auto-opened or auto-closed every minute on weekdays only."""
    open_time, close_time = await _get_queue_times()
    meeting_time = await _get_ta_meeting()
    denver_tz = ZoneInfo("America/Denver")
    current_time = datetime.now(denver_tz) 
    
    # Only run on weekdays (Monday-Friday; 5=Saturday, 6=Sunday)
    if current_time.weekday() >= 5:
        return
    
    message: str | None = None
    # Check if we should open (at the configured open time)
    if _should_open(current_time, open_time, meeting_time) and not bot_client.queue.is_open:
        bot_client.queue.is_open = True
        message = f"Queue auto-opened at {current_time.strftime('%H:%M')}"

    # Check if we should close (at the configured close time)
    elif _should_close(current_time, close_time, meeting_time) and bot_client.queue.is_open:
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
