import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL not found")
    exit(1)

# fix for postgresql:// vs postgres://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

with engine.connect() as conn:
    print("Checking columns in 'products' table...")
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'products';"))
    columns = [row[0] for row in result]
    print(f"Current columns: {columns}")
    
    if 'click_count' not in columns:
        print("Adding 'click_count' column...")
        conn.execute(text("ALTER TABLE products ADD COLUMN click_count INTEGER DEFAULT 0;"))
        conn.commit()
        print("Column added successfully.")
    else:
        print("Column 'click_count' already exists.")
