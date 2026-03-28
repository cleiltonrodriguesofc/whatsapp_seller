from datetime import datetime
from core.domain.entities import (
    Contact,
    Conversation,
    Group,
    Instance,
    Message,
    MessageType,
    Product,
    Sale,
    SaleStatus,
    User,
    Campaign,
    CampaignStatus,
)


def test_product_entity():
    product = Product(
        name="Test",
        description="Desc",
        price=10.0,
        affiliate_link="http://link",
    )
    assert product.name == "Test"
    assert product.is_active is True
    assert isinstance(product.created_at, datetime)


def test_contact_entity():
    contact = Contact(phone_number="123456789")
    assert contact.phone_number == "123456789"
    assert contact.is_allowed is True
    assert isinstance(contact.created_at, datetime)


def test_group_entity():
    group = Group(group_id="group@g.us", name="Test Group")
    assert group.group_id == "group@g.us"
    assert group.is_allowed is True
    assert isinstance(group.created_at, datetime)


def test_conversation_entity():
    contact = Contact(phone_number="123")
    conv = Conversation(contact=contact)
    assert conv.contact == contact
    assert conv.status == "active"
    assert isinstance(conv.started_at, datetime)
    assert conv.closed_at is None


def test_message_entity():
    contact = Contact(phone_number="123")
    conv = Conversation(contact=contact)
    msg = Message(conversation=conv, message_type=MessageType.SENT, content="Hello")
    assert msg.message_type == MessageType.SENT
    assert msg.content == "Hello"
    assert isinstance(msg.timestamp, datetime)


def test_sale_entity():
    contact = Contact(phone_number="123")
    conv = Conversation(contact=contact)
    product = Product(name="p", description="d", price=1.0, affiliate_link="link")
    sale = Sale(conversation=conv, product=product, quantity=1, total_price=1.0)
    assert sale.status == SaleStatus.PENDING
    assert isinstance(sale.created_at, datetime)


def test_campaign_entity():
    product = Product(name="p", description="d", price=1.0, affiliate_link="link")
    campaign = Campaign(title="Promo", product=product, target_groups=["g1", "g2"], scheduled_at=datetime.utcnow())
    assert campaign.status == CampaignStatus.PENDING
    assert campaign.is_recurring is False
    assert campaign.target_config == {}


def test_user_entity():
    user = User(email="test@test.com", hashed_password="hash")
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)


def test_instance_entity():
    inst = Instance(user_id=1, name="inst1")
    assert inst.status == "disconnected"
    assert isinstance(inst.created_at, datetime)
