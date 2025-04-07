import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv

class DBManager:
    """PostgreSQL Database connection manager"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            load_dotenv()
            
            # Get database connection details from environment variables
            cls._instance.db_host = os.getenv("DB_HOST", "localhost")
            cls._instance.db_port = os.getenv("DB_PORT", "5432")
            cls._instance.db_name = os.getenv("DB_NAME", "retardibot")
            cls._instance.db_user = os.getenv("DB_USER", "retardibot_user")
            cls._instance.db_password = os.getenv("DB_PASSWORD", "")
            
            # Create connection pool
            cls._instance.pool = pool.SimpleConnectionPool(
                1,  # Min connections
                10,  # Max connections
                host=cls._instance.db_host,
                port=cls._instance.db_port,
                database=cls._instance.db_name,
                user=cls._instance.db_user,
                password=cls._instance.db_password
            )
            
            # Initialize tables
            cls._instance._initialize_tables()
            
        return cls._instance
    
    def get_connection(self):
        """Get a connection from the pool"""
        return self.pool.getconn()
    
    def release_connection(self, conn):
        """Return a connection to the pool"""
        self.pool.putconn(conn)
    
    def _initialize_tables(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Create schema with all tables
                
                # 1. Moderation tables
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS mod_actions (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    moderator_id BIGINT NOT NULL,
                    action_type TEXT NOT NULL,
                    reason TEXT,
                    duration INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # 2. Confessions tables
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS confessions (
                    id SERIAL PRIMARY KEY,
                    message_id BIGINT,
                    user_id BIGINT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN DEFAULT FALSE
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS confession_bans (
                    user_id BIGINT PRIMARY KEY,
                    banned_by BIGINT NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # 3. Logging tables
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_logs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    content TEXT,
                    attachments JSONB,
                    embeds JSONB,
                    action_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_logs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    action_type TEXT NOT NULL,
                    details JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_logs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_id BIGINT,
                    details JSONB,
                    user_id BIGINT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Add indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_mod_actions_user_id ON mod_actions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_mod_actions_guild_id ON mod_actions(guild_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_confessions_user_id ON confessions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_logs_guild_id ON message_logs(guild_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_logs_user_id ON user_logs(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_server_logs_guild_id ON server_logs(guild_id)')
                
                conn.commit()
                
        except Exception as e:
            conn.rollback()
            print(f"Error initializing database tables: {e}")
        finally:
            self.release_connection(conn)