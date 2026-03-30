import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.infrastructure.database.models import Base

def debug_auth():
    # Setup test DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Override dependency
    def override():
        yield db
    app.dependency_overrides[get_db] = override

    with TestClient(app) as client:
        # 1. Create user
        email = "debug@test.com"
        pwd = "password123"
        auth = AuthService()
        user = UserModel(email=email, hashed_password=auth.hash_password(pwd))
        db.add(user)
        db.commit()

        # 2. Login
        print(f"\n--- Logging in {email} ---")
        response = client.post("/login", data={"username": email, "password": pwd}, follow_redirects=False)
        print(f"Login Status: {response.status_code}")
        print(f"Login Cookies: {client.cookies.get_dict()}")
        
        # 3. Check access
        print("\n--- Accessing /status_campaigns ---")
        response = client.get("/status_campaigns", follow_redirects=False)
        print(f"Access Status: {response.status_code}")
        if response.status_code in (302, 303):
            print(f"Redirect to: {response.headers.get('Location')}")
        
    app.dependency_overrides.clear()

if __name__ == "__main__":
    debug_auth()
