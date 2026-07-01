import aiomysql

class _DBManager:
    """Manages connections to the MySQL Database.  
    Once connect() has been called, use pool.acquire to get a connection to the database.  
    ### Fields:   
        pool: Connection pool used to generate connections.  
    ### Methods:   
        connect(): initialize pool and database schema
    """
    def __init__(self):
        pass

    async def connect(self):
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
                        reported_by VARCHAR(50),
                        incident_timestamp DATETIME,
                        incident VARCHAR(500)
                    )
                    """
                )

                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_settings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        open_hour INT DEFAULT 8,
                        open_minute INT DEFAULT 0,
                        close_hour INT DEFAULT 20,
                        close_minute INT DEFAULT 0
                    )
                    """
                )        
                
                # dequeue_time refers to the time the TA begins helping the student, as the student is no longer waiting in the queue
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        student_discord_name VARCHAR(100),
                        TA_name VARCHAR(100),
                        question VARCHAR(300),
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
                        guild_id INT NOT NULL,
                        resource_name VARCHAR(100) NOT NULL,
                        resource_id BIGINT NOT NULL,
                        PRIMARY KEY(guild_id, resource_name)
                    )
                     """
                )

                # Ensure queue_settings has a default row
                await cursor.execute("SELECT COUNT(*) FROM queue_settings")
                if await cursor.fetchone()[0] == 0:
                    await cursor.execute("INSERT INTO queue_settings (id, open_hour, open_minute, close_hour, close_minute) VALUES (1, 8, 0, 20, 0)")

db_manager = _DBManager()
