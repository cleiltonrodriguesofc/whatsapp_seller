from datetime import datetime
from core.domain.entities import Product, Campaign
from core.infrastructure.database.repositories import SQLCampaignRepository, SQLTargetRepository


def test_campaign_repository_save_and_get(db_session):
    repo = SQLCampaignRepository(db_session)

    product = Product(
        id=1, name="Test Product", description="Desc", price=10.0, affiliate_link="http://link.com", user_id=1
    )
    # Ensure product exists or mock it if needed
    # For now, let's assume existence or add it
    from core.infrastructure.database.models import ProductModel

    db_session.add(
        ProductModel(
            id=1, name="Test Product", description="Desc", price=10.0, affiliate_link="http://link.com", user_id=1
        )
    )
    db_session.commit()

    campaign = Campaign(
        title="Test Campaign",
        product=product,
        target_groups=[],
        instance_id=1,
        user_id=1,
        scheduled_at=datetime.utcnow(),
    )

    saved = repo.save(campaign)
    assert saved.id is not None

    fetched = repo.get_by_id(saved.id, user_id=1)
    assert fetched is not None
    assert fetched.title == "Test Campaign"


def test_target_repository_upsert_sync(db_session):
    repo = SQLTargetRepository(db_session)
    targets = [{"id": "123@g.us", "subject": "Group 1"}, {"id": "456@s.whatsapp.net", "subject": "User 1"}]

    repo.upsert_sync(targets, user_id=1)

    all_targets = repo.list_all(user_id=1)
    assert len(all_targets) == 2
    assert any(t.jid == "123@g.us" for t in all_targets)


def test_campaign_repository_list_pending(db_session):
    # repo = SQLCampaignRepository(db_session)
    # ... setup pending campaigns ...
    pass
