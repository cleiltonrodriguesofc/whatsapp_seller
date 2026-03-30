import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.application.use_cases.execute_broadcast_campaign import (
    ExecuteBroadcastCampaignUseCase,
    _is_group_jid,
)


# ── helper ────────────────────────────────────────────────────────────────────


def test_is_group_jid_true_for_group():
    assert _is_group_jid("1234567890@g.us") is True


def test_is_group_jid_false_for_contact():
    assert _is_group_jid("5511999999@s.whatsapp.net") is False


# ── use case ──────────────────────────────────────────────────────────────────


@pytest.fixture
def use_case():
    db = MagicMock()
    broadcast_repo = MagicMock()
    list_repo = MagicMock()
    target_repo = MagicMock()
    list_repo.db = db
    target_repo.db = db
    return ExecuteBroadcastCampaignUseCase(db, broadcast_repo, list_repo, target_repo)


@pytest.mark.asyncio
async def test_execute_skips_already_sent_campaign(use_case):
    """Campaigns already in 'sent' should be skipped without sending."""
    campaign = MagicMock()
    campaign.status = "sent"
    use_case.broadcast_repo.get_by_id.return_value = campaign

    await use_case.execute(1)

    # repo.save must NOT be called since we skipped
    use_case.broadcast_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_already_failed_campaign(use_case):
    campaign = MagicMock()
    campaign.status = "failed"
    use_case.broadcast_repo.get_by_id.return_value = campaign

    await use_case.execute(1)

    use_case.broadcast_repo.save.assert_not_called()


@pytest.mark.asyncio
async def test_execute_marks_failed_when_instance_not_found(use_case):
    """When instance model is not found, campaign must be marked as 'failed'."""
    campaign = MagicMock()
    campaign.status = "scheduled"
    campaign.target_type = "contacts"
    campaign.target_jids = []
    campaign.image_url = None
    use_case.broadcast_repo.get_by_id.return_value = campaign

    # instance not found
    use_case.db.query.return_value.get.return_value = None

    with patch("core.application.use_cases.execute_broadcast_campaign.EvolutionWhatsAppService"):
        await use_case.execute(1)

    assert campaign.status == "failed"


@pytest.mark.asyncio
async def test_execute_sends_to_contacts_and_updates_counts(use_case):
    """
    Verifies that the use case iterates over targets, calls send_text for
    each one, and updates sent_count and failed_count correctly.
    """
    campaign = MagicMock()
    campaign.id = 1
    campaign.status = "scheduled"
    campaign.target_type = "contacts"
    campaign.target_jids = ["5511111@s.whatsapp.net", "5522222@s.whatsapp.net"]
    campaign.user_id = 1
    campaign.image_url = None
    campaign.message = "Hello {nome}"
    campaign.is_recurring = False
    use_case.broadcast_repo.get_by_id.return_value = campaign

    from core.infrastructure.database.models import InstanceModel, WhatsAppTargetModel
    mock_instance = MagicMock(spec=InstanceModel)
    mock_instance.name = "inst1"
    mock_instance.apikey = "k1"
    use_case.db.query.return_value.get.return_value = mock_instance

    mock_target = MagicMock(spec=WhatsAppTargetModel)
    mock_target.name = "João Silva"
    use_case.target_repo.db.query.return_value.filter_by.return_value.first.return_value = mock_target

    with patch(
        "core.application.use_cases.execute_broadcast_campaign.EvolutionWhatsAppService"
    ) as MockSvc:
        mock_svc = MockSvc.return_value
        mock_svc.send_text = AsyncMock(return_value=True)
        mock_svc.set_presence = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await use_case.execute(1)

    assert campaign.sent_count == 2
    assert campaign.failed_count == 0
    assert campaign.status == "sent"


@pytest.mark.asyncio
async def test_execute_final_status_failed_when_all_sends_fail(use_case):
    """If every send fails, the final status is 'failed'."""
    campaign = MagicMock()
    campaign.id = 2
    campaign.status = "scheduled"
    campaign.target_type = "contacts"
    campaign.target_jids = ["5511111@s.whatsapp.net"]
    campaign.user_id = 1
    campaign.image_url = None
    campaign.message = "Teste"
    use_case.broadcast_repo.get_by_id.return_value = campaign

    from core.infrastructure.database.models import InstanceModel
    mock_instance = MagicMock(spec=InstanceModel)
    mock_instance.name = "inst1"
    mock_instance.apikey = "k1"
    use_case.db.query.return_value.get.return_value = mock_instance

    use_case.target_repo.db.query.return_value.filter_by.return_value.first.return_value = None

    with patch(
        "core.application.use_cases.execute_broadcast_campaign.EvolutionWhatsAppService"
    ) as MockSvc:
        mock_svc = MockSvc.return_value
        mock_svc.send_text = AsyncMock(return_value=False)
        mock_svc.set_presence = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await use_case.execute(2)

    assert campaign.status == "failed"
    assert campaign.failed_count == 1
