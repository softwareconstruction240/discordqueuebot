from data_access.db_manager import db_manager
import aiomysql

async def set_id(name: str, guild_id: int, id: int) -> None:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("""INSERT INTO server_ids (guild_id, resource_name, resource_id)
                        VALUES (%s, %s, %s) AS new
                        ON DUPLICATE KEY UPDATE 
                            resource_id = new.resource_id""",
                        (guild_id, name, id))

async def get_id(name: str, guild_id: int) -> int:
    async with db_manager.get_conn() as conn:
        conn: aiomysql.Connection
        async with conn.cursor() as cursor:
            cursor: aiomysql.Cursor
            await cursor.execute("SELECT resource_id FROM server_ids WHERE (guild_id, resource_name) = (%s, %s)", (guild_id, name))
            row = await cursor.fetchone()

            return row[0] if row else -1

