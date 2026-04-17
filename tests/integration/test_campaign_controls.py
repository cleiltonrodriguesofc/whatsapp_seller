"""
Integration tests for campaign control endpoints (pause, resume, cancel, resend).
Covers all three campaign types: Product (CampaignModel), Status (StatusCampaignModel),
and Broadcast (BroadcastCampaignModel).
"""

import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import (
    UserModel,
    InstanceModel,
    CampaignModel,
    StatusCampaignModel,
    BroadcastCampaignModel,
    ProductModel,
)


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login_user(client, db_session, email="controls@test.com"):
    """helper to create a user and authenticate via cookie."""
    auth = AuthService()
    user = UserModel(
        email=email, hashed_password=auth.hash_password("placeholder")
    )
    db_session.add(user)
    db_session.commit()

    access_token = auth.create_access_token(data={"sub": email})
    client.cookies.set("access_token", access_token)
    return user


def make_product(db_session, user_id):
    """helper to create a product for CampaignModel."""
    product = ProductModel(
        user_id=user_id,
        name="Test Product",
        description="desc",
        price=10.0,
        affiliate_link="http://example.com",
    )
    db_session.add(product)
    db_session.commit()
    return product


def make_instance(db_session, user_id, name="inst_ctrl"):
    """helper to create an instance."""
    instance = InstanceModel(user_id=user_id, name=name, status="connected")
    db_session.add(instance)
    db_session.commit()
    return instance


# =============================================================================
# product campaign controls (CampaignModel)
# =============================================================================


