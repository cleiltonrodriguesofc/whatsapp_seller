from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Enum as SQLEnum,
    ForeignKey,
    Table,
)
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


class StatusCampaignStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


# Association table for Campaign - Group
campaign_groups = Table(
    "campaign_groups",
    Base.metadata,
    Column("campaign_id", Integer, ForeignKey("campaigns.id")),
    Column("group_jid", String),
)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("ProductModel", back_populates="user")
    instances = relationship("InstanceModel", back_populates="user")


class InstanceModel(Base):
    __tablename__ = "instances"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, unique=True, nullable=False)  # Evolution instance name
    display_name = Column(String, nullable=True)  # User custom friendly name
    apikey = Column(String, nullable=True)  # Specific instance apikey if different
    status = Column(String, default="disconnected")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserModel", back_populates="instances")


class ProductModel(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    affiliate_link = Column(String)
    image_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserModel", back_populates="products")


class WhatsAppTargetModel(Base):
    __tablename__ = "whatsapp_targets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    jid = Column(String, unique=False, index=True, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String)  # 'group' or 'chat'
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, default=datetime.utcnow)


class CampaignModel(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    title = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))
    instance_id = Column(
        Integer, ForeignKey("instances.id"), nullable=True
    )  # Link to specific instance
    scheduled_at = Column(DateTime)
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.PENDING, index=True)
    custom_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    # Recurring Scheduling (Alarm style)
    is_recurring = Column(Boolean, default=False, index=True)
    recurrence_days = Column(String, nullable=True)  # "mon,tue,wed,thu,fri,sat,sun"
    send_time = Column(String, nullable=True)  # "HH:MM"
    last_run_at = Column(
        DateTime, nullable=True
    )  # To prevent double-send in the same day
    target_config = Column(
        Text, nullable=True
    )  # JSON stored as string: {"status": "07:00", "groups": ["08:00", "12:00"]}
    is_ai_generated = Column(Boolean, default=False)

    product = relationship("ProductModel")
    instance = relationship("InstanceModel")
    target_groups = relationship(
        "WhatsAppTargetModel",
        secondary=campaign_groups,
        primaryjoin="CampaignModel.id == campaign_groups.c.campaign_id",
        secondaryjoin="WhatsAppTargetModel.jid == campaign_groups.c.group_jid",
        viewonly=True,
    )


class StatusCampaignModel(Base):
    __tablename__ = "status_campaigns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    instance_id = Column(Integer, ForeignKey("instances.id"), nullable=True)
    title = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(StatusCampaignStatus), default=StatusCampaignStatus.DRAFT, index=True)
    is_recurring = Column(Boolean, default=False, index=True)
    recurrence_days = Column(String, nullable=True)
    send_time = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    items = relationship("StatusItemModel", back_populates="campaign", cascade="all, delete-orphan")
    user = relationship("UserModel")
    instance = relationship("InstanceModel")


class StatusItemModel(Base):
    __tablename__ = "status_items"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("status_campaigns.id"))
    image_url = Column(String, nullable=False)
    caption = Column(Text, nullable=True)
    link = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    position = Column(Integer, default=0)

    campaign = relationship("StatusCampaignModel", back_populates="items")
