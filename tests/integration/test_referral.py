import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel, ReferralCodeModel, ReferralConversionModel


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_referral_dashboard_renders(client, db_session):
    """Verify that the referral dashboard renders with correct referral data."""
    auth = AuthService()
    user = UserModel(email="referral_test@example.com", hashed_password=auth.hash_password("pass"))
    db_session.add(user)
    db_session.commit()

    ref_code = ReferralCodeModel(user_id=user.id, code="REF123")
    db_session.add(ref_code)

    conversion = ReferralConversionModel(referrer_id=user.id, referred_id=2, status="rewarded", reward_brl=29.10)
    db_session.add(conversion)
    db_session.commit()

    client.post("/login", data={"username": "referral_test@example.com", "password": "pass"})
    response = client.get("/referral")

    assert response.status_code == 200
    assert "REF123" in response.text
    # Total earned should be displayed somewhere in HTML since the context passes it
    assert "29" in response.text
    assert "Programa de Indicação" in response.text


def test_request_withdrawal_insufficient_funds(client, db_session):
    """Verify withdrawal block when funds are under 100 BRL."""
    auth = AuthService()
    user = UserModel(
        email="poor_referral@example.com",
        hashed_password=auth.hash_password("pass"),
        referral_balance=50.0)
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "poor_referral@example.com", "password": "pass"})
    response = client.post("/referral/request-withdrawal", data={"pix_key": "my_pix_key"}, follow_redirects=False)

    # Needs to raise 400 Bad Request
    assert response.status_code == 400
    assert "isuficiente" in response.text.lower() or "insuficiente" in response.text.lower()


def test_request_withdrawal_success(client, db_session):
    """Verify withdrawal success when funds are > 100 BRL."""
    auth = AuthService()
    user = UserModel(
        email="rich_referral@example.com",
        hashed_password=auth.hash_password("pass"),
        referral_balance=150.0)
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "rich_referral@example.com", "password": "pass"})
    response = client.post("/referral/request-withdrawal", data={"pix_key": "my_pix_key"}, follow_redirects=False)

    assert response.status_code in (302, 303)
    assert "success=withdraw_requested" in response.headers.get("Location", "")
