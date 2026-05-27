"""
migration: add ml affiliate and group broadcast columns to affiliate_configs
and source column to affiliate_logs.
run once manually: python scripts/migrate_affiliate_ml_groups.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./database.db")

engine = create_engine(DATABASE_URL)

MIGRATIONS = [
    # mercado livre affiliate
    "ALTER TABLE affiliate_configs ADD COLUMN ml_profile_slug VARCHAR",
    "ALTER TABLE affiliate_configs ADD COLUMN ml_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE affiliate_configs ADD COLUMN ml_categories VARCHAR DEFAULT 'notebook,celular'",

    # group broadcast
    "ALTER TABLE affiliate_configs ADD COLUMN group_enabled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE affiliate_configs ADD COLUMN group_jids TEXT",
    "ALTER TABLE affiliate_configs ADD COLUMN group_dispatch_hours VARCHAR DEFAULT '9,12,15,18,21'",

    # affiliate log source tracking
    "ALTER TABLE affiliate_logs ADD COLUMN source VARCHAR DEFAULT 'magalu'",
]


def run():
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            col_name = sql.split("ADD COLUMN")[1].strip().split()[0]
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"[ok] added column: {col_name}")
            except Exception as e:
                err = str(e).lower()
                if "duplicate column" in err or "already exists" in err:
                    print(f"[skip] column already exists: {col_name}")
                else:
                    print(f"[error] {col_name}: {e}")


if __name__ == "__main__":
    run()
    print("\nmigration complete.")
