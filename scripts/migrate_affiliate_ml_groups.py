"""
migration: run with dotenv loaded.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./database.db")
print(f"Using DB: {DATABASE_URL[:60]}...")

engine = create_engine(DATABASE_URL)

MIGRATIONS = [
    "ALTER TABLE affiliate_configs ADD COLUMN ml_profile_slug VARCHAR",
    "ALTER TABLE affiliate_configs ADD COLUMN ml_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE affiliate_configs ADD COLUMN ml_categories VARCHAR DEFAULT 'notebook,celular'",
    "ALTER TABLE affiliate_configs ADD COLUMN group_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE affiliate_configs ADD COLUMN group_jids TEXT",
    "ALTER TABLE affiliate_configs ADD COLUMN group_dispatch_hours VARCHAR DEFAULT '9,12,15,18,21'",
    "ALTER TABLE affiliate_logs ADD COLUMN source VARCHAR DEFAULT 'magalu'",
]


def run():
    with engine.connect() as conn:
        for i, sql in enumerate(MIGRATIONS):
            col_name = sql.split("ADD COLUMN")[1].strip().split()[0]
            sp = f"sp_{i}"
            try:
                conn.execute(text(f"SAVEPOINT {sp}"))
                conn.execute(text(sql))
                conn.execute(text(f"RELEASE SAVEPOINT {sp}"))
                conn.commit()
                print(f"[ok] added column: {col_name}")
            except Exception as e:
                conn.execute(text(f"ROLLBACK TO SAVEPOINT {sp}"))
                err = str(e).lower()
                if "duplicate column" in err or "already exists" in err:
                    print(f"[skip] already exists: {col_name}")
                else:
                    print(f"[error] {col_name}: {e}")


if __name__ == "__main__":
    run()
    print("\nmigration complete.")
