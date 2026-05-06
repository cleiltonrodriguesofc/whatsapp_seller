from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# IMPORTANT: for supabase, use the transaction-mode pooler url (port 6543),
# not the session-mode url (port 5432). session mode has a hard cap of 15
# clients shared across all workers/deployments — transaction mode releases
# connections after each transaction and supports many more concurrent clients.
# example: postgresql://user:pass@aws-1-us-west-2.pooler.supabase.com:6543/postgres
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./whatsapp_agent.db")

# supabase transaction-mode pooler requires ssl — inject it if missing
if "postgresql" in DATABASE_URL and "sslmode" not in DATABASE_URL:
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

kwargs = {}
if "sqlite" in DATABASE_URL:
    kwargs["connect_args"] = {"check_same_thread": False}
else:
    # keep total connections (pool_size + max_overflow) well below supabase's
    # session-mode cap. with transaction-mode pooler these are cheap, but we
    # stay conservative to be safe across multiple render workers/restarts.
    kwargs["pool_pre_ping"] = True
    kwargs["pool_recycle"] = 300
    kwargs["pool_size"] = 2       # base pool — 2 persistent connections
    kwargs["max_overflow"] = 3    # burst up to 5 total connections max
    kwargs["pool_timeout"] = 10   # fail fast if no connection available (seconds)

engine = create_engine(DATABASE_URL, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
