from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./whatsapp_agent.db")

def migrate():
    engine = create_engine(DATABASE_URL)
    tables = ["campaigns", "status_campaigns", "broadcast_campaigns"]
    columns = [
        ("recurrence_type", "VARCHAR DEFAULT 'weekdays'"),
        ("recurrence_interval", "INTEGER")
    ]

    with engine.connect() as conn:
        for table in tables:
            print(f"Checking table: {table}")
            for col_name, col_type in columns:
                try:
                    # Check if column exists
                    # SQL compatible with PostgreSQL and SQLite
                    if "sqlite" in DATABASE_URL:
                        result = conn.execute(text(f"PRAGMA table_info({table})"))
                        existing_cols = [row[1] for row in result]
                        if col_name not in existing_cols:
                            print(f"Adding {col_name} to {table} (SQLite)")
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                    else:
                        # PostgreSQL
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    conn.commit()
                except Exception as e:
                    print(f"Error adding {col_name} to {table}: {e}")
                    conn.rollback()

if __name__ == "__main__":
    migrate()
    print("Migration complete!")
