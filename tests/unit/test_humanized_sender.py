import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.application.services.humanized_sender import HumanizedSender


@pytest.mark.asyncio
async def test_send_campaign_humanized_text_only():
    """send_campaign_humanized returns a result dict with 'completed' status on success."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0.1
    sender.max_delay = 0.2

    targets = ["user1", "user2"]
    content = "Hello"

    result = await sender.send_campaign_humanized(targets, content)

    assert isinstance(result, dict)
    assert result["status"] == "completed"
    assert result["sent"] == 2
    assert result["total"] == 2
    # two targets, presence called twice (skipped for status@broadcast, but these are users)
    assert mock_ws.set_presence.call_count == 2
    assert mock_ws.send_text.call_count == 2


@pytest.mark.asyncio
async def test_send_campaign_humanized_with_media():
    """send_campaign_humanized sends images and returns result dict on success."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_image = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0.1
    sender.max_delay = 0.2

    with patch(
        "core.infrastructure.utils.image_utils.get_optimized_base64",
        AsyncMock(return_value="base64data"),
    ):
        targets = ["user1"]
        content = "Hello with image"

        result = await sender.send_campaign_humanized(
            targets, content, media_url="http://example.com/image.jpg"
        )

        assert isinstance(result, dict)
        assert result["status"] == "completed"
        assert result["sent"] == 1
        assert result["total"] == 1
        assert mock_ws.send_image.called
        args, kwargs = mock_ws.send_image.call_args
        assert args[0] == "user1"
        assert args[1] == "base64data"
        assert args[2] == content


@pytest.mark.asyncio
async def test_status_broadcast_skips_presence():
    """presence should not be called for status@broadcast targets."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0
    sender.max_delay = 0

    targets = ["status@broadcast"]
    content = "Status Update"

    await sender.send_campaign_humanized(targets, content)

    # presence should NOT be called for status
    assert mock_ws.set_presence.call_count == 0
    assert mock_ws.send_text.call_count == 1


@pytest.mark.asyncio
async def test_send_campaign_humanized_returns_failed_on_all_failures():
    """when all sends fail, status should be 'failed'."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=False)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0.1
    sender.max_delay = 0.2

    result = await sender.send_campaign_humanized(["u1", "u2"], "fail msg")

    assert result["status"] == "failed"
    assert result["sent"] == 0
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_send_campaign_humanized_partial_failure():
    """when some sends fail, status should be 'failed' but sent count reflects partial success."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    # first call succeeds, second fails
    mock_ws.send_text = AsyncMock(side_effect=[True, False])

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0.1
    sender.max_delay = 0.2

    result = await sender.send_campaign_humanized(["u1", "u2"], "partial")

    assert result["status"] == "failed"
    assert result["sent"] == 1
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_send_campaign_humanized_paused_stops_loop():
    """when campaign status changes to 'paused' mid-loop, return partial result."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0
    sender.max_delay = 0

    # simulate a db session that returns a paused campaign on the second iteration
    mock_campaign_scheduled = MagicMock()
    mock_campaign_scheduled.status = "sending"

    mock_campaign_paused = MagicMock()
    mock_campaign_paused.status = "paused"

    mock_db = MagicMock()
    mock_db.expire_all = MagicMock()
    # first query returns sending (proceed), second query returns paused (stop)
    mock_db.query.return_value.get.side_effect = [
        mock_campaign_scheduled,
        mock_campaign_paused,
    ]

    result = await sender.send_campaign_humanized(
        ["u1", "u2", "u3"], "msg", campaign_id=42, db=mock_db
    )

    assert result["status"] == "paused"
    assert result["sent"] == 1  # only the first was sent before pause detected
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_send_campaign_humanized_canceled_stops_loop():
    """when campaign status changes to 'canceled' mid-loop, return partial result."""
    mock_ws = MagicMock()
    mock_ws.set_presence = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=True)

    sender = HumanizedSender(mock_ws)
    sender.min_delay = 0
    sender.max_delay = 0

    mock_campaign_canceled = MagicMock()
    mock_campaign_canceled.status = "canceled"

    mock_db = MagicMock()
    mock_db.expire_all = MagicMock()
    mock_db.query.return_value.get.return_value = mock_campaign_canceled

    result = await sender.send_campaign_humanized(
        ["u1", "u2"], "msg", campaign_id=42, db=mock_db
    )

    assert result["status"] == "canceled"
    assert result["sent"] == 0
    assert result["total"] == 2
    # send_text should never be called because canceled was detected on first check
    assert mock_ws.send_text.call_count == 0
