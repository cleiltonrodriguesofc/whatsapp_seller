import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.infrastructure.database.models import StatusCampaignModel, InstanceModel


@pytest.mark.asyncio
async def test_execute_status_task_calls_expire_before_send():
    """
    Verifies that db.expire(model) is called to clear the sqlalchemy identity map
    cache before calling send_status_campaign, preventing stale data issues.
    """
    mock_model = MagicMock(spec=StatusCampaignModel)
    mock_model.id = 1
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_model

    with (
        patch("core.presentation.web.scheduler.SessionLocal", return_value=mock_db),
        patch(
            "core.presentation.web.scheduler.send_status_campaign",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        from core.presentation.web.scheduler import execute_status_campaign_task

        await execute_status_campaign_task(1)

        mock_db.expire.assert_called_once_with(mock_model)
        mock_send.assert_called_once_with(1, mock_db)


@pytest.mark.asyncio
async def test_execute_status_task_recovery_session_on_failure():
    """
    When send_status_campaign raises an exception, a fresh recovery session
    must force the campaign status to 'failed' to prevent the record from
    being stuck in 'sending' indefinitely.
    """
    mock_model = MagicMock(spec=StatusCampaignModel)
    mock_model.id = 1

    # primary session: query finds the model
    primary_db = MagicMock()
    primary_db.query.return_value.filter.return_value.first.return_value = mock_model

    # recovery session: also finds the (stuck) model
    stuck_model = MagicMock(spec=StatusCampaignModel)
    stuck_model.id = 1
    recovery_db = MagicMock()
    recovery_db.query.return_value.filter.return_value.first.return_value = stuck_model

    session_calls = [primary_db, recovery_db]

    with (
        patch(
            "core.presentation.web.scheduler.SessionLocal", side_effect=session_calls
        ),
        patch(
            "core.presentation.web.scheduler.send_status_campaign",
            new_callable=AsyncMock,
            side_effect=RuntimeError("api exploded"),
        ),
    ):
        from core.presentation.web.scheduler import execute_status_campaign_task

        await execute_status_campaign_task(1)

        # recovery session must have set status to 'failed' and committed
        assert stuck_model.status == "failed"
        recovery_db.commit.assert_called_once()
        recovery_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_send_status_campaign_marks_sent_on_success():
    """Full happy path: model found, instance found, send_status returns True → status='sent'."""
    mock_model = MagicMock(spec=StatusCampaignModel)
    mock_model.id = 42
    mock_model.title = "Bom Dia"
    mock_model.image_url = None
    mock_model.caption = "Bom dia a todos!"
    mock_model.background_color = "#128C7E"
    mock_model.target_contacts = None

    mock_instance = MagicMock(spec=InstanceModel)
    mock_instance.name = "inst1"
    mock_instance.apikey = "key1"

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_model,
        mock_instance,
    ]

    with patch("core.presentation.web.scheduler.EvolutionWhatsAppService") as MockSvc:
        mock_svc_instance = MockSvc.return_value
        mock_svc_instance.send_status = AsyncMock(return_value=True)

        from core.presentation.web.scheduler import send_status_campaign

        await send_status_campaign(42, mock_db)

        assert mock_model.status == "sent"
        mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_send_status_campaign_marks_failed_when_instance_missing():
    """When instance is not found, status must be set to 'failed' immediately."""
    mock_model = MagicMock(spec=StatusCampaignModel)
    mock_model.id = 99
    mock_model.instance_id = 999

    mock_db = MagicMock()
    # first call returns model, second (instance lookup) returns None
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        mock_model,
        None,
    ]

    from core.presentation.web.scheduler import send_status_campaign

    await send_status_campaign(99, mock_db)

    assert mock_model.status == "failed"
    mock_db.commit.assert_called()
