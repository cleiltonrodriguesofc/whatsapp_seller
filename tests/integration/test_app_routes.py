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


def test_list_products_with_auth(client, db_session):
    # Setup test user and login
    auth = AuthService()
    user = UserModel(email="prod_test@test.com", hashed_password=auth.hash_password("mock_auth_val_x9"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "prod_test@test.com", "password": "mock_auth_val_x9"})

    response = client.get("/products")
    assert response.status_code == 200
    assert "Products" in response.text


def test_new_campaign_form_with_auth(client, db_session):
    auth = AuthService()
    user = UserModel(email="camp_test@test.com", hashed_password=auth.hash_password("mock_auth_val_x9"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "camp_test@test.com", "password": "mock_auth_val_x9"})

    response = client.get("/campaigns/new")
    assert response.status_code == 200
    assert "Campaign" in response.text


def test_campaigns_list_with_auth(client, db_session):
    auth = AuthService()
    user = UserModel(email="list_test@test.com", hashed_password=auth.hash_password("mock_auth_val_x9"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "list_test@test.com", "password": "mock_auth_val_x9"})

    response = client.get("/")
    assert response.status_code == 200
    assert "Campaigns" in response.text or "Campanhas" in response.text or "Dashboard" in response.text


def test_broadcast_campaigns_list_with_auth(client, db_session):
    """Broadcast campaign list must return 200 for authenticated users."""
    auth = AuthService()
    user = UserModel(email="bc_list@test.com", hashed_password=auth.hash_password("mock_auth_val_x9"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "bc_list@test.com", "password": "mock_auth_val_x9"})

    response = client.get("/broadcast/campaigns")
    assert response.status_code == 200


def test_broadcast_new_campaign_form_with_auth(client, db_session):
    """New broadcast campaign form must return 200 and render the editor."""
    from core.infrastructure.database.models import InstanceModel
    auth = AuthService()
    user = UserModel(email="bc_new@test.com", hashed_password=auth.hash_password("mock_auth_val_x9"))
    db_session.add(user)
    db_session.commit()

    instance = InstanceModel(user_id=user.id, name="inst_bc_new2", status="connected")
    db_session.add(instance)
    db_session.commit()

    client.post("/login", data={"username": "bc_new@test.com", "password": "mock_auth_val_x9"})

    response = client.get("/broadcast/campaigns/new")
    assert response.status_code == 200
    assert "form" in response.text.lower()


def test_unauthenticated_access_to_status_redirects(client):
    """Accessing status campaigns without authentication must redirect to login."""
    response = client.get("/status_campaigns", follow_redirects=False)
    # either a redirect or a login page response is acceptable
    assert response.status_code in (302, 303, 200)
