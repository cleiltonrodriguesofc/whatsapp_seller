from datetime import datetime
from core.domain.entities import StatusCampaign, CampaignStatus
from core.infrastructure.database.repositories import SQLStatusCampaignRepository
from core.infrastructure.database.models import UserModel, InstanceModel


def test_status_campaign_repository_save_and_get(db_session):
    repo = SQLStatusCampaignRepository(db_session)

    # Create test user
    user = UserModel(email="status_repo@test.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()

    # Create test instance
    instance = InstanceModel(user_id=user.id, name="test_inst", status="connected")
    db_session.add(instance)
    db_session.commit()

    now = datetime.utcnow()
    campaign = StatusCampaign(
        title="Repo Test Status",
        scheduled_at=now,
        image_url="http://image.com",
        caption="Repo Caption",
        user_id=user.id,
        instance_id=instance.id,
        target_contacts=["123@s.whatsapp.net"],
    )

    saved = repo.save(campaign)
    assert saved.id is not None

    fetched = repo.get_by_id(saved.id, user_id=user.id)
    assert fetched.title == "Repo Test Status"
    assert fetched.caption == "Repo Caption"
    assert fetched.target_contacts == ["123@s.whatsapp.net"]
    assert fetched.instance_id == instance.id


def test_status_campaign_repository_list_pending(db_session):
    repo = SQLStatusCampaignRepository(db_session)
    user = UserModel(email="list_pending@test.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()

    now = datetime.utcnow()
    c1 = StatusCampaign(title="C1", scheduled_at=now, status=CampaignStatus.SCHEDULED, user_id=user.id)
    c2 = StatusCampaign(title="C2", scheduled_at=now, status=CampaignStatus.SENT, user_id=user.id)

    repo.save(c1)
    repo.save(c2)

    pending = repo.list_pending(user_id=user.id)
    assert len(pending) == 1
    assert pending[0].title == "C1"


def test_status_campaign_repository_delete(db_session):
    repo = SQLStatusCampaignRepository(db_session)
    user = UserModel(email="delete_status@test.com", hashed_password="hash")
    db_session.add(user)
    db_session.commit()

    campaign = StatusCampaign(title="To Delete", scheduled_at=datetime.utcnow(), user_id=user.id)
    saved = repo.save(campaign)

    success = repo.delete(saved.id, user_id=user.id)
    assert success is True

    fetched = repo.get_by_id(saved.id, user_id=user.id)
    assert fetched is None
