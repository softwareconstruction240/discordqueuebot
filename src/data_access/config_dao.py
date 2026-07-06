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
            await cursor.execute("SELECT open_hour, open_minute, close_hour, close_minute FROM config WHERE name = %s", (Config.QUEUE_SCHEDULE,))
            row = await cursor.fetchone()
            if row:
                return int(row["open_hour"]), int(row["open_minute"]), int(row["close_hour"]), int(row["close_minute"])
            return 8, 0, 20, 0  # Default to 8:00am-8:00pm


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
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                "UPDATE config SET open_hour = %s, open_minute = %s, close_hour = %s, close_minute = %s WHERE name = %s",
                (open_hour, open_minute, close_hour, close_minute, Config.QUEUE_SCHEDULE)
            )


# Queue auto-open/close scheduled tasks
@tasks.loop(minutes=1)
async def auto_queue_scheduler(bot_client: discord.Client) -> None:
    """Check if queue should be auto-opened or auto-closed every minute on weekdays only."""
    open_hour, open_minute, close_hour, close_minute = await _get_queue_times()
    denver_tz = ZoneInfo("America/Denver")
    current_time = datetime.now(denver_tz) 
    
    # Only run on weekdays (Monday-Friday; 5=Saturday, 6=Sunday)
    if current_time.weekday() >= 5:
        return
    
    message: str | None = None
    # Check if we should open (at the configured open time)
    if current_time.hour == open_hour and current_time.minute == open_minute and not bot_client.queue.is_open:
        bot_client.queue.is_open = True
        message = f"Queue auto-opened at {current_time.strftime('%H:%M')}"

    # Check if we should close (at the configured close time)
    elif current_time.hour == close_hour and current_time.minute == close_minute and bot_client.queue.is_open:
        bot_client.queue.is_open = False
        message = f"Queue auto-closed at {current_time.strftime('%H:%M')}"
    
    # Get TA text channel
    ta_channel = None
    for guild in bot_client.guilds:
        channel_id = await get_id(Channels.TA_TEXT_CHANNEL_NAME, guild.id)
        ta_channel = get(guild.text_channels, id=channel_id)
        if message:
            if ta_channel:
                await ta_channel.send(message, delete_after=30)
            else:
                print(message)
            await update_queue_messages(bot_client, guild)
