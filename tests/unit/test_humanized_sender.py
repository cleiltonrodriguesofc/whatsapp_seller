import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.application.services.humanized_sender import HumanizedSender


@pytest.mark.asyncio
async def test_send_campaign_humanized_text_only():
    # Mock WhatsApp Service
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0.1
    sender.max_delay = 0.2

    targets = ["user1", "user2"]
    content = "Hello"

    success = await sender.send_campaign_humanized(targets, content)

    assert success is True
    # Two targets, presence called twice (skipped for status@broadcast, but these are users)
    assert mock_ws.set_presence.call_count == 2
    assert mock_ws.send_text.call_count == 2


@pytest.mark.asyncio
async def test_send_campaign_humanized_with_media():
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_image = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0.1
    sender.max_delay = 0.2

    # Mock get_optimized_base64
    with patch(
        "core.infrastructure.utils.image_utils.get_optimized_base64",
        AsyncMock(return_value="base64data"),
    ):
        targets = ["user1"]
        content = "Hello with image"

        success = await sender.send_campaign_humanized(
            targets, content, media_url="http://example.com/image.jpg"
        )

        assert success is True
        assert mock_ws.send_image.called
        args, kwargs = mock_ws.send_image.call_args
        assert args[0] == "user1"
        assert args[1] == "base64data"
        assert args[2] == content


@pytest.mark.asyncio
async def test_status_broadcast_skips_presence():
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0
    sender.max_delay = 0

    targets = ["status@broadcast"]
    content = "Status Update"

    await sender.send_campaign_humanized(targets, content)

    # Presence should NOT be called for status
    assert mock_ws.set_presence.call_count == 0
    assert mock_ws.send_text.call_count == 1
