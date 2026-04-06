"""
Integration tests for the status_campaigns router.
Verifies HTTP routes, form handling, and the existing_image_url persistence
logic introduced to fix image loss during campaign duplication.
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


def get_auth_headers(client, db_session, email="test@example.com"):
    """Helper to create a user and log them in by setting cookies directly."""
    auth = AuthService()
    user = UserModel(email=email, hashed_password=auth.hash_password("mock_auth_val_x9"))
    db_session.add(user)
    db_session.commit()

    # Inject access_token cookie directly to bypass fragile POST /login in tests
    access_token = auth.create_access_token(data={"sub": email})
    client.cookies.set("access_token", access_token)
    return user


def test_status_campaigns_list_auth(client, db_session):
    get_auth_headers(client, db_session, email="list_status@test.com")
    response = client.get("/status_campaigns")
    assert response.status_code == 200
    assert "Status Automático" in response.text


def test_new_status_campaign_form_auth(client, db_session):
    get_auth_headers(client, db_session, email="new_status@test.com")
    response = client.get("/status_campaigns/new")
    assert response.status_code == 200
    assert "Novo Status Automático" in response.text


def test_create_status_campaign_auth(client, db_session):
    user = get_auth_headers(client, db_session, email="create_status@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_status", status="connected")
    db_session.add(instance)
    db_session.commit()

    response = client.post(
        "/status_campaigns/new",
        data={
            "title": "New Web Status",
            "caption": "Check this web status",
            "background_color": "#128C7E",
            "instance_id": instance.id,
            "target_groups": '["123@s.whatsapp.net"]',
            "is_recurring": "false",
            "save_mode": "schedule",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/status_campaigns"


def test_create_status_preserves_existing_image_url(client, db_session):
    """
    When no new file is uploaded, existing_image_url must be used as the
    campaign's image_url — this is the fix for image loss during duplication.
    """
    user = get_auth_headers(client, db_session, email="dup_preserve@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_img", status="connected")
    db_session.add(instance)
    db_session.commit()

    image_url = "supabase://images/abc123.jpg"

    response = client.post(
        "/status_campaigns/new",
        data={
            "title": "Duplicated Campaign",
            "caption": "With existing image",
            "background_color": "#128C7E",
            "instance_id": instance.id,
            "target_groups": "[]",
            "is_recurring": "false",
            "save_mode": "draft",
            "existing_image_url": image_url,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Force SQLAlchemy to update its local cache from the DB
    db_session.expire_all()

    # verify the campaign was saved with the existing image url
    saved = db_session.query(StatusCampaignModel).filter_by(title="Duplicated Campaign").first()
    assert saved is not None
    assert saved.image_url == image_url


def test_create_status_new_file_overrides_existing_image_url(client, db_session):
    """
    When both a new file and existing_image_url are provided, the new file must
    take priority (user explicitly chose a new image).
    """
    user = get_auth_headers(client, db_session, email="dup_override@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_override", status="connected")
    db_session.add(instance)
    db_session.commit()

    old_url = "supabase://images/old.jpg"

    async def mock_save(*args, **kwargs):
        return "supabase://images/new_uploaded.jpg"

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "core.presentation.web.routers.status_campaigns._save_uploaded_image",
            mock_save,
        )

        import io
        fake_file = io.BytesIO(b"fake image data")

        response = client.post(
            "/status_campaigns/new",
            data={
                "title": "Override Test",
                "background_color": "#128C7E",
                "instance_id": instance.id,
                "target_groups": "[]",
                "is_recurring": "false",
                "save_mode": "draft",
                "existing_image_url": old_url,
            },
            files={"image_file": ("new_image.jpg", fake_file, "image/jpeg")},
            follow_redirects=False,
        )

    assert response.status_code == 303

    saved = db_session.query(StatusCampaignModel).filter_by(title="Override Test").first()
    assert saved is not None
    # new file should win over the existing url
    assert saved.image_url != old_url


def test_duplicate_status_campaign_form_renders_correctly(client, db_session):
    """GET /status_campaigns/duplicate/{id} must return 200 with pre-filled form."""
    user = get_auth_headers(client, db_session, email="dup_form@test.com")
    instance = InstanceModel(user_id=user.id, name="inst_dup", status="connected")
    db_session.add(instance)
    db_session.commit()

    # create a campaign to duplicate
    campaign = StatusCampaignModel(
        user_id=user.id,
        instance_id=instance.id,
        title="Original Campaign",
        status="sent",
        image_url="supabase://images/original.jpg",
    )
    db_session.add(campaign)
    db_session.commit()

    response = client.get(f"/status_campaigns/duplicate/{campaign.id}")
    assert response.status_code == 200
    assert "Original Campaign" in response.text
    # hidden field with existing image url must be present in the form
    assert 'name="existing_image_url"' in response.text
    # the form action must NOT contain 'None'
    assert "/edit/None" not in response.text
