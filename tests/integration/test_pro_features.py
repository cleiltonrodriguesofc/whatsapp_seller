import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.infrastructure.database.models import (
    UserModel,
    SubscriptionModel,
    ReferralCodeModel,
    PlanModel,
    ReferralConversionModel,
)
from core.application.services.auth_service import AuthService


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_registration_creates_trial_and_ref_code(client, db_session):
    # Setup: Ensure a "starter" plan exists
    plan = PlanModel(
        name="starter", display_name="Starter", price_brl=97.0, max_instances=1
    )
    db_session.add(plan)
    db_session.commit()

    # Action: Register a new user
    response = client.post(
        "/register",
        data={
            "email": "trial_user@test.com",
            "password": "password123",
            "business_name": "Test Business",
            "terms_accepted": "on",
        },
    )

    assert response.status_code == 303  # Redirect to dashboard

    # Verify User
    user = db_session.query(UserModel).filter_by(email="trial_user@test.com").first()
    assert user is not None

    # Verify Referral Code
    ref_code = db_session.query(ReferralCodeModel).filter_by(user_id=user.id).first()
    assert ref_code is not None
    assert len(ref_code.code) == 8

    # Verify Subscription
    subscription = (
        db_session.query(SubscriptionModel).filter_by(user_id=user.id).first()
    )
    assert subscription is not None
    assert subscription.status == "trialing"
    assert subscription.plan_id == plan.id
    # Check trial ends in ~3 days
    delta = subscription.trial_ends_at - datetime.utcnow()
    assert 1 < delta.days <= 3


def test_referral_conversion_tracking(client, db_session):
    # Setup: Referrer user
    auth = AuthService()
    referrer = UserModel(
        email="referrer@test.com", hashed_password=auth.hash_password("pass")
    )
    db_session.add(referrer)
    db_session.commit()

    ref_code = ReferralCodeModel(user_id=referrer.id, code="REF12345")
    db_session.add(ref_code)

    plan = PlanModel(
        name="starter", display_name="Starter", price_brl=97.0, max_instances=1
    )
    db_session.add(plan)
    db_session.commit()

    # Action: Register with referral code
    client.post(
        "/register?ref=REF12345",
        data={
            "email": "referred_user@test.com",
            "password": "password123",
            "business_name": "Referred Business",
            "terms_accepted": "on",
        },
    )

    # Verify Conversion record
    new_user = (
        db_session.query(UserModel).filter_by(email="referred_user@test.com").first()
    )
    conversion = (
        db_session.query(ReferralConversionModel)
        .filter_by(referred_id=new_user.id)
        .first()
    )

    assert conversion is not None
    assert conversion.referrer_id == referrer.id
    assert conversion.status == "pending"


def test_static_pages_accessibility(client):
    for path in ["/terms", "/privacy", "/docs"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "WhatSeller Pro" in response.text


def test_pricing_on_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Automatize" in response.text
    assert "3.2M" in response.text
    assert "Capacidades" in response.text
    assert "Metodologia" in response.text
