import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

# Clean possible spaces or extras in the URL
DATABASE_URL = DATABASE_URL.strip()

print(f"Connecting to: {DATABASE_URL.split('@')[-1]}")

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        print("Successfully connected to the database!")
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("\nTables found in database:")
        if not tables:
            print("- (No tables found)")
        else:
            for table in tables:
                # Count rows for each table
                from sqlalchemy import text
                result = connection.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"- {table}: {count} rows")
            
except Exception as e:
    print(f"\nFailed to connect or query database: {e}")
