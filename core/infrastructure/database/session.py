from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./whatsapp_agent.db")

kwargs = {}
if "sqlite" in DATABASE_URL:
    kwargs["connect_args"] = {"check_same_thread": False}
else:
    kwargs["pool_pre_ping"] = True
    kwargs["pool_recycle"] = 300
    kwargs["pool_size"] = 20
    kwargs["max_overflow"] = 10

engine = create_engine(DATABASE_URL, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
