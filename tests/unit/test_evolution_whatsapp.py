import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from core.infrastructure.notifications.evolution_whatsapp import (
    EvolutionWhatsAppService,
)


ENV = {"EVOLUTION_API_URL": "http://api.com", "EVOLUTION_API_KEY": "key"}


@pytest.fixture
def svc():
    with patch.dict("os.environ", ENV):
        yield EvolutionWhatsAppService()


@pytest.fixture
def mock_client():
    with patch(
        "core.infrastructure.notifications.evolution_whatsapp.httpx.AsyncClient"
    ) as c:
        instance = c.return_value
        instance.__aenter__.return_value = instance
        instance.__aexit__ = AsyncMock(return_value=False)
        yield instance


# ── send_text ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_text_returns_true_on_2xx(svc, mock_client):
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=201, text="ok"))
    assert await svc.send_text("5511999999@s.whatsapp.net", "hello") is True


@pytest.mark.asyncio
async def test_send_text_returns_true_on_4xx(svc, mock_client):
    """4xx from evolution api should still return True — message may be delivered."""
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=400, text="bad request")
    )
    assert await svc.send_text("5511999999@s.whatsapp.net", "hello") is True


@pytest.mark.asyncio
async def test_send_text_returns_false_on_5xx(svc, mock_client):
    """5xx is a true server error — return False."""
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=500, text="internal error")
    )
    assert await svc.send_text("5511999999@s.whatsapp.net", "hello") is False


@pytest.mark.asyncio
async def test_send_text_returns_true_on_timeout(svc, mock_client):
    """Timeout means request was sent; evolution api usually processes it anyway."""
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    assert await svc.send_text("5511999999@s.whatsapp.net", "hello") is True


@pytest.mark.asyncio
async def test_send_text_returns_false_on_connect_error(svc, mock_client):
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    assert await svc.send_text("5511999999@s.whatsapp.net", "hello") is False


# ── send_image ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_image_returns_true_on_2xx(svc, mock_client):
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=200, text="ok"))
    assert (
        await svc.send_image(
            "5511999999@s.whatsapp.net", "http://img.com/x.jpg", "caption"
        )
        is True
    )


@pytest.mark.asyncio
async def test_send_image_returns_true_on_4xx(svc, mock_client):
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=422, text="unprocessable")
    )
    assert (
        await svc.send_image("5511999999@s.whatsapp.net", "http://img.com/x.jpg")
        is True
    )


@pytest.mark.asyncio
async def test_send_image_returns_false_on_5xx(svc, mock_client):
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=503, text="unavailable")
    )
    assert (
        await svc.send_image("5511999999@s.whatsapp.net", "http://img.com/x.jpg")
        is False
    )


@pytest.mark.asyncio
async def test_send_image_returns_true_on_timeout(svc, mock_client):
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    assert (
        await svc.send_image("5511999999@s.whatsapp.net", "http://img.com/x.jpg")
        is True
    )


# ── send_status ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_status_returns_true_on_2xx(svc, mock_client):
    mock_client.post = AsyncMock(return_value=MagicMock(status_code=201, text="ok"))
    assert await svc.send_status("hello world", type="text") is True


@pytest.mark.asyncio
async def test_send_status_returns_true_on_4xx(svc, mock_client):
    """evolution api sendStatus commonly returns 400 even when message is delivered."""
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=400, text="bad request")
    )
    assert await svc.send_status("hello world", type="text") is True


@pytest.mark.asyncio
async def test_send_status_returns_false_on_5xx(svc, mock_client):
    mock_client.post = AsyncMock(
        return_value=MagicMock(status_code=500, text="server error")
    )
    assert await svc.send_status("hello world", type="text") is False


@pytest.mark.asyncio
async def test_send_status_returns_true_on_timeout(svc, mock_client):
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    assert await svc.send_status("hello world", type="text") is True


@pytest.mark.asyncio
async def test_send_status_returns_false_on_connect_error(svc, mock_client):
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    assert await svc.send_status("hello world", type="text") is False


# ── helpers ───────────────────────────────────────────────────────────────────


def test_clean_phone_adds_country_code(svc):
    assert svc._clean_phone("11999999999").startswith("55")


def test_clean_phone_keeps_existing_country_code(svc):
    assert svc._clean_phone("5511999999999") == "5511999999999"
