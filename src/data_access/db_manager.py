import aiomysql
import warnings
from datetime import datetime
from ui.helpers.constants import Config
from os import getenv

warnings.filterwarnings("ignore", message=r".*exists.*")

class _DBManager:
    """Manages connections to the MySQL Database.  
    Once connect() has been called, use get_conn() to get a connection to the database.  
    ### Fields:   
        pool: Connection pool used to generate connections.  
    ### Methods:   
        connect(): initialize pool and database schema
        get_conn(): Acquire database connection
    """
    def __init__(self):
        self.pool = None

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def connect(self):
        print("Connecting to database at " +getenv("HOST") + ":" + getenv("PORT"))

        self.pool: aiomysql.Pool = await aiomysql.create_pool(
            user=getenv("USER"),
            password=getenv("PASSWORD"),
            host=getenv("HOST"),
            port=int(getenv("PORT")),
            charset="utf8mb4",

            minsize=1,
            maxsize=1,
            autocommit=True
        )            

        async with self.pool.acquire() as conn:
            conn: aiomysql.Connection
            async with conn.cursor() as cursor:
                cursor: aiomysql.Cursor
                await cursor.execute("CREATE DATABASE IF NOT EXISTS help_queue")

        self.pool.close()
        await self.pool.wait_closed()

        self.pool: aiomysql.Pool = await aiomysql.create_pool(
            user=getenv("USER"),
            password=getenv("PASSWORD"),
            host=getenv("HOST"),
            port=int(getenv("PORT")),
            db="help_queue",
            charset="utf8mb4",

            minsize=1,
            maxsize=5,
            autocommit=True
        )
        print("Database connection established successfully")
        await self._initialize_database()
        print("Database initialized successfully")

    def get_conn(self):
        return self.pool.acquire()
    
    async def _initialize_database(self):
        async with self.pool.acquire() as conn:
            conn: aiomysql.Connection

            async with conn.cursor() as cursor:
                cursor: aiomysql.Cursor
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_stats (
                        user_id BIGINT PRIMARY KEY,
                        user_name VARCHAR(100),
                        student_name VARCHAR(100),
                        total_help INT DEFAULT 0,
                        daily_help INT DEFAULT 0
                    )
                    """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_incidents (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        reported_by VARCHAR(100),
                        incident_timestamp DATETIME,
                        incident VARCHAR(500)
                    )
                    """
                )

                await cursor.execute(
                    # make config table a key-value pair where value is text that is parsed by the accessing object according to the expected format of the data for that particular configuration
                    """
                    CREATE TABLE IF NOT EXISTS config (
                        name VARCHAR(100) PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )        
                
                # dequeue_time refers to the time the TA begins helping the student, as the student is no longer waiting in the queue
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        student_discord_name VARCHAR(100) NOT NULL,
                        TA_name VARCHAR(100) NOT NULL,
                        question VARCHAR(300) NOT NULL,
                        enqueue_time DATETIME NOT NULL,
                        dequeue_time DATETIME NOT NULL,
                        is_passoff BOOLEAN NOT NULL,
                        in_person BOOLEAN NOT NULL,
                        time_finished DATETIME
                        )
                    """
                )
                    
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS server_ids (
                        guild_id BIGINT NOT NULL,
                        resource_name VARCHAR(100) NOT NULL,
                        resource_id BIGINT NOT NULL,
                        PRIMARY KEY(guild_id, resource_name)
                    )
                     """
                )

                # Ensure config has a row for default opening/closing
                await cursor.execute("SELECT COUNT(*) FROM config")
                if (await cursor.fetchone())[0] == 0:
                    await cursor.execute("INSERT INTO config (name, value) VALUES (%s, %s)", (Config.QUEUE_SCHEDULE, f"{datetime(2000, 1, 1, hour=8, minute=0).isoformat()},{datetime(2000, 1, 1, hour=20, minute=0).isoformat()}"))

db_manager = _DBManager()
