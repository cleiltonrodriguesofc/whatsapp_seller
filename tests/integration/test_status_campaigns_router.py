import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel, InstanceModel

@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_status_campaigns_list_auth(client, db_session):
    """Test accessing the status campaigns list with authentication."""
    auth = AuthService()
    user = UserModel(email="status_list@test.com", hashed_password=auth.hash_password("pw123"))
    db_session.add(user)
    db_session.commit()
    
    # Login
    client.post("/login", data={"username": "status_list@test.com", "password": "pw123"})
    
    response = client.get("/status_campaigns")
    assert response.status_code == 200
    assert "Status Automático" in response.text

def test_new_status_campaign_form_auth(client, db_session):
    """Test accessing the new status campaign form with authentication."""
    auth = AuthService()
    user = UserModel(email="status_form@test.com", hashed_password=auth.hash_password("pw123"))
    db_session.add(user)
    db_session.commit()
    
    client.post("/login", data={"username": "status_form@test.com", "password": "pw123"})
    
    response = client.get("/status_campaigns/new")
    assert response.status_code == 200
    assert "Novo Status Automático" in response.text

def test_create_status_campaign_auth(client, db_session):
    """Test creating a new status campaign via POST."""
    auth = AuthService()
    user = UserModel(email="status_create@test.com", hashed_password=auth.hash_password("pw123"))
    db_session.add(user)
    db_session.commit()
    
    instance = InstanceModel(user_id=user.id, name="inst_status", status="connected")
    db_session.add(instance)
    db_session.commit()
    
    client.post("/login", data={"username": "status_create@test.com", "password": "pw123"})
    
    # Mocking form data
    form_data = {
        "title": "New Web Status",
        "caption": "Check this web status",
        "background_color": "#128C7E",
        "instance_id": instance.id,
        "target_groups": "[\"123@s.whatsapp.net\"]",
        "is_recurring": "false",
        "save_mode": "schedule"
    }
    
    response = client.post("/status_campaigns/new", data=form_data, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/status_campaigns"
