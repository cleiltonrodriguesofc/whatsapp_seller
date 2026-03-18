from sqlalchemy import create_engine, text, inspect
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def migrate():
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        print("Starting robust migration...")
        
        # Check if campaigns table exists
        if "campaigns" not in inspector.get_table_names():
            print("Table 'campaigns' not found. Skipping.")
            return

        columns = [c['name'] for c in inspector.get_columns('campaigns')]
        
        # Add instance_id if missing
        if "instance_id" not in columns:
            try:
                # Ensure instances table exists first
                if "instances" in inspector.get_table_names():
                    conn.execute(text("ALTER TABLE campaigns ADD COLUMN instance_id INTEGER REFERENCES instances(id)"))
                    conn.commit()
                    print("Added column instance_id to campaigns table.")
                else:
                    print("Table 'instances' missing. Cannot add foreign key.")
            except Exception as e:
                print(f"Error adding instance_id: {e}")
                conn.rollback()
        else:
            print("Column 'instance_id' already exists.")

        # Add is_ai_generated if missing
        if "is_ai_generated" not in columns:
            try:
                conn.execute(text("ALTER TABLE campaigns ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("Added column is_ai_generated to campaigns table.")
            except Exception as e:
                print(f"Error adding is_ai_generated: {e}")
                conn.rollback()
        else:
            print("Column 'is_ai_generated' already exists.")
            
        print("Migration finished.")

if __name__ == "__main__":
    migrate()
