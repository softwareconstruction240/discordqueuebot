import aiomysql
from aiomysql.cursors import DictCursor
from data_access.db_manager import db_manager
from datetime import datetime, timedelta, UTC
from typing import Optional


async def record_bot_issue(username: str, issue: str) -> None:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            timestamp = datetime.now(UTC)
            await cursor.execute(
                "INSERT INTO bot_incidents (incident_timestamp, reported_by, incident) VALUES (%s, %s, %s)",
                (timestamp, username, issue)
            )


async def get_last_incident_info() -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Get information for most recent bot issue. 
    Returns:
        A tuple of 3 elements containing the user who reported the issue, the number of days since the issue, and the issue description, in that order."""
    
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor(DictCursor) as cursor:
            cursor: DictCursor

            await cursor.execute("SELECT reported_by, incident_timestamp, incident FROM bot_incidents ORDER BY incident_timestamp DESC LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                return None, None, None

            try:
                last_incident_time = row["incident_timestamp"].replace(tzinfo=UTC)
            except ValueError:
                return row["reported_by"] or None, None, row["incident"] or None

            delta: timedelta = datetime.now(UTC) - last_incident_time
            return row["reported_by"] or None, delta.days, row["incident"] or None

