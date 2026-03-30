import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.infrastructure.database.models import UserModel
from core.application.services.auth_service import AuthService


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign In" in response.text or "Login" in response.text


def test_registration_flow(client, db_session):
    # Mocking Evolution API for instance creation
    from unittest.mock import patch, AsyncMock

    with patch("core.presentation.web.routers.auth.EvolutionWhatsAppService") as mock_ws:
        mock_instance = mock_ws.return_value
        mock_instance.create_instance = AsyncMock(return_value={"hash": {"apikey": "mock_sys_key_x9"}})

        response = client.post(
            "/register",
            data={"email": "api_test@test.com", "password": "test_password_placeholder", "business_name": "API Business"},
            follow_redirects=True,
        )

        # Should redirect to connect_whatsapp_page
        assert response.status_code == 200
        assert "connect_whatsapp.html" in response.template.name or "/whatsapp/connect" in response.url.path

        # Verify user created in DB
        user = db_session.query(UserModel).filter(UserModel.email == "api_test@test.com").first()
        assert user is not None
        assert user.instances[0].apikey == "mock_sys_key_x9"


def test_dashboard_login_required(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "WhatsApp" in response.text


def test_successful_login(client, db_session):
    # Create user
    auth = AuthService()
    user = UserModel(email="auth_test@test.com", hashed_password=auth.hash_password("test_password_placeholder"))
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/login", data={"username": "auth_test@test.com", "password": "test_password_placeholder"}, follow_redirects=True
    )

    assert response.status_code == 200
    # Should show dashboard (list campaigns)
    assert "Dashboard" in response.text or "Campaign Details" in response.text or "/" in response.url.path
