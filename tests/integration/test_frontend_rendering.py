"""
Frontend rendering tests.
The project uses FastAPI + Jinja2, so frontend testing is done
via TestClient — asserting that correct HTML elements are rendered.
"""
import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel, InstanceModel, StatusCampaignModel


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login_user(client, db_session, email="frontend@test.com"):
    """Helper to create a unique user and log them in by setting cookies directly."""
    auth = AuthService()
    user = UserModel(email=email, hashed_password=auth.hash_password("test_password_placeholder"))
    db_session.add(user)
    db_session.commit()

    # Inject access_token cookie directly
    access_token = auth.create_access_token(data={"sub": email})
    client.cookies.set("access_token", access_token)
    return user


# ── status list ───────────────────────────────────────────────────────────────


def test_status_list_shows_duplicate_button(client, db_session):
    """The status list page must render the duplicate button for each campaign."""
    user = login_user(client, db_session, email="status_list_fe@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_fe", status="connected")
    db_session.add(instance)
    db_session.commit()

    campaign = StatusCampaignModel(
        user_id=user.id, instance_id=instance.id, title="My Status", status="sent"
    )
    db_session.add(campaign)
    db_session.commit()

    response = client.get("/status_campaigns")
    assert response.status_code == 200
    assert "duplicate" in response.text.lower() or "/status_campaigns/duplicate/" in response.text


def test_status_editor_has_existing_image_url_for_campaign_with_image(client, db_session):
    """
    When editing a campaign that has an image, the editor template must render
    the hidden existing_image_url field — this is required for image persistence
    on duplication.
    """
    user = login_user(client, db_session, email="status_edit_fe@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_img_fe", status="connected")
    db_session.add(instance)
    db_session.commit()

    campaign = StatusCampaignModel(
        user_id=user.id,
        instance_id=instance.id,
        title="Campaign With Image",
        status="sent",
        image_url="supabase://images/test.jpg",
    )
    db_session.add(campaign)
    db_session.commit()

    response = client.get(f"/status_campaigns/edit/{campaign.id}")
    assert response.status_code == 200
    assert 'name="existing_image_url"' in response.text


def test_status_duplicate_form_action_does_not_contain_none(client, db_session):
    """
    The duplicated campaign form action must point to /new, not /edit/None.
    This verifies the fix for the 'edit/None' routing bug.
    """
    user = login_user(client, db_session, email="status_dup_fe@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_dup_fe", status="connected")
    db_session.add(instance)
    db_session.commit()

    campaign = StatusCampaignModel(
        user_id=user.id, instance_id=instance.id, title="To Duplicate", status="sent"
    )
    db_session.add(campaign)
    db_session.commit()

    response = client.get(f"/status_campaigns/duplicate/{campaign.id}")
    assert response.status_code == 200
    assert "/edit/None" not in response.text
    assert "/status_campaigns/new" in response.text


# ── broadcast editor ──────────────────────────────────────────────────────────


def test_broadcast_campaigns_list_renders(client, db_session):
    """GET /broadcast/campaigns must return 200 with the campaign list."""
    login_user(client, db_session, email="bc_list_fe@test.com")
    response = client.get("/broadcast/campaigns")
    assert response.status_code == 200


def test_new_broadcast_campaign_form_renders(client, db_session):
    """GET /broadcast/campaigns/new must return 200 with the editor form."""
    user = login_user(client, db_session, email="bc_new_fe@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_bc_new", status="connected")
    db_session.add(instance)
    db_session.commit()

    response = client.get("/broadcast/campaigns/new")
    assert response.status_code == 200
    assert "form" in response.text.lower()


def test_broadcast_duplicate_form_action_does_not_contain_none(client, db_session):
    """
    The duplicated broadcast campaign form action must use /new,
    not /campaigns/edit/None — verifies fix for the Broadcast edit/None bug.
    """
    user = login_user(client, db_session, email="bc_dup_fe@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_bc_dup", status="connected")
    db_session.add(instance)
    db_session.commit()

    from core.infrastructure.database.models import BroadcastCampaignModel
    campaign = BroadcastCampaignModel(
        user_id=user.id,
        instance_id=instance.id,
        title="Broadcast To Dup",
        target_type="contacts",
        status="sent",
        message="Hello",
    )
    db_session.add(campaign)
    db_session.commit()

    response = client.get(f"/broadcast/campaigns/duplicate/{campaign.id}")
    assert response.status_code == 200
    assert "/campaigns/edit/None" not in response.text
    assert "/broadcast/campaigns/new" in response.text
