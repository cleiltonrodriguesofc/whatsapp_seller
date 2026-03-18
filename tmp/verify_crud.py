
from core.infrastructure.database.session import SessionLocal
from core.infrastructure.database.repositories import SQLProductRepository, SQLCampaignRepository
from core.domain.entities import Product, Campaign, CampaignStatus
from datetime import datetime

def test_crud():
    db = SessionLocal()
    try:
        product_repo = SQLProductRepository(db)
        campaign_repo = SQLCampaignRepository(db)
        
        # 1. Create Product
        product = Product(
            name="Test Product",
            description="Test Description",
            price=99.99,
            affiliate_link="http://example.com",
            user_id=1
        )
        saved_product = product_repo.save(product)
        print(f"Created Product: {saved_product.id}")
        
        # 2. Update Product
        saved_product.name = "Updated Test Product"
        updated_product = product_repo.save(saved_product)
        print(f"Updated Product Name: {updated_product.name}")
        
        # 3. Create Campaign
        campaign = Campaign(
            title="Test Campaign",
            product=updated_product,
            target_groups=["group1@g.us", "group2@g.us"],
            scheduled_at=datetime.utcnow(),
            user_id=1,
            instance_id=None
        )
        saved_campaign = campaign_repo.save(campaign)
        print(f"Created Campaign: {saved_campaign.id} with {len(saved_campaign.target_groups)} targets")
        
        # 4. Reload and check targets
        reloaded_campaign = campaign_repo.get_by_id(saved_campaign.id)
        print(f"Reloaded Campaign Targets: {reloaded_campaign.target_groups}")
        assert len(reloaded_campaign.target_groups) == 2
        
        # 5. Update Campaign
        reloaded_campaign.target_groups = ["group3@g.us"]
        updated_campaign = campaign_repo.save(reloaded_campaign)
        reloaded_updated = campaign_repo.get_by_id(updated_campaign.id)
        print(f"Updated Campaign Targets: {reloaded_updated.target_groups}")
        assert len(reloaded_updated.target_groups) == 1
        
        # 6. Delete Campaign
        success = campaign_repo.delete(saved_campaign.id, user_id=1)
        print(f"Deleted Campaign Success: {success}")
        
        # 7. Delete Product
        success = product_repo.delete(saved_product.id, user_id=1)
        print(f"Deleted Product Success: {success}")
        
        print("CRUD Logic Verification PASSED!")
        
    except Exception as e:
        print(f"CRUD Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_crud()
