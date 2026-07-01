import aiomysql


class DBManager:
    async def __init__(self):
        self.pool: aiomysql.Pool = aiomysql.create_pool(
            user="root",
            password="SQLPassword",
            host="localhost",
            port=3306,
            db="help_queue",
            charset="utf8mb4",

            minsize=1,
            maxsize=5,
            autocommit=True
        )

        await self._initialize_database()
    
    async def _initialize_database(self):
        async with self.pool.acquire() as conn:
            conn: aiomysql.Connection

            async with conn.cursor() as cursor:
                cursor: aiomysql.Cursor
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_stats (
                        user_id INT PRIMARY KEY,
                        user_name STRING,
                        student_name STRING,
                        total_help INTEGER DEFAULT 0,
                        daily_help INTEGER DEFAULT 0
                    )
                    """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_incidents (
                        id INTEGER PRIMARY KEY,
                        reported_by VARCHAR(50),
                        incident_timestamp TEXT,
                        incident TEXT
                    )
                    """
                )

                await cursor.execute(
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
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_history (
                        id INTEGER PRIMARY KEY,
                        student_discord_name TEXT,
                        TA_name TEXT,
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
                await cursor.execute("SELECT COUNT(*) FROM queue_settings")
                if await cursor.fetchone()[0] == 0:
                    await cursor.execute("INSERT INTO queue_settings (id, open_hour, open_minute, close_hour, close_minute) VALUES (1, 8, 0, 20, 0)")
