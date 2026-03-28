from datetime import datetime
from core.domain.entities import StatusCampaign, CampaignStatus


def test_status_campaign_entity_creation():
    """Test standard creation of StatusCampaign entity."""
    now = datetime.utcnow()
    campaign = StatusCampaign(
        title="Test Status",
        scheduled_at=now,
        image_url="http://example.com/image.jpg",
        caption="Check out my status!",
        user_id=1,
        instance_id=1,
    )

    assert campaign.title == "Test Status"
    assert campaign.scheduled_at == now
    assert campaign.image_url == "http://example.com/image.jpg"
    assert campaign.caption == "Check out my status!"
    assert campaign.status == CampaignStatus.PENDING
    assert campaign.background_color == "#128C7E"  # Default value
    assert campaign.target_contacts == []
    assert isinstance(campaign.created_at, datetime)


def test_status_campaign_entity_defaults():
    """Test default values for StatusCampaign entity."""
    campaign = StatusCampaign(title="Default Test", scheduled_at=datetime.utcnow())
    assert campaign.background_color == "#128C7E"
    assert campaign.status == CampaignStatus.PENDING
    assert campaign.target_contacts == []


def test_status_campaign_recurring():
    """Test recurring fields in StatusCampaign entity."""
    campaign = StatusCampaign(
        title="Recurring Status",
        scheduled_at=datetime.utcnow(),
        is_recurring=True,
        recurrence_days="mon,wed,fri",
        send_time="10:00",
    )
    assert campaign.is_recurring is True
    assert campaign.recurrence_days == "mon,wed,fri"
    assert campaign.send_time == "10:00"
