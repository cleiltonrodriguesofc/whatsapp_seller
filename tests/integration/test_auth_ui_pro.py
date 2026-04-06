import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login_user(client, db_session, email="pro_test@test.com"):
    auth = AuthService()
    user = UserModel(email=email, hashed_password=auth.hash_password("genpass123"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": email, "password": "genpass123"})
    return user


def test_login_page_identity(client):
    """Verify that the login page renders the WhatSeller Pro identity and banner."""
    response = client.get("/login")
    assert response.status_code == 200
    # Identity (check for parts since they are split by tags)
    assert "What" in response.text
    assert "Seller" in response.text
    assert "Pro" in response.text
    assert "gradient-text" in response.text
    # Layout classes
    assert "auth-split-container" in response.text
    assert "auth-banner" in response.text
    assert "auth-form-side" in response.text
    # Form fields
    assert 'name="username"' in response.text
    assert 'name="password"' in response.text


def test_register_page_identity(client):
    """Verify that the register page renders the identity and registration fields."""
    response = client.get("/register")
    assert response.status_code == 200
    assert "What" in response.text
    assert "Seller" in response.text
    assert "Pro" in response.text
    assert "Começar Agora" in response.text
    # Registration specific fields
    assert 'name="business_name"' in response.text
    assert 'name="email"' in response.text
    assert 'name="password"' in response.text
    assert 'name="terms_accepted"' in response.text


def test_sidebar_hides_beta_features(client, db_session):
    """Verify that 'Faturamento' and 'Indicação' are NOT visible in the sidebar."""
    login_user(client, db_session)
    response = client.get("/")
    assert response.status_code == 200

    # These should be commented out or removed from DOM
    assert "Faturamento" not in response.text
    assert "Indicação" not in response.text
    # Verify core features ARE present
    assert "Painel" in response.text
    assert "Status Auto" in response.text
    assert "Broadcast" in response.text


def test_auth_pages_suppress_base_mobile_header(client):
    """Verify that the duplicate mobile header from base.html is suppressed."""
    response = client.get("/login")
    assert response.status_code == 200
    # The style should contain the suppression
    assert ".mobile-header { display: none !important; }" in response.text
    # Our specific auth mobile header should be present
    assert "auth-mobile-header" in response.text


def test_login_submission_works_with_new_ui(client, db_session):
    """Verify that the login form remains functional after the UI redesign."""
    from core.presentation.web.app import limiter
    from limits.storage import MemoryStorage
    limiter._storage = MemoryStorage()
    limiter.enabled = False

    import uuid
    email = f"functional_{uuid.uuid4().hex[:6]}@test.com"
    password = "pass"
    auth = AuthService()
    user = UserModel(email=email, hashed_password=auth.hash_password(password))
    db_session.add(user)
    db_session.commit()

    response = client.post("/login", data={"username": email, "password": password}, follow_redirects=True)
    assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
    # Should land on dashboard
    assert "Dashboard" in response.text or "Painel" in response.text
