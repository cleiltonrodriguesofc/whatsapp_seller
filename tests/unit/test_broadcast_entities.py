from datetime import datetime
from core.domain.entities import BroadcastList, BroadcastCampaign


def test_broadcast_list_entity_creation():
    """Test creation of BroadcastList entity."""
    now = datetime.utcnow()
    blist = BroadcastList(
        id=1,
        user_id=1,
        name="Test List",
        description="A test description",
        member_count=10,
        created_at=now
    )

    assert blist.id == 1
    assert blist.user_id == 1
    assert blist.name == "Test List"
    assert blist.description == "A test description"
    assert blist.member_count == 10
    assert blist.created_at == now


def test_broadcast_campaign_entity_creation():
    """Test creation of BroadcastCampaign entity."""
    now = datetime.utcnow()
    campaign = BroadcastCampaign(
        id=1,
        user_id=1,
        instance_id=1,
        title="Test Campaign",
        target_type="list",
        target_jids=["group1", "group2"],
        list_id=1,
        message="Hello world",
        image_url="http://example.com/img.jpg",
        scheduled_at=now,
        status="scheduled"
    )

    assert campaign.id == 1
    assert campaign.user_id == 1
    assert campaign.title == "Test Campaign"
    assert campaign.target_type == "list"
    assert campaign.target_jids == ["group1", "group2"]
    assert campaign.list_id == 1
    assert campaign.message == "Hello world"
    assert campaign.image_url == "http://example.com/img.jpg"
    assert campaign.scheduled_at == now
    assert campaign.status == "scheduled"
    assert campaign.sent_count == 0
    assert campaign.failed_count == 0
    assert campaign.total_targets == 0


def test_broadcast_campaign_defaults():
    """Test default values for BroadcastCampaign entity."""
    campaign = BroadcastCampaign(
        user_id=1,
        instance_id=1,
        title="Draft Campaign",
        target_type="contacts",
        message="Test message",
        scheduled_at=datetime.utcnow()
    )

    assert campaign.status == "draft"
    assert campaign.is_recurring is False
    assert campaign.sent_count == 0
    assert campaign.failed_count == 0
    assert campaign.total_targets == 0
