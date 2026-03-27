import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from core.application.use_cases.schedule_campaign import ScheduleCampaign
from core.domain.entities import Product, Campaign, CampaignStatus

@pytest.mark.asyncio
async def test_schedule_campaign_success():
    product_repo = MagicMock()
    campaign_repo = MagicMock()
    notification_service = MagicMock()
    ai_service = AsyncMock()
    
    product = Product(id=1, name="Test Product", description="Desc", price=10.0, affiliate_link="http://link.com", user_id=1)
    product_repo.get_by_id.return_value = product
    
    use_case = ScheduleCampaign(campaign_repo, product_repo, notification_service, ai_service)
    
    ai_service.chat.return_value = "AI generated message"
    
    campaign = await use_case.execute(
        title="Test Title",
        product_id=1,
        target_groups=["group1"],
        scheduled_at=datetime.utcnow(),
        use_ai=True,
        user_id=1
    )
    
    assert campaign is not None
    product_repo.get_by_id.assert_called_once_with(1)
    campaign_repo.save.assert_called_once()
    ai_service.chat.assert_called_once()

@pytest.mark.asyncio
async def test_schedule_campaign_product_not_found():
    product_repo = MagicMock()
    campaign_repo = MagicMock()
    notification_service = MagicMock()
    
    product_repo.get_by_id.return_value = None
    
    use_case = ScheduleCampaign(campaign_repo, product_repo, notification_service)
    
    with pytest.raises(ValueError, match="Product with ID 999 not found"):
        await use_case.execute(
            title="Test",
            product_id=999,
            target_groups=[],
            scheduled_at=None
        )

@pytest.mark.asyncio
async def test_schedule_campaign_as_draft():
    product_repo = MagicMock()
    campaign_repo = MagicMock()
    notification_service = MagicMock()
    
    product = Product(id=1, name="P", description="D", price=1.0, affiliate_link="L", user_id=1)
    product_repo.get_by_id.return_value = product
    
    use_case = ScheduleCampaign(campaign_repo, product_repo, notification_service)
    
    await use_case.execute(
        title="Draft",
        product_id=1,
        target_groups=[],
        scheduled_at=None,
        save_as_draft=True
    )
    
    args, kwargs = campaign_repo.save.call_args
    saved_campaign = args[0]
    assert saved_campaign.status == CampaignStatus.DRAFT
