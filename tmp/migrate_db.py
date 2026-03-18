from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        print("Starting manual migration...")
        
        # Add instance_id to campaigns
        try:
            conn.execute(text("ALTER TABLE campaigns ADD COLUMN instance_id INTEGER REFERENCES instances(id)"))
            conn.commit()
            print("Added column instance_id to campaigns table.")
        except Exception as e:
            print(f"Error adding instance_id: {e}")
            conn.rollback()

        # Add is_ai_generated to campaigns
        try:
            conn.execute(text("ALTER TABLE campaigns ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Added column is_ai_generated to campaigns table.")
        except Exception as e:
            print(f"Error adding is_ai_generated: {e}")
            conn.rollback()
            
        print("Migration finished.")

if __name__ == "__main__":
    migrate()
