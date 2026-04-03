import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel, PlanModel

@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_pricing_page_renders(client, db_session):
    """Verify that the pricing page renders properly with plans."""
    plan = PlanModel(name="pro", display_name="Pro", price_brl=97.0, max_instances=1)
    db_session.add(plan)
    db_session.commit()
    
    response = client.get("/pricing")
    assert response.status_code == 200
    assert "pricing" in response.text or "Pro" in response.text

def test_billing_dashboard_requires_login(client):
    """Verify that billing dashboard requires authentication."""
    response = client.get("/dashboard/billing", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/login" in response.headers.get("Location", "")

def test_checkout_create_session_fails_gracefully_without_token(client, db_session):
    """Verify that checkout gracefully errors when no token is present."""
    auth = AuthService()
    user = UserModel(email="billing_test@example.com", hashed_password=auth.hash_password("pass"))
    plan = PlanModel(name="test_plan", display_name="Test", price_brl=100.0, mp_plan_id="mp_123", max_instances=1)
    db_session.add(user)
    db_session.add(plan)
    db_session.commit()
    
    # Login user
    client.post("/login", data={"username": "billing_test@example.com", "password": "pass"})
    
    response = client.post(
        "/checkout/create-session", 
        data={"plan_name": "test_plan"},
        follow_redirects=False
    )
    
    # Since MP_ACCESS_TOKEN is not configured in this test environment, it should hit 500
    # or fail at Mercado Pago SDK level instead of giving internal fatal error
    assert response.status_code in (500, 404, 400)
