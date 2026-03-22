from core.infrastructure.database.models import (
    UserModel,
    InstanceModel,
    ProductModel,
    WhatsAppTargetModel,
    CampaignModel,
)

def test_user_model():
    user = UserModel(email="test@models.com", hashed_password="pw")
    assert user.email == "test@models.com"
    assert user.hashed_password == "pw"

def test_instance_model():
    instance = InstanceModel(user_id=1, name="inst_name")
    assert instance.user_id == 1
    assert instance.name == "inst_name"

def test_product_model():
    product = ProductModel(
        user_id=1,
        name="Prod",
        description="Desc",
        price=9.99,
        affiliate_link="link"
    )
    assert product.name == "Prod"
    assert product.price == 9.99

def test_whatsapp_target_model():
    target = WhatsAppTargetModel(
        user_id=1,
        jid="123@s.whatsapp.net",
        name="John",
        type="chat"
    )
    assert target.jid == "123@s.whatsapp.net"
    assert target.type == "chat"

def test_campaign_model():
    campaign = CampaignModel(
        user_id=1,
        title="Camp",
        product_id=1
    )
    assert campaign.title == "Camp"
    assert campaign.product_id == 1

