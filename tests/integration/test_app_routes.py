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
    user = UserModel(email="prod_test@test.com", hashed_password=auth.hash_password("t3st_p@ssw0rd_2026"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "prod_test@test.com", "password": "t3st_p@ssw0rd_2026"})

    response = client.get("/products")
    assert response.status_code == 200
    assert "Products" in response.text


def test_new_campaign_form_with_auth(client, db_session):
    auth = AuthService()
    user = UserModel(email="camp_test@test.com", hashed_password=auth.hash_password("t3st_p@ssw0rd_2026"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "camp_test@test.com", "password": "t3st_p@ssw0rd_2026"})

    response = client.get("/campaigns/new")
    assert response.status_code == 200
    assert "Campaign" in response.text


def test_campaigns_list_with_auth(client, db_session):
    auth = AuthService()
    user = UserModel(email="list_test@test.com", hashed_password=auth.hash_password("t3st_p@ssw0rd_2026"))
    db_session.add(user)
    db_session.commit()

    client.post("/login", data={"username": "list_test@test.com", "password": "t3st_p@ssw0rd_2026"})

    response = client.get("/")
    assert response.status_code == 200
    assert "Campaigns" in response.text or "Campanhas" in response.text or "Dashboard" in response.text
