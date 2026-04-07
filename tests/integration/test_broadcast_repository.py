import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.infrastructure.database.models import Base
from core.infrastructure.database.repositories import (
    SQLBroadcastListRepository,
    SQLBroadcastCampaignRepository,
)
from core.domain.entities import BroadcastList, BroadcastCampaign


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_broadcast_list_repository_save_and_get(db_session):
    repo = SQLBroadcastListRepository(db_session)
    blist = BroadcastList(
        user_id=1,
        instance_id=2,
        name="Integration Test List",
        description="Testing repo",
    )

    # Save
    saved_list = repo.save(blist)
    assert saved_list.id is not None
    assert saved_list.instance_id == 2

    # Get
    retrieved = repo.get_by_id(saved_list.id, user_id=1)
    assert retrieved.name == "Integration Test List"
    assert retrieved.instance_id == 2
    assert retrieved.member_count == 0


def test_broadcast_campaign_repository_save_and_list(db_session):
    repo = SQLBroadcastCampaignRepository(db_session)
    campaign = BroadcastCampaign(
        user_id=1,
        instance_id=1,
        title="Integration Campaign",
        target_type="list",
        target_jids=["jid1"],
        message="Integration message",
        scheduled_at=datetime.utcnow(),
        status="scheduled",
    )

    # Save
    saved = repo.save(campaign)
    assert saved.id is not None

    # List
    all_campaigns = repo.list_all(user_id=1)
    assert len(all_campaigns) == 1
    assert all_campaigns[0].title == "Integration Campaign"


def test_broadcast_campaign_repository_delete(db_session):
    repo = SQLBroadcastCampaignRepository(db_session)
    campaign = BroadcastCampaign(
        user_id=1,
        instance_id=1,
        title="ToDelete",
        target_type="contacts",
        message="Delete me",
        scheduled_at=datetime.utcnow(),
    )
    saved = repo.save(campaign)

    success = repo.delete(saved.id, user_id=1)
    assert success is True
    assert repo.get_by_id(saved.id) is None
