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


def test_target_repository_upsert_sync_with_instance(db_session):
    repo = SQLTargetRepository(db_session)
    targets_inst1 = [{"id": "111@g.us", "subject": "Group Inst1"}, {"id": "222@s.whatsapp.net", "subject": "User Inst1"}]
    targets_inst2 = [{"id": "333@g.us", "subject": "Group Inst2"}]

    repo.upsert_sync(targets_inst1, user_id=1, instance_id=1)
    repo.upsert_sync(targets_inst2, user_id=1, instance_id=2)

    all_targets = repo.list_all(user_id=1)
    assert len(all_targets) == 3

    # Check instance 1 targets
    t1 = next(t for t in all_targets if t.jid == "111@g.us")
    assert t1.instance_id == 1
    
    # Check instance 2 targets
    t2 = next(t for t in all_targets if t.jid == "333@g.us")
    assert t2.instance_id == 2
    
    # Check updating existing target shifts instance safely (or keeps it) based on implementation
    # With upsert_sync, if same JID comes from same user but different instance, it updates it.
    repo.upsert_sync([{"id": "333@g.us", "subject": "Group Inst2 Updated"}], user_id=1, instance_id=2)
    t2_updated = next(t for t in repo.list_all(user_id=1) if t.jid == "333@g.us")
    assert t2_updated.name == "Group Inst2 Updated"
    assert t2_updated.instance_id == 2


def test_campaign_repository_list_pending(db_session):
    # repo = SQLCampaignRepository(db_session)
    # ... setup pending campaigns ...
    pass

def test_target_repository_list_deduplication(db_session):
    from core.infrastructure.database.models import WhatsAppTargetModel
    from datetime import datetime
    
    db_session.add(WhatsAppTargetModel(user_id=1, instance_id=1, jid="dup@g.us", name="Group Inst 1", type="group", last_synced_at=datetime.utcnow(), is_active=True))
    db_session.add(WhatsAppTargetModel(user_id=1, instance_id=2, jid="dup@g.us", name="Group Inst 2", type="group", last_synced_at=datetime.utcnow(), is_active=True))
    db_session.commit()
    
    repo = SQLTargetRepository(db_session)
    # When no instance is provided, should deduplicate by JID
    groups_all = repo.list_groups(user_id=1, instance_id=None)
    assert len(groups_all) == 1
    assert groups_all[0].jid == "dup@g.us"
    
    # When instance is provided, should return exact match
    groups_inst1 = repo.list_groups(user_id=1, instance_id=1)
    assert len(groups_inst1) == 1
    assert groups_inst1[0].instance_id == 1

def test_target_repository_legacy_sync_no_duplicates(db_session):
    from core.infrastructure.database.models import WhatsAppTargetModel
    from datetime import datetime
    
    # Simulate a legacy target synced before instance logic existed
    db_session.add(WhatsAppTargetModel(
        user_id=1, instance_id=None, jid="legacy@g.us", name="Legacy Group", type="group", last_synced_at=datetime.utcnow(), is_active=True
    ))
    db_session.commit()
    
    repo = SQLTargetRepository(db_session)
    targets_inst1 = [{"id": "legacy@g.us", "subject": "Legacy Group Synced Now"}]
    
    # Sync using a modern instance
    repo.upsert_sync(targets_inst1, user_id=1, instance_id=1)
    
    all_targets = db_session.query(WhatsAppTargetModel).filter_by(jid="legacy@g.us").all()
    # Should NOT have created a new row, but updated the legacy one
    assert len(all_targets) == 1
    assert all_targets[0].instance_id == 1
    assert all_targets[0].name == "Legacy Group Synced Now"
