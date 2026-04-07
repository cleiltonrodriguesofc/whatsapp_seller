from datetime import timedelta
from core.application.services.auth_service import AuthService
from core.infrastructure.utils.timezone import now_sp


def test_generate_reset_token():
    token1 = AuthService.generate_reset_token()
    token2 = AuthService.generate_reset_token()

    assert isinstance(token1, str)
    assert len(token1) >= 32
    assert token1 != token2


def test_token_expiration_logic():
    # Valid token (just created)
    now = now_sp()
    assert AuthService.is_token_expired(now + timedelta(minutes=30)) is False

    # Expired token (created 2 hours ago)
    past = now_sp() - timedelta(hours=2)
    assert AuthService.is_token_expired(past) is True

    # Boundary case
    future = now_sp() + timedelta(seconds=10)
    assert AuthService.is_token_expired(future) is False

    expired = now_sp() - timedelta(seconds=1)
    assert AuthService.is_token_expired(expired) is True


def test_none_expiry_is_expired():
    assert AuthService.is_token_expired(None) is True


def test_password_reset_hashing():
    new_password = "new_secure_password"
    hashed = AuthService.hash_password(new_password)

    assert hashed != new_password
    assert AuthService.verify_password(new_password, hashed) is True
