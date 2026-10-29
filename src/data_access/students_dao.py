import aiomysql

from data_access.db_manager import db_manager


async def get_registered_name(discord_id: int) -> str | None:
    """Look up the registered real name for a student by their Discord ID.

    Returns:
        The registered name, or None if the student has not registered.
    """
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                "SELECT registered_name FROM students WHERE discord_id = %s",
                (discord_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_registered_name(discord_id: int, name: str) -> None:
    """Insert or update the registered real name for a student."""
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute(
                """INSERT INTO students (discord_id, registered_name)
                VALUES (%s, %s) as new
                ON DUPLICATE KEY UPDATE registered_name = new.registered_name
                """,
                (discord_id, name)
            )
