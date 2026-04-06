import pytest
from unittest.mock import patch
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


def setup_user_and_instance(db_session, salt):
    auth = AuthService()
    user = UserModel(email=f"tester_{salt}@test.com", hashed_password=auth.hash_password("pass"))
    db_session.add(user)
    db_session.commit()
    instance = InstanceModel(user_id=user.id, name=f"Test_Inst_{salt}")
    db_session.add(instance)
    db_session.commit()
    return user, instance


def test_view_whatsapp_chats_endpoint(client, db_session):
    """Test the /chats frontend rendering endpoint."""
    user, instance = setup_user_and_instance(db_session, "chats")
    client.post("/login", data={"username": "tester_chats@test.com", "password": "pass"})

    with patch("core.presentation.web.routers.whatsapp.EvolutionWhatsAppService.get_active_chats") as mock_get_chats:
        mock_get_chats.return_value = [
            {"id": "uuid1",
             "remoteJid": "111@s.whatsapp.net",
             "name": "Test Active Chat",
             "unreadCount": 1,
             "lastMsgTimestamp": 1000}
        ]
        res = client.get("/chats")
        assert res.status_code == 200
        assert "Test Active Chat" in res.text


def test_get_chat_messages_api(client, db_session):
    """Test the /chats/messages API endpoint directly fetches via WhatsApp Service."""
    user, instance = setup_user_and_instance(db_session, "msgs")
    client.post("/login", data={"username": "tester_msgs@test.com", "password": "pass"})

    with patch("core.presentation.web.routers.whatsapp.EvolutionWhatsAppService.get_chat_messages") as mock_get_msgs:
        mock_get_msgs.return_value = [
            {"key": {"id": "1", "remoteJid": "123@s.whatsapp.net", "fromMe": False},
                "message": {"conversation": "Hello test world!"}}
        ]
        res = client.get(f"/chats/messages?jid=123@s.whatsapp.net&instance_id={instance.id}")
        assert res.status_code == 200
        data = res.json()
        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0]["text"] == "Hello test world!"


def test_sync_whatsapp_targets_prioritizes_remote_jid(client, db_session):
    """Test the /whatsapp/sync endpoint ensuring remoteJid parsing logic works during contact aggregation."""
    user, instance = setup_user_and_instance(db_session, "sync")
    client.post("/login", data={"username": "tester_sync@test.com", "password": "pass"})

    with patch("core.presentation.web.routers.whatsapp.EvolutionWhatsAppService.get_groups") as mock_groups, \
            patch("core.presentation.web.routers.whatsapp.EvolutionWhatsAppService.get_contacts") as mock_contacts, \
            patch("core.presentation.web.routers.whatsapp.EvolutionWhatsAppService."
                  "get_phonebook_contacts") as mock_phonebook:

        # Evolution mock responses
        mock_groups.return_value = [{"id": "grp1@g.us", "subject": "Group 1", "name": "Group 1"}]
        mock_contacts.return_value = [{"id": "internal-uuid",
                                       "remoteJid": "sync1@s.whatsapp.net", "name": "Contact Synced 1"}]
        mock_phonebook.return_value = []

        res = client.get("/whatsapp/sync")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["count"] == 2
