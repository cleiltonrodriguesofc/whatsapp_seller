import sys
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.infrastructure.database.models import Base
from core.infrastructure.database.session import get_db

# Add the project root to sys.path to allow importing the 'core' package
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Test database URL (using SQLite in-memory for speed and isolation)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(engine):
    """Provides a transactional database session for tests."""
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def override_get_db(db_session):
    """Overrides the FastAPI get_db dependency."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass
    return _override_get_db
