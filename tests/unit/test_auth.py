from core.application.services.auth_service import AuthService


def test_password_hashing():
    password = "secret_password"
    hashed = AuthService.hash_password(password)
    assert hashed != password
    assert AuthService.verify_password(password, hashed) is True
    assert AuthService.verify_password("wrong_password", hashed) is False


def test_token_creation_and_decoding():
    data = {"user_id": 123, "email": "test@example.com"}
    token = AuthService.create_access_token(data)
    assert isinstance(token, str)

    decoded = AuthService.decode_access_token(token)
    assert decoded is not None
    assert decoded["user_id"] == 123
    assert decoded["email"] == "test@example.com"


def test_invalid_token():
    assert AuthService.decode_access_token("invalid_token") is None