class TestProductCampaignControls:
    """tests for POST /campaign/{action}/{id} endpoints."""

    def test_pause_scheduled_campaign(self, client, db_session):
        user = login_user(client, db_session, email="prod_pause@test.com")
        instance = make_instance(db_session, user.id, "inst_pp")
        product = make_product(db_session, user.id)

        campaign = CampaignModel(
            user_id=user.id,
            title="Scheduled Campaign",
            product_id=product.id,
            instance_id=instance.id,
            status="scheduled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/campaign/pause/{campaign.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "paused"

        db_session.expire_all()
        updated = db_session.query(CampaignModel).get(campaign.id)
        assert updated.status == "paused"

    def test_resume_paused_campaign(self, client, db_session):
        user = login_user(client, db_session, email="prod_resume@test.com")
        instance = make_instance(db_session, user.id, "inst_pr")
        product = make_product(db_session, user.id)

        campaign = CampaignModel(
            user_id=user.id,
            title="Paused Campaign",
            product_id=product.id,
            instance_id=instance.id,
            status="paused",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/campaign/resume/{campaign.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "scheduled"

        db_session.expire_all()
        updated = db_session.query(CampaignModel).get(campaign.id)
        assert updated.status == "scheduled"

    def test_cancel_scheduled_campaign(self, client, db_session):
        user = login_user(client, db_session, email="prod_cancel@test.com")
        instance = make_instance(db_session, user.id, "inst_pc")
        product = make_product(db_session, user.id)

        campaign = CampaignModel(
            user_id=user.id,
            title="To Cancel",
            product_id=product.id,
            instance_id=instance.id,
            status="scheduled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/campaign/cancel/{campaign.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "canceled"

        db_session.expire_all()
        updated = db_session.query(CampaignModel).get(campaign.id)
        assert updated.status == "canceled"

    def test_resend_sent_campaign(self, client, db_session):
        user = login_user(client, db_session, email="prod_resend@test.com")
        instance = make_instance(db_session, user.id, "inst_prs")
        product = make_product(db_session, user.id)

        from datetime import datetime

        campaign = CampaignModel(
            user_id=user.id,
            title="Already Sent",
            product_id=product.id,
            instance_id=instance.id,
            status="sent",
            sent_at=datetime(2026, 1, 1, 12, 0),
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/campaign/resend/{campaign.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "scheduled"

        db_session.expire_all()
        updated = db_session.query(CampaignModel).get(campaign.id)
        assert updated.status == "scheduled"
        assert updated.sent_at is None

    def test_resend_failed_campaign(self, client, db_session):
        user = login_user(client, db_session, email="prod_resend_fail@test.com")
        instance = make_instance(db_session, user.id, "inst_prf")
        product = make_product(db_session, user.id)

        campaign = CampaignModel(
            user_id=user.id,
            title="Failed Campaign",
            product_id=product.id,
            instance_id=instance.id,
            status="failed",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/campaign/resend/{campaign.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"

    def test_resend_canceled_campaign(self, client, db_session):
        user = login_user(client, db_session, email="prod_resend_canc@test.com")
        instance = make_instance(db_session, user.id, "inst_prc")
        product = make_product(db_session, user.id)

        campaign = CampaignModel(
            user_id=user.id,
            title="Canceled Campaign",
            product_id=product.id,
            instance_id=instance.id,
            status="canceled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/campaign/resend/{campaign.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"

    def test_control_returns_404_for_wrong_user(self, client, db_session):
        user = login_user(client, db_session, email="prod_wrong@test.com")
        instance = make_instance(db_session, user.id, "inst_pw")
        product = make_product(db_session, user.id)

        # create campaign owned by this user
        campaign = CampaignModel(
            user_id=user.id,
            title="My Campaign",
            product_id=product.id,
            instance_id=instance.id,
            status="scheduled",
        )
        db_session.add(campaign)
        db_session.commit()

        # login as a different user
        login_user(client, db_session, email="prod_other@test.com")

        response = client.post(f"/campaign/pause/{campaign.id}")
        assert response.status_code == 404

    def test_control_returns_404_for_nonexistent(self, client, db_session):
        login_user(client, db_session, email="prod_ghost@test.com")
        response = client.post("/campaign/pause/999999")
        assert response.status_code == 404


# =============================================================================
# status campaign controls (StatusCampaignModel)
# =============================================================================


class TestStatusCampaignControls:
    """tests for POST /status_campaigns/{action}/{id} endpoints."""

    def test_pause_status_campaign(self, client, db_session):
        user = login_user(client, db_session, email="sc_pause@test.com")
        instance = make_instance(db_session, user.id, "inst_sp")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Scheduled Status",
            status="scheduled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/status_campaigns/pause/{campaign.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        db_session.expire_all()
        updated = db_session.query(StatusCampaignModel).get(campaign.id)
        assert updated.status == "paused"

    def test_resume_status_campaign(self, client, db_session):
        user = login_user(client, db_session, email="sc_resume@test.com")
        instance = make_instance(db_session, user.id, "inst_sr")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Paused Status",
            status="paused",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/status_campaigns/resume/{campaign.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"

        db_session.expire_all()
        updated = db_session.query(StatusCampaignModel).get(campaign.id)
        assert updated.status == "scheduled"

    def test_cancel_status_campaign(self, client, db_session):
        user = login_user(client, db_session, email="sc_cancel@test.com")
        instance = make_instance(db_session, user.id, "inst_sc")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Active Status",
            status="sending",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/status_campaigns/cancel/{campaign.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "canceled"

        db_session.expire_all()
        updated = db_session.query(StatusCampaignModel).get(campaign.id)
        assert updated.status == "canceled"

    def test_resend_status_campaign(self, client, db_session):
        user = login_user(client, db_session, email="sc_resend@test.com")
        instance = make_instance(db_session, user.id, "inst_srs")

        from datetime import datetime

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Sent Status",
            status="sent",
            sent_at=datetime(2026, 1, 1, 12, 0),
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/status_campaigns/resend/{campaign.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"

        db_session.expire_all()
        updated = db_session.query(StatusCampaignModel).get(campaign.id)
        assert updated.status == "scheduled"
        assert updated.sent_at is None

    def test_status_control_returns_404_for_wrong_user(self, client, db_session):
        user = login_user(client, db_session, email="sc_wrong@test.com")
        instance = make_instance(db_session, user.id, "inst_sw")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Owner Status",
            status="scheduled",
        )
        db_session.add(campaign)
        db_session.commit()

        # login as someone else
        login_user(client, db_session, email="sc_other@test.com")

        response = client.post(f"/status_campaigns/pause/{campaign.id}")
        assert response.status_code == 404


# =============================================================================
# broadcast campaign controls (BroadcastCampaignModel)
# =============================================================================


class TestBroadcastCampaignControls:
    """tests for POST /broadcast/campaigns/{id}/{action} endpoints."""

    def test_pause_broadcast_campaign(self, client, db_session):
        user = login_user(client, db_session, email="bc_pause@test.com")
        instance = make_instance(db_session, user.id, "inst_bp")

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Scheduled Broadcast",
            target_type="contacts",
            status="scheduled",
            message="hello",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/broadcast/campaigns/{campaign.id}/pause")
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        db_session.expire_all()
        updated = db_session.query(BroadcastCampaignModel).get(campaign.id)
        assert updated.status == "paused"

    def test_resume_broadcast_campaign(self, client, db_session):
        user = login_user(client, db_session, email="bc_resume@test.com")
        instance = make_instance(db_session, user.id, "inst_br")

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Paused Broadcast",
            target_type="contacts",
            status="paused",
            message="hello",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/broadcast/campaigns/{campaign.id}/resume")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"

    def test_cancel_broadcast_campaign(self, client, db_session):
        user = login_user(client, db_session, email="bc_cancel@test.com")
        instance = make_instance(db_session, user.id, "inst_bc")

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Active Broadcast",
            target_type="groups",
            status="sending",
            message="hello",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/broadcast/campaigns/{campaign.id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "canceled"

    def test_resend_broadcast_campaign(self, client, db_session):
        user = login_user(client, db_session, email="bc_resend@test.com")
        instance = make_instance(db_session, user.id, "inst_brs")

        from datetime import datetime

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Sent Broadcast",
            target_type="contacts",
            status="sent",
            message="hello",
            sent_count=10,
            failed_count=2,
            sent_at=datetime(2026, 1, 1, 12, 0),
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.post(f"/broadcast/campaigns/{campaign.id}/resend")
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"

        db_session.expire_all()
        updated = db_session.query(BroadcastCampaignModel).get(campaign.id)
        assert updated.status == "scheduled"
        assert updated.sent_at is None
        assert updated.sent_count == 0
        assert updated.failed_count == 0

    def test_broadcast_control_returns_404_for_wrong_user(self, client, db_session):
        user = login_user(client, db_session, email="bc_wrong@test.com")
        instance = make_instance(db_session, user.id, "inst_bw")

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Owner Broadcast",
            target_type="contacts",
            status="scheduled",
            message="hello",
        )
        db_session.add(campaign)
        db_session.commit()

        login_user(client, db_session, email="bc_other@test.com")
        response = client.post(f"/broadcast/campaigns/{campaign.id}/pause")
        assert response.status_code == 404


# =============================================================================
# ui rendering — campaign control buttons
# =============================================================================


class TestCampaignControlUI:
    """tests that verify control buttons render correctly in templates."""

    def test_status_list_shows_pause_for_scheduled(self, client, db_session):
        user = login_user(client, db_session, email="ui_pause@test.com")
        instance = make_instance(db_session, user.id, "inst_up")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Scheduled UI",
            status="scheduled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/status_campaigns")
        assert response.status_code == 200
        # should have pause button with controlCampaign call
        assert "pause" in response.text.lower()
        # should always have edit link
        assert f"/status_campaigns/edit/{campaign.id}" in response.text

    def test_status_list_shows_resume_for_paused(self, client, db_session):
        user = login_user(client, db_session, email="ui_resume@test.com")
        instance = make_instance(db_session, user.id, "inst_ur")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Paused UI",
            status="paused",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/status_campaigns")
        assert response.status_code == 200
        assert "resume" in response.text.lower()
        assert "PAUSADO" in response.text

    def test_status_list_shows_resend_for_sent(self, client, db_session):
        user = login_user(client, db_session, email="ui_resend@test.com")
        instance = make_instance(db_session, user.id, "inst_urs")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Sent UI",
            status="sent",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/status_campaigns")
        assert response.status_code == 200
        assert "resend" in response.text.lower()
        assert "ENVIADO" in response.text

    def test_status_list_shows_resend_for_canceled(self, client, db_session):
        user = login_user(client, db_session, email="ui_canc@test.com")
        instance = make_instance(db_session, user.id, "inst_uc")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Canceled UI",
            status="canceled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/status_campaigns")
        assert response.status_code == 200
        assert "resend" in response.text.lower()
        assert "CANCELADO" in response.text

    def test_status_detail_shows_paused_badge(self, client, db_session):
        user = login_user(client, db_session, email="ui_det_p@test.com")
        instance = make_instance(db_session, user.id, "inst_udp")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Detail Paused",
            status="paused",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get(f"/status_campaigns/{campaign.id}")
        assert response.status_code == 200
        assert "PAUSADO" in response.text
        assert "resume" in response.text.lower()

    def test_status_detail_shows_canceled_badge(self, client, db_session):
        user = login_user(client, db_session, email="ui_det_c@test.com")
        instance = make_instance(db_session, user.id, "inst_udc")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Detail Canceled",
            status="canceled",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get(f"/status_campaigns/{campaign.id}")
        assert response.status_code == 200
        assert "CANCELADO" in response.text
        assert "REENVIAR" in response.text.upper()

    def test_edit_always_available_for_sent_status(self, client, db_session):
        """edit link must be present regardless of campaign status."""
        user = login_user(client, db_session, email="ui_edit_sent@test.com")
        instance = make_instance(db_session, user.id, "inst_ues")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Edit Sent",
            status="sent",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/status_campaigns")
        assert response.status_code == 200
        assert f"/status_campaigns/edit/{campaign.id}" in response.text

    def test_edit_always_available_for_failed_status(self, client, db_session):
        """edit link must be present for failed campaigns too."""
        user = login_user(client, db_session, email="ui_edit_fail@test.com")
        instance = make_instance(db_session, user.id, "inst_uef")

        campaign = StatusCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Edit Failed",
            status="failed",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/status_campaigns")
        assert response.status_code == 200
        assert f"/status_campaigns/edit/{campaign.id}" in response.text

    def test_broadcast_list_shows_paused_pill(self, client, db_session):
        user = login_user(client, db_session, email="ui_bc_p@test.com")
        instance = make_instance(db_session, user.id, "inst_ubp")

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Paused BC",
            target_type="contacts",
            status="paused",
            message="hello",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/broadcast/campaigns")
        assert response.status_code == 200
        assert "PAUSADO" in response.text

    def test_broadcast_list_shows_canceled_pill(self, client, db_session):
        user = login_user(client, db_session, email="ui_bc_c@test.com")
        instance = make_instance(db_session, user.id, "inst_ubc")

        campaign = BroadcastCampaignModel(
            user_id=user.id,
            instance_id=instance.id,
            title="Canceled BC",
            target_type="contacts",
            status="canceled",
            message="hello",
        )
        db_session.add(campaign)
        db_session.commit()

        response = client.get("/broadcast/campaigns")
        assert response.status_code == 200
        assert "CANCELADO" in response.text

    def test_global_control_js_is_available(self, client, db_session):
        """controlCampaign function must be defined in base.html for all pages."""
        login_user(client, db_session, email="ui_js@test.com")
        response = client.get("/status_campaigns")
        assert response.status_code == 200
        assert "controlCampaign" in response.text
