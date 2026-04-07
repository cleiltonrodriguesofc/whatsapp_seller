import pytest
from fastapi.testclient import TestClient
from core.presentation.web.app import app
from core.infrastructure.database.session import get_db
from core.application.services.auth_service import AuthService
from core.infrastructure.database.models import UserModel, ActivityLogModel


@pytest.fixture
def client(override_get_db):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_deactivated_user_access_denied(client, db_session):
    """Users with is_active=False must be rejected and redirected to login."""
    auth = AuthService()
    user = UserModel(
        email="deactivated@test.com",
        hashed_password=auth.hash_password("password"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    # Attempt to login (the login route itself doesn't check is_active yet, but get_current_user does)
    client.post(
        "/login", data={"username": "deactivated@test.com", "password": "password"}
    )

    # accessing a protected route should redirect due to is_active check in get_current_user
    # Note: get_current_user is called via Depends(login_required)
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/login" in response.headers.get("Location", "")


def test_activity_log_system_event_null_user(db_session):
    """ActivityLog must support null user_id for system-level events."""
    from datetime import datetime

    log = ActivityLogModel(
        user_id=None,
        event_type="system_startup",
        description="System started successfully without user context",
        timestamp=datetime.utcnow(),
    )
    db_session.add(log)
    db_session.commit()

    saved_log = (
        db_session.query(ActivityLogModel)
        .filter_by(event_type="system_startup")
        .first()
    )
    assert saved_log is not None
    assert saved_log.user_id is None
    assert "System started" in saved_log.description


def test_admin_dashboard_vision_2_0_rendering(client, db_session):
    """Admin dashboard must render with Vision 2.0 design tokens."""
    auth = AuthService()
    admin = UserModel(
        email="admin@vision.com",
        hashed_password=auth.hash_password("adminpass"),
        is_admin=True,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    # Login as admin
    client.post(
        "/login", data={"username": "admin@vision.com", "password": "adminpass"}
    )

    response = client.get("/admin/")
    assert response.status_code == 200
    # Check for Vision 2.0 specific design tokens/text
    assert "Visão do Administrador" in response.text
    assert "admin-card" in response.text
    assert "Glassmorphism" not in response.text  # (it's in CSS, not HTML text)
    assert "Audit Logs" in response.text
    assert "stat-premium" in response.text


def test_admin_users_page_renders_without_500(client, db_session):
    """Admin users page must load without internal server error."""
    auth = AuthService()
    admin = UserModel(
        email="admin_users@test.com",
        hashed_password=auth.hash_password("pass"),
        is_admin=True,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    client.post("/login", data={"username": "admin_users@test.com", "password": "pass"})

    response = client.get("/admin/users")
    assert response.status_code == 200
    assert "Membros da Comunidade" in response.text
    assert "Operações" in response.text
