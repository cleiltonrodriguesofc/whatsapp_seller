from core.infrastructure.database.models import (
    UserModel,
    InstanceModel,
    ProductModel,
    WhatsAppTargetModel,
    CampaignModel,
    StatusCampaignModel,
    BroadcastListModel,
    BroadcastCampaignModel,
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
        user_id=1, name="Prod", description="Desc", price=9.99, affiliate_link="link"
    )
    assert product.name == "Prod"
    assert product.price == 9.99


def test_whatsapp_target_model():
    target = WhatsAppTargetModel(
        user_id=1, jid="123@s.whatsapp.net", name="John", type="chat"
    )
    assert target.jid == "123@s.whatsapp.net"
    assert target.type == "chat"


def test_campaign_model():
    campaign = CampaignModel(user_id=1, title="Camp", product_id=1)
    assert campaign.title == "Camp"
    assert campaign.product_id == 1


def test_status_campaign_model_refinements():
    model = StatusCampaignModel(
        user_id=1,
        title="Status",
        link="http://link",
        price=10.0,
        background_color="#FFFFFF",
    )
    assert model.link == "http://link"
    assert model.price == 10.0
    assert model.background_color == "#FFFFFF"


def test_broadcast_list_model():
    model = BroadcastListModel(user_id=1, name="List")
    assert model.name == "List"
    assert model.user_id == 1


def test_broadcast_campaign_model():
    model = BroadcastCampaignModel(user_id=1, title="BCamp", status="sent")
    assert model.title == "BCamp"
    assert model.status == "sent"
