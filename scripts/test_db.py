import sys
import os

# Add the project root directory to Python's path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.common.db_manager import DBManager

print("Connecting to database...")

# Test database connection
db = DBManager()
conn = db.get_connection()
try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"Database connection successful: {result}")
except Exception as e:
    print(f"Database connection error: {e}")
finally:
    db.release_connection(conn)