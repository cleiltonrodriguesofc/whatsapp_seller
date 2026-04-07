import pytest
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.infrastructure.database.models import Base, UserModel
from core.application.services.auth_service import AuthService
from core.infrastructure.utils.timezone import now_sp


# Setup in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_user_model_recovery_fields(db_session):
    # Setup test user
    user = UserModel(
        email="test@example.com",
        hashed_password="old_password",
        reset_token="some_token_123",
        reset_token_expiry=now_sp() + timedelta(hours=1),
    )
    db_session.add(user)
    db_session.commit()

    # Retrieve user and verify fields
    db_user = (
        db_session.query(UserModel)
        .filter(UserModel.email == "test@example.com")
        .first()
    )
    assert db_user.reset_token == "some_token_123"
    assert db_user.reset_token_expiry is not None


def test_full_recovery_db_flow(db_session):
    # Step 1: User requests recovery
    user = UserModel(email="user@test.com", hashed_password="old_hash")
    db_session.add(user)
    db_session.commit()

    token = AuthService.generate_reset_token()
    expiry = now_sp() + timedelta(hours=1)

    user.reset_token = token
    user.reset_token_expiry = expiry
    db_session.commit()

    # Verify token is saved
    db_user = (
        db_session.query(UserModel).filter(UserModel.email == "user@test.com").first()
    )
    assert db_user.reset_token == token
    assert db_user.reset_token_expiry == expiry

    # Step 2: User resets password
    new_pass = "very_secret_new_pass"
    new_hash = AuthService.hash_password(new_pass)

    db_user.hashed_password = new_hash
    db_user.reset_token = None
    db_user.reset_token_expiry = None
    db_session.commit()

    # Step 3: Final verification
    db_user_final = (
        db_session.query(UserModel).filter(UserModel.email == "user@test.com").first()
    )
    assert db_user_final.reset_token is None
    assert db_user_final.reset_token_expiry is None
    assert AuthService.verify_password(new_pass, db_user_final.hashed_password) is True
    assert db_user_final.hashed_password != "old_hash"
