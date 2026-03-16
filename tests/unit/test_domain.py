import pytest
from datetime import datetime
from core.domain.entities import Product, Contact, Message, MessageType


def test_product_creation():
    product = Product(
        name="Test Product",
        description="A test product description",
        price=100.0,
        affiliate_link="https://example.com/test",
    )
    assert product.name == "Test Product"
    assert product.price == 100.0
    assert product.is_active is True


def test_contact_creation():
    contact = Contact(phone_number="5511999999999", name="John Doe")
    assert contact.phone_number == "5511999999999"
    assert contact.name == "John Doe"


def test_message_creation():
    contact = Contact(phone_number="5511999999999")
    from core.domain.entities import Conversation

    conversation = Conversation(contact=contact)
    message = Message(
        conversation=conversation, message_type=MessageType.SENT, content="Hello Test"
    )
    assert message.content == "Hello Test"
    assert message.message_type == MessageType.SENT
