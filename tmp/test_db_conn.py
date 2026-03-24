import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
load_dotenv(".env")

# Ensure core module can be imported
sys.path.insert(0, os.path.abspath("."))

from core.infrastructure.database.session import engine

def test_connection():
    print("Testing Database Connection...")
    print(f"DATABASE_URL is set: {'DATABASE_URL' in os.environ}")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"SUCCESS: Connection established! DB Query 'SELECT 1' returned: {result.fetchone()[0]}")
    except Exception as e:
        print(f"FAILURE: Could not connect to the database. Error: {e}")

if __name__ == "__main__":
    test_connection()
