import json
import pytest
from fastapi.testclient import TestClient
from bs4 import BeautifulSoup

from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import (
    UserModel,
    CampaignModel,
    StatusCampaignModel,
    BroadcastCampaignModel,
    campaign_groups,
    ProductModel,
    WhatsAppTargetModel,
)


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client, db_session):
    """Creates a user, logs in, and returns the client."""
    auth = AuthService()
    user = UserModel(
        email="dashboard_test@test.com",
        hashed_password=auth.hash_password("testpass123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client.post(
        "/login",
        data={"username": "dashboard_test@test.com", "password": "testpass123"},
    )
    return client, user


def test_dashboard_total_campaigns(authenticated_client, db_session):
    """Total campaigns = sum of all 3 campaign types."""
    client, user = authenticated_client
    uid = user.id

    product = ProductModel(user_id=uid, name="P1", price=1.0)
    db_session.add(product)
    db_session.commit()

    db_session.add_all(
        [
            CampaignModel(
                user_id=uid, title="C1", status="draft", product_id=product.id
            ),
            CampaignModel(
                user_id=uid, title="C2", status="sent", product_id=product.id
            ),
            StatusCampaignModel(user_id=uid, title="S1", status="sent"),
            BroadcastCampaignModel(
                user_id=uid,
                title="B1",
                status="sent",
                instance_id=1,
                target_type="contacts",
                message="hi",
                sent_count=5,
            ),
        ]
    )
    db_session.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    cards = BeautifulSoup(resp.text, "html.parser").select(".stat-value")

    # 2 regular + 1 status + 1 broadcast = 4
    assert (
        cards[0].text.strip() == "4"
    ), f"total_campaigns errado: {cards[0].text.strip()}"


def test_dashboard_sent_messages_recipients(authenticated_client, db_session):
    """
    Sent count is based on actual recipients, not campaign rows:
    - CampaignModel: rows in campaign_groups for sent campaigns
    - StatusCampaignModel: len(target_contacts JSON list)
    - BroadcastCampaignModel: sum(sent_count)
    """
    client, user = authenticated_client
    uid = user.id

    product = ProductModel(user_id=uid, name="P2", price=1.0)
    db_session.add(product)
    db_session.commit()

    # campaign sent to 3 groups via campaign_groups association
    camp = CampaignModel(
        user_id=uid, title="C_sent", status="sent", product_id=product.id
    )
    db_session.add(camp)
    db_session.flush()
    db_session.execute(
        campaign_groups.insert(),
        [
            {"campaign_id": camp.id, "group_jid": "g1@g.us"},
            {"campaign_id": camp.id, "group_jid": "g2@g.us"},
            {"campaign_id": camp.id, "group_jid": "g3@g.us"},
        ],
    )

    # status campaign sent to 4 contacts stored as JSON
    stat = StatusCampaignModel(
        user_id=uid,
        title="S_sent",
        status="sent",
        target_contacts=json.dumps(
            [
                "c1@s.whatsapp.net",
                "c2@s.whatsapp.net",
                "c3@s.whatsapp.net",
                "c4@s.whatsapp.net",
            ]
        ),
    )
    db_session.add(stat)

    # broadcast with sent_count = 7
    broad = BroadcastCampaignModel(
        user_id=uid,
        title="B_sent",
        status="sent",
        instance_id=1,
        target_type="contacts",
        message="hi",
        sent_count=7,
    )
    db_session.add(broad)
    db_session.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    cards = BeautifulSoup(resp.text, "html.parser").select(".stat-value")

    # 3 (campaign_groups) + 4 (status contacts) + 7 (broadcast) = 14
    assert cards[1].text.strip() == "14", f"total_sent errado: {cards[1].text.strip()}"


def test_dashboard_contacts_and_groups_deduplicated(authenticated_client, db_session):
    """
    Contacts and groups counts are deduplicated by JID and only active targets.
    """
    client, user = authenticated_client
    uid = user.id

    # add duplicate contact jid (different instance_id simulates duplicates)
    db_session.add_all(
        [
            WhatsAppTargetModel(
                user_id=uid,
                jid="c1@s.whatsapp.net",
                name="Alice",
                type="chat",
                instance_id=1,
                is_active=True,
            ),
            WhatsAppTargetModel(
                user_id=uid,
                jid="c1@s.whatsapp.net",
                name="Alice",
                type="chat",
                instance_id=2,
                is_active=True,
            ),  # duplicate JID
            WhatsAppTargetModel(
                user_id=uid,
                jid="c2@s.whatsapp.net",
                name="Bob",
                type="chat",
                instance_id=1,
                is_active=True,
            ),
            WhatsAppTargetModel(
                user_id=uid,
                jid="g1@g.us",
                name="Group1",
                type="group",
                instance_id=1,
                is_active=True,
            ),
            WhatsAppTargetModel(
                user_id=uid,
                jid="g2@g.us",
                name="Group2",
                type="group",
                instance_id=1,
                is_active=False,
            ),  # inactive, should NOT count
        ]
    )
    db_session.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    cards = BeautifulSoup(resp.text, "html.parser").select(".stat-value")

    # 2 unique active contacts (c1 deduplicated, c2)
    assert (
        cards[2].text.strip() == "2"
    ), f"contact_count errado: {cards[2].text.strip()}"
    # 1 unique active group (g2 is inactive)
    assert cards[3].text.strip() == "1", f"group_count errado: {cards[3].text.strip()}"
