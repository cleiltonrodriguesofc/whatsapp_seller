from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum as SQLEnum, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class CampaignStatus(enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"

# Association table for Campaign - Group
campaign_groups = Table(
    'campaign_groups',
    Base.metadata,
    Column('campaign_id', Integer, ForeignKey('campaigns.id')),
    Column('group_jid', String)
)

class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    affiliate_link = Column(String)
    image_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class WhatsAppTargetModel(Base):
    __tablename__ = "whatsapp_targets"
    id = Column(Integer, primary_key=True, index=True)
    jid = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String) # 'group' or 'chat'
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, default=datetime.utcnow)

class CampaignModel(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))
    scheduled_at = Column(DateTime)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.PENDING)
    custom_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    product = relationship("ProductModel")
